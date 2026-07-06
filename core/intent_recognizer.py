"""
MallPilot 三路融合意图识别模块。

这个模块保留 LLM、Embedding 与关键词三路识别亮点，但把业务语义切换为导购、订单、售后场景。
"""
import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class IntentCategory(Enum):
    """MallPilot 领域意图。"""

    GUIDE = "guide"  # 商品推荐、参数对比、预算建议等导购场景。
    ORDER = "order"  # 订单、物流、支付、地址、发票等订单场景。
    AFTER_SALES = "after_sales"  # 退款、退货、换货、售后进度等售后场景。
    COMPLAINT = "complaint"  # 强烈不满或投诉表达。
    GREETING = "greeting"  # 问候语。
    ESCALATION = "escalation"  # 明确要求人工、专员或紧急升级。
    FEEDBACK = "feedback"  # 正向反馈。
    OTHER = "other"  # 低置信度或未命中场景。


class UrgencyLevel(Enum):
    """请求紧急度。"""

    LOW = 1  # 低紧急度。
    MEDIUM = 2  # 中紧急度。
    HIGH = 3  # 高紧急度。
    CRITICAL = 4  # 极高紧急度。


@dataclass
class IntentResult:
    """意图识别结果。"""

    intent: IntentCategory  # 本轮识别出的主意图。
    confidence: float  # 识别置信度。
    urgency: UrgencyLevel  # 本轮识别出的紧急度。
    entities: Dict[str, List[str]]  # 从消息中提取的结构化实体。
    reasoning: str  # LLM 给出的简短判断理由。
    latency_ms: float  # 本轮识别总耗时。


_TEMPLATES: Dict[IntentCategory, List[str]] = {
    IntentCategory.GUIDE: [
        "预算 3000 元想买续航好的手机",
        "帮我对比一下两款蓝牙耳机",
        "送女生礼物有什么推荐",
    ],
    IntentCategory.ORDER: [
        "订单 MP20260706001 到哪了",
        "这单什么时候发货",
        "我想补开发票",
    ],
    IntentCategory.AFTER_SALES: [
        "这笔订单想退货",
        "收到商品有瑕疵怎么换货",
        "退款怎么还没到账",
    ],
    IntentCategory.COMPLAINT: [
        "你们处理也太慢了",
        "售后服务太差了",
        "我非常不满意",
    ],
    IntentCategory.GREETING: [
        "你好",
        "在吗",
        "嗨，帮我看看",
    ],
    IntentCategory.ESCALATION: [
        "我要转人工",
        "现在立刻找专员",
        "我要投诉并升级处理",
    ],
    IntentCategory.FEEDBACK: [
        "推荐很准",
        "这次体验不错",
        "谢谢，回答很有帮助",
    ],
}

_URGENCY_KEYWORDS = {
    UrgencyLevel.CRITICAL: ["立刻", "马上", "紧急", "urgent", "asap", "今天必须"],
    UrgencyLevel.HIGH: ["尽快", "催一下", "来不及", "马上要", "今天要用"],
    UrgencyLevel.MEDIUM: ["这周", "早点", "帮我看看"],
}


# 做什么：计算余弦相似度。
# 为什么：在无远端 Embedding 时仍能完成轻量语义匹配。
def _cosine(left: List[float], right: List[float]) -> float:
    dot = sum(lv * rv for lv, rv in zip(left, right))
    left_norm = sum(item * item for item in left) ** 0.5
    right_norm = sum(item * item for item in right) ** 0.5
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


