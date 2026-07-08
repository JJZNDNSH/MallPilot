"""
MallPilot 综合电商导购助手 FastAPI 入口。

这个模块负责初始化导购业务所需的 Agent、记忆、知识库、结构化数据、监控与评测组件。
"""
import asyncio
import json
import logging
import os
import pathlib
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple

# 做什么：把项目根目录注入模块搜索路径。
# 为什么：保证从不同目录启动时都能正确导入项目内模块。
_ROOT = str(pathlib.Path(__file__).parent.parent.resolve())
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

# 做什么：加载 .env 并允许覆盖系统同名环境变量。
# 为什么：确保本地调试时以项目内 .env 配置为准，避免被机器上的旧变量劫持。
load_dotenv(override=True)

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BANNER = r"""
 __  __       _ _ ____  _ _       _
|  \/  | __ _| | |  _ \(_) | ___ | |_
| |\/| |/ _` | | | |_) | | |/ _ \| __|
| |  | | (_| | | |  __/| | | (_) | |_
|_|  |_|\__,_|_|_|_|   |_|_|\___/ \__|

MallPilot v2.0  综合电商导购助手
"""

# 做什么：保存生命周期内共享的全局组件。
# 为什么：让路由、监控和 CLI 共享同一批运行时对象。
_orchestrator = None
_memory = None
_tool_manager = None
_monitor = None
_evaluator = None
_skill_manager = None
_commerce_store = None


