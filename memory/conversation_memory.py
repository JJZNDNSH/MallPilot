"""
亮点：多轮对话记忆管理。
三级记忆架构分别保存当前会话、跨会话片段和长期用户画像，
用于让 MallPilot 在导购、订单、售后场景中保持连续上下文。
"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import chromadb
import redis
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class MsgRole(Enum):
    """做什么：定义消息角色枚举；为什么：统一记忆读写时的角色取值。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """做什么：描述单条消息；为什么：让 Redis 与 Chroma 之间的数据结构一致。"""

    role: MsgRole  # 做什么：记录消息角色；为什么：组装上下文时需要区分用户和助手发言。
    content: str  # 做什么：记录消息文本；为什么：后续压缩、检索和画像提炼都依赖正文。
    timestamp: datetime = field(default_factory=datetime.now)  # 做什么：记录消息时间；为什么：恢复会话顺序时需要使用。
    metadata: Dict[str, Any] = field(default_factory=dict)  # 做什么：记录扩展元数据；为什么：便于保留来源和链路信息。


@dataclass
class MemoryContext:
    """做什么：承载注入 Agent 的完整记忆上下文；为什么：避免各层记忆散落在调用链中。"""

    recent_messages: List[Message]  # 做什么：保存工作记忆；为什么：维持当前会话连续性。
    relevant_history: List[str]  # 做什么：保存情景记忆片段；为什么：补充跨会话相关历史。
    user_profile: Dict[str, Any]  # 做什么：保存用户画像；为什么：支撑长期偏好和售后关注点的理解。
    summary: str  # 做什么：保存会话摘要；为什么：在长对话中压缩 token 成本。

    @staticmethod
    def _clean(text: str) -> str:
        """做什么：清理非法 Unicode 代理字符；为什么：避免 prompt 编码失败。"""
        return text.encode("utf-8", errors="ignore").decode("utf-8")

    def to_prompt_text(self) -> str:
        """做什么：把记忆上下文转成 prompt 文本；为什么：让主链路直接拼接给模型。"""
        parts: List[str] = []
        if self.summary:
            parts.append(f"[会话摘要]\n{self._clean(self.summary)}")
        if self.relevant_history:
            parts.append("[相关历史]\n" + "\n".join(f"- {self._clean(item)}" for item in self.relevant_history[:3]))
        if self.user_profile:
            parts.append(f"[用户画像]\n{json.dumps(self.user_profile, ensure_ascii=False)}")
        if self.recent_messages:
            parts.append("[最近对话]")
            for message in self.recent_messages:
                parts.append(f"{message.role.value}: {self._clean(message.content)}")
        return "\n\n".join(parts)