class IntentRecognizer:
    """MallPilot 端到端意图识别器。"""

    # 做什么：初始化模型客户端、阈值和模板缓存。
    # 为什么：为三路融合提供统一的状态管理。
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        confidence_threshold: float = 0.5,
    ):
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncAnthropic(**kwargs)
        self.model = model
        self.threshold = confidence_threshold
        self._embedding_enabled = not bool(base_url)
        self._tpl_embeddings: Dict[IntentCategory, List[List[float]]] = {}
        self._cache: Dict[str, IntentResult] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    # 做什么：执行一次完整意图识别。
    # 为什么：统一组合 LLM、Embedding、关键词与实体提取结果。
    async def recognize(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        cache_key = self._cache_key(message)
        if cache_key in self._cache:
            self.cache_hits += 1
            return self._cache[cache_key]
        self.cache_misses += 1

        t0 = time.monotonic()

        # 做什么：并行启动 LLM 与 Embedding 识别。
        # 为什么：降低整体识别耗时，同时保留多路融合效果。
        llm_task = asyncio.create_task(self._llm_recognize(message, history))
        emb_task = asyncio.create_task(self._embedding_recognize(message)) if self._embedding_enabled else None
        pattern_result = self._pattern_recognize(message)

        if emb_task is not None:
            llm_result, emb_result = await asyncio.gather(llm_task, emb_task)
        else:
            llm_result = await llm_task
            emb_result = {"intent": IntentCategory.OTHER, "confidence": 0.0}

        intent = self._vote(llm_result, emb_result, pattern_result)
        entities = await self._extract_entities(message)
        urgency = self._urgency(message, intent)

        result = IntentResult(
            intent=intent,
            confidence=float(llm_result.get("confidence", 0.0)),
            urgency=urgency,
            entities=entities,
            reasoning=str(llm_result.get("reasoning", "")),
            latency_ms=(time.monotonic() - t0) * 1000,
        )

        # 做什么：做简单 LRU 风格缓存。
        # 为什么：连续多轮对话里，相同句子经常会重复出现。
        if len(self._cache) >= 1000:
            for key in list(self._cache)[:500]:
                del self._cache[key]
        self._cache[cache_key] = result
        return result

    # 做什么：在线补充模板样本。
    # 为什么：为后续手工纠偏或回放学习保留入口。
    def learn(self, message: str, correct: IntentCategory) -> None:
        templates = _TEMPLATES.setdefault(correct, [])
        if message not in templates:
            templates.append(message)
            self._tpl_embeddings.pop(correct, None)
            logger.info("学习新样本 -> %s: %s", correct.value, message[:40])

    # 做什么：用 LLM 识别主意图。
    # 为什么：LLM 对复杂导购、订单、售后混合语义最敏感。
    async def _llm_recognize(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]],
    ) -> Dict[str, Any]:
        clean_message = self._clean_text(message)
        examples = "\n".join(
            f'  消息: "{sample}" -> 意图: {intent.value}'
            for intent, samples in _TEMPLATES.items()
            for sample in samples[:1]
        )

        context_block = ""
        if history:
            context_block = "\n最近对话:\n" + "\n".join(
                f"  {self._clean_text(item.get('role', 'user'))}: {self._clean_text(item.get('content', ''))}"
                for item in history[-3:]
            )

        prompt = f"""你是 MallPilot 的意图识别专家。请结合示例与上下文判断用户当前最主要的业务意图。

示例:
{examples}

{context_block}
用户消息: "{clean_message}"

请只返回 JSON:
{{"intent": "<意图值>", "confidence": <0-1>, "reasoning": "<一句话理由>"}}

可选意图: {", ".join(intent.value for intent in IntentCategory)}"""
        prompt = self._clean_text(prompt)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=256,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            start, end = raw.find("{"), raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            # 做什么：对 LLM 返回的意图值做安全转换。
            # 为什么：避免模型输出未知字符串时直接抛出 ValueError 中断主链路。
            try:
                data["intent"] = IntentCategory(data.get("intent", IntentCategory.OTHER.value))
            except ValueError:
                data["intent"] = IntentCategory.OTHER
            data["confidence"] = float(data.get("confidence", 0.0))
            return data
        except Exception as ex:
            logger.warning("LLM 识别失败: %s", ex)
            return {
                "intent": IntentCategory.OTHER,
                "confidence": 0.0,
                "reasoning": "LLM 识别失败",
                "failed": True,
            }

    # 做什么：用 Embedding 识别近似意图。
    # 为什么：在高频表达上给 LLM 一个低成本语义投票补充。
    async def _embedding_recognize(self, message: str) -> Dict[str, Any]:
        try:
            await self._load_template_embeddings()
            message_vector = await self._embed_text(message)

            best_intent = IntentCategory.OTHER
            best_score = 0.0
            for intent, vectors in self._tpl_embeddings.items():
                score = max(_cosine(message_vector, vector) for vector in vectors)
                if score > best_score:
                    best_intent = intent
                    best_score = score
            return {"intent": best_intent, "confidence": best_score}
        except Exception as ex:
            logger.warning("Embedding 识别失败: %s", ex)
            return {"intent": IntentCategory.OTHER, "confidence": 0.0}

    # 做什么：用关键词快速兜底分类。
    # 为什么：让明显的导购、订单、售后表达零延迟命中。
    def _pattern_recognize(self, message: str) -> Dict[str, Any]:
        lowered = message.lower()
        patterns = {
            IntentCategory.ESCALATION: ["转人工", "专员", "人工", "经理", "升级"],
            IntentCategory.COMPLAINT: ["不满意", "太差", "投诉", "糟糕", "慢死了"],
            IntentCategory.GUIDE: ["推荐", "对比", "哪个好", "预算", "送礼", "适合", "买什么"],
            IntentCategory.ORDER: ["订单", "物流", "发货", "签收", "地址", "发票", "支付", "优惠券"],
            IntentCategory.AFTER_SALES: ["退款", "退货", "换货", "售后", "瑕疵", "破损", "没到账"],
            IntentCategory.GREETING: ["你好", "您好", "在吗", "hello", "hi"],
            IntentCategory.FEEDBACK: ["不错", "谢谢", "很准", "满意", "有帮助"],
        }

        best_intent = IntentCategory.OTHER
        best_score = 0.0
        for intent, keywords in patterns.items():
            hits = sum(1 for keyword in keywords if keyword in lowered)
            if hits:
                score = hits / len(keywords)
                if score > best_score:
                    best_intent = intent
                    best_score = score
        return {"intent": best_intent, "confidence": best_score}

    # 做什么：融合三路识别结果。
    # 为什么：避免单一路径误判，把表达强度和语义强度都纳入计算。
    def _vote(self, llm_result: Dict[str, Any], emb_result: Dict[str, Any], pattern_result: Dict[str, Any]) -> IntentCategory:
        if llm_result.get("failed"):
            if emb_result.get("confidence", 0.0) > 0:
                return emb_result["intent"]
            if pattern_result.get("confidence", 0.0) > 0:
                return pattern_result["intent"]
            return IntentCategory.OTHER

        weights = [(llm_result, 0.7), (emb_result, 0.2), (pattern_result, 0.1)] if self._embedding_enabled else [
            (llm_result, 0.85),
            (pattern_result, 0.15),
        ]

        scores: Dict[IntentCategory, float] = {}
        for result, weight in weights:
            intent = result.get("intent", IntentCategory.OTHER)
            confidence = float(result.get("confidence", 0.0))
            scores[intent] = scores.get(intent, 0.0) + weight * confidence

        best_intent = max(scores, key=scores.get)
        return best_intent if scores[best_intent] >= self.threshold else IntentCategory.OTHER

    # 做什么：提取导购与订单场景常用实体。
    # 为什么：为数据库查询和后续画像更新保留可结构化的字段。
    async def _extract_entities(self, message: str) -> Dict[str, List[str]]:
        clean_message = self._clean_text(message)
        prompt = f"""从 MallPilot 用户消息中提取结构化实体，只返回 JSON。
消息: "{clean_message}"
格式: {{"product":[],"category":[],"budget":[],"sku":[],"order_id":[],"coupon":[],"address":[]}}"""
        prompt = self._clean_text(prompt)
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=256,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            start, end = raw.find("{"), raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            return {
                "product": [str(item) for item in data.get("product", [])],
                "category": [str(item) for item in data.get("category", [])],
                "budget": [str(item) for item in data.get("budget", [])],
                "sku": [str(item) for item in data.get("sku", [])],
                "order_id": [str(item) for item in data.get("order_id", [])],
                "coupon": [str(item) for item in data.get("coupon", [])],
                "address": [str(item) for item in data.get("address", [])],
            }
        except Exception:
            order_id_match = re.findall(r"(MP\d{8,})", clean_message.upper())
            budget_match = re.findall(r"(\d{2,5}\s*元)", clean_message)
            return {
                "product": [],
                "category": [],
                "budget": budget_match,
                "sku": [],
                "order_id": order_id_match,
                "coupon": [],
                "address": [],
            }

    # 做什么：懒加载模板向量。
    # 为什么：避免启动阶段额外阻塞，同时复用模板缓存。
    async def _load_template_embeddings(self) -> None:
        missing = [intent for intent in _TEMPLATES if intent not in self._tpl_embeddings]
        if not missing:
            return

        all_texts = [sample for intent in missing for sample in _TEMPLATES[intent]]
        vectors = [await self._embed_text(text) for text in all_texts]

        index = 0
        for intent in missing:
            sample_count = len(_TEMPLATES[intent])
            self._tpl_embeddings[intent] = vectors[index:index + sample_count]
            index += sample_count

    # 做什么：生成文本向量。
    # 为什么：优先使用远端 Embedding，缺失时自动降级到本地哈希向量。
    async def _embed_text(self, text: str) -> List[float]:
        embeddings = getattr(self.client, "embeddings", None)
        if embeddings is not None:
            try:
                response = await embeddings.create(model="voyage-3-lite", input=[text])
                return list(response.data[0].embedding)
            except Exception as ex:
                logger.warning("远端 Embedding 失败，使用本地向量兜底: %s", ex)
        return self._local_embedding(text)

    # 做什么：构造稳定的字符 n-gram 哈希向量。
    # 为什么：在没有远端 Embedding 时仍保留基础语义近似能力。
    @staticmethod
    def _local_embedding(text: str, dims: int = 256) -> List[float]:
        normalized = text.lower().strip()
        vector = [0.0] * dims
        tokens = set()
        for ngram_size in (1, 2, 3):
            if len(normalized) >= ngram_size:
                tokens.update(normalized[index:index + ngram_size] for index in range(len(normalized) - ngram_size + 1))
        if not tokens:
            tokens.add(normalized)

        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return vector

    # 做什么：判断消息紧急度。
    # 为什么：售后催单、强投诉和人工升级场景需要更高优先级。
    def _urgency(self, message: str, intent: IntentCategory) -> UrgencyLevel:
        lowered = message.lower()
        for level, keywords in _URGENCY_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return level
        if intent == IntentCategory.ESCALATION:
            return UrgencyLevel.HIGH
        if intent in (IntentCategory.COMPLAINT, IntentCategory.AFTER_SALES):
            return UrgencyLevel.MEDIUM
        return UrgencyLevel.LOW

    # 做什么：构造缓存键。
    # 为什么：降低重复消息在多轮对话中的重复识别成本。
    def _cache_key(self, message: str) -> str:
        return self._clean_text(message)[:200]

    # 做什么：清洗字符串中的非法代理字符。
    # 为什么：避免 HTTP 客户端在编码 prompt 时崩溃。
    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.encode("utf-8", errors="ignore").decode("utf-8")

    # 做什么：返回当前缓存统计。
    # 为什么：便于评测或调试识别链路是否命中缓存。
    @property
    def cache_stats(self) -> Dict[str, Any]:
        total = self.cache_hits + self.cache_misses
        return {
            "size": len(self._cache),
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate": self.cache_hits / total if total else 0.0,
        }