# 做什么：统一读取环境变量，支持新旧变量平滑迁移。
# 为什么：新配置以 MallPilot 为主，同时避免已有环境立即失效。
def _get_env(name: str, default: str = "", legacy_name: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    if legacy_name:
        legacy_value = os.getenv(legacy_name)
        if legacy_value:
            return legacy_value
    return default


# 做什么：读取布尔型环境变量。
# 为什么：让演示数据开关等配置更直观。
def _get_bool_env(name: str, default: bool, legacy_name: str = "") -> bool:
    raw = _get_env(name, str(default).lower(), legacy_name)
    return raw.strip().lower() not in {"0", "false", "no", "off"}


# 做什么：归一化用于 Anthropic SDK 的 base_url。
# 为什么：避免把 OpenAI 兼容地址直接传给 Anthropic SDK 后在运行时才报错。
def _normalize_anthropic_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return ""

    # 做什么：把 DashScope 的 OpenAI 兼容入口改写为 Anthropic 兼容入口。
    # 为什么：当前项目统一使用 Anthropic SDK，必须命中 `/apps/anthropic` 才能走 Messages 接口。
    if "/compatible-mode" in normalized and ("dashscope.aliyuncs.com" in normalized or ".maas.aliyuncs.com" in normalized):
        return normalized.split("/compatible-mode", 1)[0] + "/apps/anthropic"
    return normalized


# 做什么：从 base_url 推断当前接入的服务商。
# 为什么：在启动阶段做最小必要的模型兼容性校验，尽早暴露明显错配。
def _provider_from_base_url(base_url: str) -> str:
    lowered = base_url.lower()
    if "moonshot" in lowered:
        return "moonshot"
    if "dashscope.aliyuncs.com" in lowered or ".maas.aliyuncs.com" in lowered:
        return "dashscope"
    return "custom"


# 做什么：校验模型名是否与当前服务商匹配。
# 为什么：把“模型不存在/无权限”这类确定性配置错误提前到启动阶段拦住。
def _validate_anthropic_model(model: str, base_url: str) -> None:
    provider = _provider_from_base_url(base_url)
    normalized_model = model.strip().lower()
    if provider == "moonshot" and normalized_model and not normalized_model.startswith(("kimi-", "moonshot-")):
        raise RuntimeError(
            f"ANTHROPIC_MODEL={model} 与 Moonshot 接入不匹配。请改用 Moonshot 支持的 Kimi/Moonshot 系列模型，或改回与当前 SDK 兼容的服务商配置。"
        )


# 做什么：组装 LLM 配置。
# 为什么：减少不同入口对同一组模型配置的重复读取。
def _anthropic_cfg() -> Dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("未设置 ANTHROPIC_API_KEY")
    config: Dict[str, Any] = {
        "api_key": api_key,
        "model": _get_env("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022", "CLAUDE_MODEL"),
    }
    raw_base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip()
    base_url = _normalize_anthropic_base_url(raw_base_url)
    if base_url:
        # 做什么：记录被自动纠正的兼容地址。
        # 为什么：方便排查“环境里填的是一个地址，实际请求却去了另一个地址”的现象。
        if raw_base_url and raw_base_url.rstrip("/") != base_url:
            logger.warning("ANTHROPIC_BASE_URL 已自动修正: %s -> %s", raw_base_url, base_url)
        # 做什么：在统一配置出口校验模型与服务商是否兼容。
        # 为什么：避免同一份错误配置被多个组件复用后重复触发 404。
        _validate_anthropic_model(config["model"], base_url)
        config["base_url"] = base_url
    return config


# 做什么：组装 MySQL 业务数据配置。
# 为什么：把商品、订单、售后和工具层统一切到 MySQL 真实数据源。
def _commerce_cfg() -> Dict[str, Any]:
    return {
        "host": _get_env("MALLPILOT_MYSQL_HOST", "127.0.0.1"),
        "port": int(_get_env("MALLPILOT_MYSQL_PORT", "3306")),
        "user": _get_env("MALLPILOT_MYSQL_USER", "mallpilot"),
        "password": _get_env("MALLPILOT_MYSQL_PASSWORD", "mallpilot123"),
        "database": _get_env("MALLPILOT_MYSQL_DATABASE", "mallpilot"),
        "charset": _get_env("MALLPILOT_MYSQL_CHARSET", "utf8mb4"),
        "connect_timeout": int(_get_env("MALLPILOT_MYSQL_CONNECT_TIMEOUT", "5")),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期入口。"""

    global _orchestrator, _memory, _tool_manager, _monitor, _evaluator, _skill_manager, _commerce_store

    print(BANNER, flush=True)

    from agents.agent_orchestrator import AgentOrchestrator
    from core.commerce_store import CommerceStore
    from core.intent_recognizer import IntentRecognizer
    from core.skill_loader import SkillManager
    from evaluation.evaluator import EndToEndEvaluator
    from mcp.knowledge_base import KnowledgeBase
    from mcp.tool_manager import MCPToolManager, Tool
    from memory.conversation_memory import MemoryManager
    from monitor.performance_monitor import PerformanceMonitor
    from tools.tool_registry import register_commerce_tools

    cfg = _anthropic_cfg()
    logger.info("MallPilot 模型: %s base_url: %s", cfg["model"], cfg.get("base_url", "(官方)"))

    # 做什么：初始化意图识别器供评测器复用。
    # 为什么：评测器需要直接调用识别链路，而不是只走 /chat。
    recognizer = IntentRecognizer(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )

    # 做什么：初始化 Skill 管理器。
    # 为什么：让导购、订单、售后规则支持热加载。
    skills_dir = _get_env("MALLPILOT_SKILLS_DIR", str(pathlib.Path(_ROOT) / "skills"), "ECHOMIND_SKILLS_DIR")
    max_prompt_chars = int(_get_env("MALLPILOT_SKILLS_MAX_PROMPT_CHARS", "5000", "ECHOMIND_SKILLS_MAX_PROMPT_CHARS"))
    _skill_manager = SkillManager(root_dir=skills_dir, max_prompt_chars=max_prompt_chars)
    _skill_manager.load()

    # 做什么：初始化结构化商品、订单与售后库。
    # 为什么：让导购与订单事实落到 MySQL，而不是靠 prompt 编造。
    commerce_cfg = _commerce_cfg()
    _commerce_store = CommerceStore(
        host=commerce_cfg["host"],
        port=commerce_cfg["port"],
        user=commerce_cfg["user"],
        password=commerce_cfg["password"],
        database=commerce_cfg["database"],
        seed_demo_data=_get_bool_env("MALLPILOT_SEED_DEMO_DATA", True),
        charset=commerce_cfg["charset"],
        connect_timeout=commerce_cfg["connect_timeout"],
    )
    _commerce_store.initialize()
    logger.info("MallPilot 结构化数据已初始化: %s", _commerce_store.stats())

    # 做什么：初始化 Agent 编排器。
    # 为什么：主对话链路、评测与监控都依赖这套编排逻辑。
    _orchestrator = AgentOrchestrator(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
        skill_manager=_skill_manager,
    )

    # 做什么：初始化三级记忆管理器。
    # 为什么：保留原项目的工作记忆、情景记忆与用户画像亮点。
    _memory = MemoryManager(
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        chroma_host=os.getenv("CHROMA_HOST", "chromadb"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "/app/data/chroma"),
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )

    # 做什么：初始化工具管理器和知识库。
    # 为什么：把 RAG 与结构化查询统一纳入工具层管理。
    _tool_manager = MCPToolManager(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )
    knowledge_base = KnowledgeBase(
        chroma_host=os.getenv("CHROMA_HOST", "chromadb"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "/app/data/chroma"),
    )

    # 做什么：知识库降级时返回可解释结果。
    # 为什么：避免 RAG 不可用时直接中断主对话链路。
    def knowledge_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str):
        query = params.get("query", "")
        return [
            {
                "title": "知识库降级结果",
                "content": f"知识库暂时不可用，未能完成对“{query}”的规则检索。请稍后重试，或先根据商品库/订单库信息继续判断。",
                "score": 0.0,
                "fallback": True,
                "error": error,
            }
        ]

    # 做什么：注册知识库搜索工具。
    # 为什么：保留查询改写、并行召回、重排与 fallback 亮点。
    _tool_manager.register(
        Tool(
            name="knowledge_search",
            description="搜索 MallPilot 规则知识库",
            handler=knowledge_base.search_handler,
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                },
                "required": ["query"],
            },
            cache_ttl=300.0,
            supports_rerank=True,
            fallback=knowledge_fallback,
        )
    )
    # 做什么：集中注册导购、订单与售后工具。
    # 为什么：让多角色工具统一收敛到 tools 目录，同时继续复用 MCPToolManager 的执行特色。
    register_commerce_tools(_tool_manager, _commerce_store)

    # 做什么：初始化监控闭环。
    # 为什么：保留在线表现自动降权的技术亮点。
    prom_port = int(os.getenv("PROMETHEUS_PORT", "0")) or None
    _monitor = PerformanceMonitor(
        orchestrator=_orchestrator,
        tool_manager=_tool_manager,
        interval_s=float(os.getenv("MONITOR_INTERVAL", "10")),
        webhook_url=os.getenv("ALERT_WEBHOOK_URL") or None,
        prometheus_port=prom_port,
    )
    await _monitor.start()

    # 做什么：初始化端到端评测器。
    # 为什么：保留意图识别、对话质量与回归检测闭环。
    _evaluator = EndToEndEvaluator(
        orchestrator=_orchestrator,
        recognizer=recognizer,
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
        baseline_path=os.getenv("EVAL_BASELINE_PATH", "/app/data/eval/baseline.json"),
    )

    logger.info("MallPilot 已就绪")
    yield

    await _monitor.stop()
    logger.info("MallPilot 已关闭")


app = FastAPI(
    title="MallPilot 综合电商导购助手",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """聊天请求。"""

    message: str  # 用户消息内容。
    user_id: str = "anonymous"  # 用户标识。
    conv_id: Optional[str] = None  # 会话标识。


class ChatResponse(BaseModel):
    """聊天响应。"""

    conv_id: str  # 当前会话标识。
    response: str  # Agent 最终回复。
    intent: str  # 本轮识别意图。
    agent_type: str  # 主处理 Agent 类型。
    escalated: bool  # 是否触发升级标记。
    latency_ms: float  # 本轮处理总耗时。
    knowledge_used: bool = False  # 本轮是否使用到知识库。


class CatalogSearchRequest(BaseModel):
    """商品搜索请求。"""

    query: str = ""  # 商品搜索关键词。
    category: Optional[str] = None  # 指定商品类目。
    min_price: Optional[float] = None  # 价格下限。
    max_price: Optional[float] = None  # 价格上限。
    limit: int = 5  # 返回条数上限。


class OrderLookupRequest(BaseModel):
    """订单查询请求。"""

    order_id: str  # 待查询订单号。
    user_id: Optional[str] = None  # 可选用户标识，用于做归属校验。


class DocInput(BaseModel):
    """知识库单篇文档输入。"""

    title: str  # 文档标题。
    content: str  # 文档正文。


class BatchDocInput(BaseModel):
    """知识库批量导入请求。"""

    documents: List[DocInput]  # 待导入文档列表。


class EvalIntentInput(BaseModel):
    """意图评测输入。"""

    message: str  # 测试消息。
    expected_intent: str  # 期望意图。
    context: Optional[Dict[str, Any]] = None  # 可选上下文。


class EvalDialogInput(BaseModel):
    """对话评测输入。"""

    question: Optional[str] = None  # 单轮问题。
    turns: Optional[List[str]] = None  # 多轮问题列表。
    user_id: Optional[str] = None  # 评测用户 ID。
    conv_id: Optional[str] = None  # 评测会话 ID。


class EvalRunInput(BaseModel):
    """评测请求。"""

    intent_cases: Optional[List[EvalIntentInput]] = None  # 自定义意图评测样例。
    dialog_cases: Optional[List[EvalDialogInput]] = None  # 自定义对话评测样例。


# 做什么：暴露健康检查接口。
# 为什么：便于容器编排、监控和人工排查运行状态。
@app.get("/health")
async def health():
    if _orchestrator is None or _commerce_store is None:
        raise HTTPException(503, "服务未就绪")
    return {
        "status": "ok",
        "agents": _orchestrator.get_stats(),
        "commerce": _commerce_store.stats(),
    }


# 做什么：查看当前 Skill 加载结果。
# 为什么：验证导购、订单、售后三套 Skills 是否已生效。
@app.get("/skills", tags=["Skills"])
async def skills_summary():
    if _skill_manager is None:
        raise HTTPException(503, "Skills 未初始化")
    return _skill_manager.summary()


# 做什么：运行时热加载 Skills。
# 为什么：修改 Skill 文件后无需重启即可生效。
@app.post("/skills/reload", tags=["Skills"])
async def reload_skills():
    if _skill_manager is None:
        raise HTTPException(503, "Skills 未初始化")
    _skill_manager.reload()
    if _orchestrator is not None:
        _orchestrator.set_skill_manager(_skill_manager)
    return _skill_manager.summary()


# 做什么：执行主对话链路。
# 为什么：把记忆、知识库、商品库、订单库和 Agent 编排串起来。
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if _orchestrator is None or _memory is None:
        raise HTTPException(503, "服务未就绪")

    from agents.agent_orchestrator import Request as OrcRequest
    from memory.conversation_memory import MsgRole

    conv_id = req.conv_id or str(uuid.uuid4())

    # 做什么：先读取三级记忆上下文。
    # 为什么：让多轮对话能延续订单、偏好和历史讨论信息。
    memory_context = await _memory.get_context(req.user_id, conv_id, query=req.message)
    history = [
        {"role": message.role.value, "content": message.content}
        for message in memory_context.recent_messages[-5:]
    ] if memory_context.recent_messages else None

    knowledge_text, knowledge_used = await _build_knowledge_context(req.message)
    structured_text = await _build_structured_context(req.message, req.user_id)
    context_parts = [memory_context.to_prompt_text(), knowledge_text, structured_text]
    full_context = "\n\n".join(part for part in context_parts if part)

    result = await _orchestrator.run(
        OrcRequest(
            message=req.message,
            user_id=req.user_id,
            conv_id=conv_id,
            context=full_context,
            history=history,
        )
    )

    await _memory.add_message(req.user_id, conv_id, MsgRole.USER, req.message)
    await _memory.add_message(req.user_id, conv_id, MsgRole.ASSISTANT, result.response)
    asyncio.create_task(_memory.update_profile(req.user_id, conv_id))

    return ChatResponse(
        conv_id=conv_id,
        response=result.response,
        intent=result.intent.value if result.intent else "other",
        agent_type=result.agent_type.value,
        escalated=result.escalated,
        latency_ms=round(result.latency_ms, 1),
        knowledge_used=knowledge_used,
    )


# 做什么：商品搜索演示接口。
# 为什么：直接展示 MySQL 商品库能力，便于校验数据层是否正确接入。
@app.post("/catalog/search")
async def catalog_search(body: CatalogSearchRequest):
    if _commerce_store is None:
        raise HTTPException(503, "商品库未初始化")
    results = _commerce_store.search_products(
        query=body.query,
        category=body.category,
        min_price=body.min_price,
        max_price=body.max_price,
        limit=body.limit,
    )
    return {"results": results, "count": len(results)}


# 做什么：订单查询演示接口。
# 为什么：直接展示 MySQL 订单库能力，便于核对订单与明细演示数据。
@app.post("/orders/lookup")
async def orders_lookup(body: OrderLookupRequest):
    if _commerce_store is None:
        raise HTTPException(503, "订单库未初始化")
    result = _commerce_store.lookup_order(order_id=body.order_id, user_id=body.user_id)
    if result is None:
        raise HTTPException(404, "未找到对应订单")
    return result


# 做什么：暴露监控摘要。
# 为什么：便于查看 Agent 与工具在线表现。
@app.get("/monitor")
async def monitor_summary():
    if _monitor is None:
        raise HTTPException(503, "服务未就绪")
    return _monitor.summary()


# 做什么：暴露 Prometheus 指标。
# 为什么：让 Prometheus 能稳定采集运行指标。
@app.get("/metrics")
async def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# 做什么：演示知识库检索链路。
# 为什么：单独验证查询改写、并行召回和重排能力。
@app.post("/search")
async def search(query: str, top_k: int = 5):
    if _tool_manager is None:
        raise HTTPException(503, "服务未就绪")
    result = await _tool_manager.search_with_rewrite("knowledge_search", query, top_k=top_k)
    return {"query": query, "results": result.data, "reranked": result.reranked}


# 做什么：批量导入知识库文档。
# 为什么：让 MallPilot 规则知识可以通过 API 扩充。
@app.post("/knowledge/add", tags=["知识库"])
async def add_knowledge(body: BatchDocInput):
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    knowledge_base = tool.handler.__self__
    added_chunks = knowledge_base.add_documents(
        [{"title": document.title, "content": document.content} for document in body.documents]
    )
    return {
        "message": f"成功导入 {added_chunks} 个文档片段",
        "added_chunks": added_chunks,
        "total_chunks": knowledge_base.doc_count,
    }


# 做什么：上传文件导入知识库。
# 为什么：方便把 Markdown、文本或 JSON 规则文档快速接入。
@app.post("/knowledge/upload", tags=["知识库"])
async def upload_knowledge(file: UploadFile = File(...)):
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    knowledge_base = tool.handler.__self__

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "文件大小超过 10MB 限制")

    filename = file.filename or "unknown"
    text = content.decode("utf-8", errors="ignore")
    if filename.endswith(".json"):
        try:
            documents = json.loads(text)
            if not isinstance(documents, list):
                raise HTTPException(400, "JSON 文件应为数组格式: [{title, content}, ...]")
        except json.JSONDecodeError as ex:
            raise HTTPException(400, f"JSON 解析失败: {ex}") from ex
    else:
        title = filename.rsplit(".", 1)[0] if "." in filename else filename
        documents = [{"title": title, "content": text}]

    added_chunks = knowledge_base.add_documents(documents)
    return {
        "message": f"文件 {filename} 导入成功",
        "added_chunks": added_chunks,
        "total_chunks": knowledge_base.doc_count,
    }


# 做什么：查看知识库片段总数。
# 为什么：帮助快速确认默认文档和新增文档是否已导入。
@app.get("/knowledge/stats", tags=["知识库"])
async def knowledge_stats():
    tool = _tool_manager._tools.get("knowledge_search") if _tool_manager else None
    if tool is None:
        raise HTTPException(503, "知识库未初始化")
    knowledge_base = tool.handler.__self__
    return {"total_chunks": knowledge_base.doc_count}


# 做什么：运行端到端评测。
# 为什么：验证 MallPilot 的意图识别、回答质量与回归情况。
@app.post("/eval/run")
async def run_eval(body: Optional[EvalRunInput] = None):
    if _evaluator is None:
        raise HTTPException(503, "服务未就绪")

    from evaluation.evaluator import DEFAULT_DIALOG_CASES, DEFAULT_INTENT_CASES, IntentTestCase

    if body and body.intent_cases is not None:
        intent_cases = [
            IntentTestCase(
                message=case.message,
                expected_intent=case.expected_intent,
                context=case.context,
            )
            for case in body.intent_cases
        ]
    else:
        intent_cases = DEFAULT_INTENT_CASES

    if body and body.dialog_cases is not None:
        dialog_cases = [case.model_dump(exclude_none=True) for case in body.dialog_cases]
    else:
        dialog_cases = DEFAULT_DIALOG_CASES

    report = await _evaluator.run(intent_cases=intent_cases, dialog_cases=dialog_cases)
    return {
        "pass_rate": report.pass_rate,
        "total": report.total,
        "passed": report.passed,
        "avg_scores": report.avg_scores,
        "regressions": report.regressions,
        "recommendations": report.recommendations,
        "results": [
            {
                "test_id": result.test_id,
                "passed": result.passed,
                "scores": result.scores,
                "detail": result.detail,
                "metadata": result.metadata,
            }
            for result in report.results
        ],
    }


# 做什么：构建知识库上下文。
# 为什么：规则类问题优先参考 Chroma 中的政策与说明，减少编造。
async def _build_knowledge_context(message: str, top_k: int = 3) -> Tuple[str, bool]:
    if _tool_manager is None or not _should_use_knowledge(message):
        return "", False
    try:
        result = await _tool_manager.search_with_rewrite("knowledge_search", message, top_k=top_k)
        if not result.success or not isinstance(result.data, list) or not result.data:
            return "", False

        lines = ["[知识库检索结果]"]
        used = False
        for index, item in enumerate(result.data[:top_k], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "未命名文档"))
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            used = True
            lines.append(f"{index}. 标题: {title}")
            lines.append(f"   相关度: {item.get('score', '')}")
            lines.append(f"   内容: {content[:600]}")
        if not used:
            return "", False
        lines.append("请优先依据以上规则知识回答；如果知识不足，再结合商品库、订单库和通用业务规范说明。")
        return "\n".join(lines), True
    except Exception as ex:
        logger.warning("构建知识库上下文失败: %s", ex)
        return "", False


# 做什么：构建结构化商品与订单上下文。
# 为什么：把 MySQL 中的商品和订单事实接入主对话链路。
async def _build_structured_context(message: str, user_id: str) -> str:
    if _tool_manager is None or _commerce_store is None:
        return ""

    sections: List[str] = []

    # 做什么：导购问题优先注入商品库事实。
    # 为什么：让推荐结果能被商品价格、品牌和标签约束。
    if _should_use_catalog(message):
        category = _commerce_store._extract_category(message)
        budget = _commerce_store._extract_budget(message)
        used_product = False  # 做什么：标记工具链路是否已经拿到可用商品结果；为什么：避免空结果时遗漏本地商品库兜底。
        product_result = await _tool_manager.call(
            "product_search",
            {
                "query": message,
                "category": category or "",
                "max_price": budget,
                "limit": 3,
            },
            {"user_id": user_id},
            use_cache=True,
        )
        if product_result.success and isinstance(product_result.data, list):
            product_lines = ["[商品库结果]"]
            for index, item in enumerate(product_result.data, start=1):
                if not isinstance(item, dict) or item.get("fallback"):
                    continue
                used_product = True
                product_lines.append(
                    f"{index}. {item['name']} | 类目: {item['category']} | 品牌: {item['brand']} | 价格: {item['price']} 元 | 评分: {item['rating']}"
                )
                product_lines.append(f"   标签: {item['tags']}")
                product_lines.append(f"   简介: {item['summary']}")
            if used_product:
                product_lines.append("请优先依据以上商品事实做推荐或对比，不要凭空补充不存在的参数。")
                sections.append("\n".join(product_lines))
        # 做什么：在工具结果为空时回退到本地商品库上下文构建。
        # 为什么：复用商品库已有的预算放宽与语义兜底逻辑，避免模型脱离 MySQL 事实自由发挥。
        if not used_product:
            fallback_product_context = _commerce_store.build_product_context(message)
            if fallback_product_context:
                sections.append(fallback_product_context)

    # 做什么：订单与售后问题优先注入订单库事实。
    # 为什么：物流、发票、退款状态必须基于结构化订单数据回答。
    if _should_use_order(message):
        lookup_params: Dict[str, Any] = {"user_id": user_id, "limit": 2}
        order_id = _commerce_store.extract_order_id(message)
        if order_id:
            lookup_params["order_id"] = order_id
        order_result = await _tool_manager.call("order_lookup", lookup_params, {"user_id": user_id}, use_cache=True)
        if order_result.success and isinstance(order_result.data, dict):
            order = order_result.data.get("order")
            recent_orders = order_result.data.get("recent_orders")
            if isinstance(order, dict):
                sections.append(_commerce_store._format_order_context(order))
            elif isinstance(recent_orders, list) and recent_orders:
                recent_lines = ["[最近订单摘要]"]
                for index, item in enumerate(recent_orders, start=1):
                    if not isinstance(item, dict):
                        continue
                    recent_lines.append(
                        f"{index}. 订单号: {item['order_id']} | 状态: {item['status']} | 物流: {item['shipping_status']} | 售后: {item['after_sales_status']}"
                    )
                recent_lines.append("用户没有提供明确订单号时，只能基于最近订单摘要做保守说明。")
                sections.append("\n".join(recent_lines))

    return "\n\n".join(section for section in sections if section)


# 做什么：判断是否值得查知识库。
# 为什么：寒暄和纯结构化查询不需要每次都做 RAG。
def _should_use_knowledge(message: str) -> bool:
    lowered = message.strip().lower()
    if not lowered:
        return False
    greetings = {"你好", "您好", "嗨", "hi", "hello", "hey", "在吗"}
    if lowered in greetings:
        return False
    knowledge_keywords = [
        "规则",
        "政策",
        "运费",
        "发票",
        "优惠券",
        "积分",
        "退货",
        "退款",
        "配送",
        "售后",
        "会员",
        "说明",
    ]
    return any(keyword in lowered for keyword in knowledge_keywords)


# 做什么：判断是否值得查商品库。
# 为什么：只在导购型消息里做商品检索，减少无关噪声。
def _should_use_catalog(message: str) -> bool:
    keywords = ["推荐", "对比", "哪个好", "预算", "买", "送礼", "适合", "手机", "耳机", "书桌", "吹风机", "投影"]
    return any(keyword in message for keyword in keywords)


# 做什么：判断是否值得查订单库。
# 为什么：订单、物流、售后问题需要优先绑定订单事实。
def _should_use_order(message: str) -> bool:
    keywords = ["订单", "物流", "发货", "签收", "地址", "发票", "支付", "退款", "退货", "换货", "售后", "运单", "订单号", "MP20"]
    return any(keyword in message for keyword in keywords)


# 做什么：提供一个简化 CLI 入口。
# 为什么：保留本地终端演示能力，便于快速手动验证改造结果。
async def _cli():
    print(BANNER)
    print("MallPilot CLI - 输入 quit 退出\n")

    from agents.agent_orchestrator import AgentOrchestrator, Request
    from core.commerce_store import CommerceStore
    from core.skill_loader import SkillManager
    from memory.conversation_memory import MemoryManager, MsgRole

    cfg = _anthropic_cfg()
    skill_manager = SkillManager(
        root_dir=_get_env("MALLPILOT_SKILLS_DIR", str(pathlib.Path(_ROOT) / "skills"), "ECHOMIND_SKILLS_DIR"),
        max_prompt_chars=int(_get_env("MALLPILOT_SKILLS_MAX_PROMPT_CHARS", "5000", "ECHOMIND_SKILLS_MAX_PROMPT_CHARS")),
    )
    skill_manager.load()
    orchestrator = AgentOrchestrator(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
        skill_manager=skill_manager,
    )
    memory = MemoryManager(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        chroma_host=os.getenv("CHROMA_HOST", "localhost"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "/tmp/chroma"),
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg["model"],
    )
    commerce_cfg = _commerce_cfg()
    commerce_store = CommerceStore(
        host=commerce_cfg["host"],
        port=commerce_cfg["port"],
        user=commerce_cfg["user"],
        password=commerce_cfg["password"],
        database=commerce_cfg["database"],
        seed_demo_data=True,
        charset=commerce_cfg["charset"],
        connect_timeout=commerce_cfg["connect_timeout"],
    )
    commerce_store.initialize()

    user_id = "cli_user"
    conv_id = str(uuid.uuid4())

    while True:
        try:
            message = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break

        if not message or message.lower() in {"quit", "exit", "退出"}:
            print("再见")
            break

        memory_context = await memory.get_context(user_id, conv_id, query=message)
        history = [
            {"role": item.role.value, "content": item.content}
            for item in memory_context.recent_messages[-5:]
        ] if memory_context.recent_messages else None

        context_parts = [memory_context.to_prompt_text()]
        if _should_use_catalog(message):
            context_parts.append(commerce_store.build_product_context(message))
        if _should_use_order(message):
            context_parts.append(commerce_store.build_order_context(message, user_id))

        result = await orchestrator.run(
            Request(
                message=message,
                user_id=user_id,
                conv_id=conv_id,
                context="\n\n".join(part for part in context_parts if part),
                history=history,
            )
        )

        await memory.add_message(user_id, conv_id, MsgRole.USER, message)
        await memory.add_message(user_id, conv_id, MsgRole.ASSISTANT, result.response)
        print(f"\nMallPilot [{result.agent_type.value}]: {result.response}\n")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        asyncio.run(_cli())
    else:
        uvicorn.run(
            "api.main:app",
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            reload=os.getenv("APP_ENV") == "development",
        )