class MemoryManager:
    """
    做什么：统一管理三级记忆。
    为什么：让 MallPilot 在保留原项目记忆亮点的同时切换到电商导购语义。
    """

    WORKING_MAX = 20  # 做什么：限制工作记忆条数；为什么：防止单会话上下文无限膨胀。
    COMPRESS_AT = 15  # 做什么：定义压缩阈值；为什么：提前生成摘要，避免 prompt 爆炸。
    HISTORY_TOP_K = 5  # 做什么：限制历史检索条数；为什么：保留相关片段同时控制噪音。

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        chroma_path: str = "./data/chroma",
        api_key: str = "",
        base_url: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
    ):
        """做什么：初始化记忆依赖；为什么：为 Redis、Chroma 和 LLM 提炼能力建立连接。"""
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)
        self._model = model
        self._redis = redis.from_url(redis_url, decode_responses=True)

        # 做什么：优先连接独立 Chroma 服务，失败时降级到本地持久化。
        # 为什么：兼容 docker 部署和本地单机运行两种模式。
        try:
            chroma = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
            chroma.heartbeat()
            logger.info("ChromaDB 已连接: %s:%s", chroma_host, chroma_port)
        except Exception:
            logger.info("ChromaDB 服务不可用，改用本地持久化路径: %s", chroma_path)
            chroma = chromadb.PersistentClient(
                path=chroma_path,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )

        self._episodic = chroma.get_or_create_collection("episodic")
        self._profile = chroma.get_or_create_collection("user_profile")

    async def add_message(
        self,
        user_id: str,
        conv_id: str,
        role: MsgRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """做什么：写入工作记忆；为什么：让当前会话可以被后续回答直接复用。"""
        safe_user_id = self._safe_text(user_id)
        safe_conv_id = self._safe_text(conv_id)
        safe_metadata = {
            self._safe_text(key): self._safe_metadata_value(value)
            for key, value in (metadata or {}).items()
        }
        message = Message(
            role=role,
            content=self._safe_text(content),
            metadata=safe_metadata,
        )
        key = self._wm_key(safe_user_id, safe_conv_id)

        self._redis.lpush(
            key,
            json.dumps(
                {
                    "role": message.role.value,
                    "content": message.content,
                    "ts": message.timestamp.isoformat(),
                    "metadata": message.metadata,
                },
                ensure_ascii=False,
            ),
        )
        self._redis.expire(key, 86400)

        # 做什么：达到阈值后自动压缩历史消息。
        # 为什么：把长对话转换成摘要和情景记忆，节省后续上下文空间。
        if self._redis.llen(key) >= self.COMPRESS_AT:
            await self._compress(safe_user_id, safe_conv_id)

    async def update_profile(self, user_id: str, conv_id: str) -> None:
        """做什么：提炼用户画像；为什么：让导购回复能持续记住偏好与关注点。"""
        safe_user_id = self._safe_text(user_id)
        safe_conv_id = self._safe_text(conv_id)
        messages = await self._get_working_memory(safe_user_id, safe_conv_id)
        if not messages:
            return

        dialogue_text = self._safe_text("\n".join(f"{item.role.value}: {item.content}" for item in messages[-10:]))
        prompt = f"""
请从下面的 MallPilot 电商对话中提炼用户画像，只返回 JSON。

对话：
{dialogue_text}

输出要求：
1. 只保留对后续导购、订单、售后有帮助的长期信息。
2. 偏好请围绕品牌偏好、价格敏感度、类目兴趣、功能关注点、售后关注点。
3. 没有信息的字段返回空数组或空字符串，不要编造。

返回格式：
{{
  "brand_preferences": [],
  "category_interests": [],
  "price_sensitivity": "",
  "feature_focus": [],
  "after_sales_concerns": [],
  "member_status": "",
  "notes": []
}}
"""
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=512,
                temperature=0.0,
                messages=[{"role": "user", "content": self._safe_text(prompt)}],
            )
            raw = response.content[0].text
            start = raw.find("{")
            end = raw.rfind("}") + 1
            profile_data = json.loads(raw[start:end])
            document_id = f"{safe_user_id}_profile_{safe_conv_id}"
            document_text = self._safe_text(json.dumps(profile_data, ensure_ascii=False))

            try:
                self._profile.delete(ids=[document_id])
            except Exception:
                pass

            self._profile.add(
                ids=[document_id],
                documents=[document_text],
                metadatas=[
                    {
                        "user_id": safe_user_id,
                        "conv_id": safe_conv_id,
                        "ts": datetime.now().isoformat(),
                    }
                ],
            )
            logger.info("用户画像已更新: %s", safe_user_id)
        except Exception as ex:
            logger.warning("更新用户画像失败: %s", ex)

    async def get_context(self, user_id: str, conv_id: str, query: str = "") -> MemoryContext:
        """做什么：构建完整记忆上下文；为什么：供主链路一次性注入模型。"""
        safe_user_id = self._safe_text(user_id)
        safe_conv_id = self._safe_text(conv_id)
        safe_query = self._safe_text(query)

        recent_messages = await self._get_working_memory(safe_user_id, safe_conv_id)
        history_query = safe_query or (recent_messages[-1].content if recent_messages else "")
        relevant_history = await self._search_episodic(safe_user_id, history_query)
        user_profile = await self._get_profile(safe_user_id)
        summary = self._redis.get(self._summary_key(safe_user_id, safe_conv_id)) or ""

        return MemoryContext(
            recent_messages=recent_messages,
            relevant_history=relevant_history,
            user_profile=user_profile,
            summary=summary,
        )

    async def _compress(self, user_id: str, conv_id: str) -> None:
        """做什么：压缩工作记忆；为什么：把旧消息沉淀为摘要和可检索情景记忆。"""
        messages = await self._get_working_memory(user_id, conv_id)
        if len(messages) < self.COMPRESS_AT:
            return

        to_compress = messages[:-5]
        keep_messages = messages[-5:]
        text_block = self._safe_text("\n".join(f"{item.role.value}: {item.content}" for item in to_compress))
        prompt = self._safe_text(
            "请用 2-3 句话总结下面 MallPilot 电商对话中的关键事实、用户诉求和待办事项：\n" + text_block
        )

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=256,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = self._safe_text(response.content[0].text).strip()
        except Exception:
            summary = f"本段对话共 {len(to_compress)} 条消息，摘要生成失败。"

        summary_key = self._summary_key(user_id, conv_id)
        old_summary = self._redis.get(summary_key) or ""
        merged_summary = self._safe_text(f"{old_summary}\n{summary}").strip()
        self._redis.setex(summary_key, 86400, merged_summary)

        await self._store_episodic(user_id, conv_id, text_block, summary)

        # 做什么：仅保留最近 5 条消息作为新的工作记忆。
        # 为什么：保证当前对话连续性，同时让旧消息让位给摘要。
        key = self._wm_key(user_id, conv_id)
        self._redis.delete(key)
        for message in reversed(keep_messages):
            self._redis.lpush(
                key,
                json.dumps(
                    {
                        "role": message.role.value,
                        "content": message.content,
                        "ts": message.timestamp.isoformat(),
                        "metadata": message.metadata,
                    },
                    ensure_ascii=False,
                ),
            )
        self._redis.expire(key, 86400)
        logger.info("工作记忆压缩完成: %s/%s", user_id, conv_id)

    async def _get_working_memory(self, user_id: str, conv_id: str) -> List[Message]:
        """做什么：读取工作记忆；为什么：恢复当前会话最近消息序列。"""
        key = self._wm_key(user_id, conv_id)
        raw_messages = self._redis.lrange(key, 0, self.WORKING_MAX - 1)
        messages: List[Message] = []
        for raw in reversed(raw_messages):
            data = json.loads(raw)
            messages.append(
                Message(
                    role=MsgRole(data["role"]),
                    content=data["content"],
                    timestamp=datetime.fromisoformat(data["ts"]),
                    metadata=data.get("metadata", {}),
                )
            )
        return messages

    async def _search_episodic(self, user_id: str, query: str) -> List[str]:
        """做什么：检索情景记忆；为什么：补充跨会话仍然相关的历史片段。"""
        query_text = self._safe_text(query).strip()
        if not query_text:
            return []
        try:
            results = self._episodic.query(
                query_texts=[query_text],
                n_results=self.HISTORY_TOP_K,
                where={"user_id": self._safe_text(user_id)},
            )
            documents = results["documents"][0] if results.get("documents") else []
            return [self._safe_text(document) for document in documents if isinstance(document, str) and document.strip()]
        except Exception as ex:
            logger.warning("情景记忆检索失败: %s", ex)
            return []

    async def _store_episodic(self, user_id: str, conv_id: str, text: str, summary: str) -> None:
        """做什么：写入情景记忆；为什么：让旧对话可被后续语义检索命中。"""
        try:
            document_id = hashlib.md5(f"{user_id}{conv_id}{time.time()}".encode("utf-8")).hexdigest()
            self._episodic.add(
                ids=[document_id],
                documents=[self._safe_text(summary)],
                metadatas=[
                    {
                        "user_id": self._safe_text(user_id),
                        "conv_id": self._safe_text(conv_id),
                        "ts": datetime.now().isoformat(),
                        "full_text": self._safe_text(text[:500]),
                    }
                ],
            )
        except Exception as ex:
            logger.warning("写入情景记忆失败: %s", ex)

    async def _get_profile(self, user_id: str) -> Dict[str, Any]:
        """做什么：读取用户画像；为什么：让画像参与当前 prompt 构建。"""
        try:
            results = self._profile.get(where={"user_id": self._safe_text(user_id)})
            documents = results.get("documents") or []
            metadatas = results.get("metadatas") or []
            if not documents:
                return {}

            # 做什么：优先读取最新画像。
            # 为什么：同一用户可能经历多次画像更新，最新结果更贴近当前偏好。
            latest_index = 0
            latest_ts = ""
            for index, metadata in enumerate(metadatas):
                current_ts = str((metadata or {}).get("ts", ""))
                if current_ts >= latest_ts:
                    latest_index = index
                    latest_ts = current_ts
            return json.loads(documents[latest_index])
        except Exception:
            return {}

    @staticmethod
    def _wm_key(user_id: str, conv_id: str) -> str:
        """做什么：生成工作记忆键；为什么：统一 Redis 命名规则。"""
        return f"wm:{user_id}:{conv_id}"

    @staticmethod
    def _summary_key(user_id: str, conv_id: str) -> str:
        """做什么：生成摘要键；为什么：统一 Redis 命名规则。"""
        return f"summary:{user_id}:{conv_id}"

    @staticmethod
    def _safe_text(value: Any) -> str:
        """做什么：把任意值转换成安全文本；为什么：避免存储和 prompt 编码异常。"""
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.encode("utf-8", errors="ignore").decode("utf-8")

    @classmethod
    def _safe_metadata_value(cls, value: Any) -> Any:
        """做什么：递归清洗 metadata；为什么：避免 Redis 和 Chroma 写入非法字符。"""
        if isinstance(value, str):
            return cls._safe_text(value)
        if isinstance(value, dict):
            return {cls._safe_text(key): cls._safe_metadata_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._safe_metadata_value(item) for item in value]
        return value
