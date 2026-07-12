import json
import re
from typing import Any

from mallpilot.app.agent.schemas import IntentResult
from mallpilot.app.llm.bailian_client import BailianClient
from mallpilot.app.llm.schemas import LlmMessage


# LLM Router 允许输出的意图集合。
ALLOWED_INTENTS = {"guide", "product_qa", "cart", "order", "after_sale", "chitchat"}

# LLM Router 支持抽取的实体字段集合。
ALLOWED_ENTITY_KEYS = {"budget_max", "brand", "category", "sub_category", "preferences"}


class IntentRouter:
    # 品牌别名表，用于把用户口语品牌映射到数据集品牌名。
    BRAND_ALIASES = {
        "苹果": "Apple 苹果",
        "iphone": "Apple 苹果",
        "iPhone": "Apple 苹果",
        "华为": "华为",
        "小米": "小米",
        "oppo": "OPPO",
        "OPPO": "OPPO",
        "vivo": "vivo",
        "耐克": "耐克",
        "nike": "Nike",
        "Nike": "Nike",
        "阿迪": "阿迪达斯",
        "阿迪达斯": "阿迪达斯",
        "兰蔻": "兰蔻",
        "雅诗兰黛": "雅诗兰黛",
        "科颜氏": "科颜氏",
        "薇诺娜": "薇诺娜",
        "理肤泉": "理肤泉",
    }

    # 路由用户意图，MVP 先用规则实现，后续可替换为 LLM JSON 路由。
    def route(self, message: str) -> IntentResult:
        if any(word in message for word in ["退货", "退款", "售后", "取消订单"]):
            return IntentResult(intent="after_sale", confidence=0.9, reason="命中售后关键词", entities=self._extract_entities(message))
        if any(word in message for word in ["下单", "购买", "结算"]):
            return IntentResult(intent="order", confidence=0.85, reason="命中下单关键词", entities=self._extract_entities(message))
        if any(word in message for word in ["购物车", "加入", "加购"]):
            return IntentResult(intent="cart", confidence=0.85, reason="命中购物车关键词", entities=self._extract_entities(message))
        if any(word in message for word in ["这款", "参数", "能用吗", "怎么样"]):
            return IntentResult(intent="product_qa", confidence=0.7, reason="命中商品问答关键词", entities=self._extract_entities(message))
        if self._is_chitchat(message):
            return IntentResult(intent="chitchat", confidence=0.8, reason="命中闲聊或非购物问题", entities={})

        # 没命中强业务动作时，默认进入导购推荐流。
        return IntentResult(intent="guide", confidence=0.75, reason="默认导购推荐", entities=self._extract_entities(message))

    # 判断是否为不应触发检索的简单闲聊。
    def _is_chitchat(self, message: str) -> bool:
        normalized = re.sub(r"[\s，。！？!?,.]", "", message)
        if normalized in {"你好", "您好", "在吗", "早上好", "下午好", "晚上好", "hello", "hi"}:
            return True
        if re.fullmatch(r"\d+(\+\d+)+等于几", normalized) or re.fullmatch(r"\d+(\+\d+)+", normalized):
            return True
        return any(word in normalized for word in ["等于几", "天气", "讲个笑话", "你是谁"])

    # 抽取第一版常用实体。
    def _extract_entities(self, message: str) -> dict:
        entities: dict = {}
        budget_match = self._extract_budget(message)
        if budget_match:
            entities["budget_max"] = budget_match
        brand = self._extract_brand(message)
        if brand:
            entities["brand"] = brand
        if any(word in message for word in ["精华", "敏感肌", "保湿", "护肤"]):
            entities["category"] = "美妆护肤"
        if "手机" in message or "iPhone" in message or "iphone" in message:
            entities["category"] = "数码电子"
            entities["sub_category"] = "智能手机"
        if "平板" in message:
            entities["category"] = "数码电子"
            entities["sub_category"] = "平板电脑"
        if "笔记本" in message or "电脑" in message:
            entities["category"] = "数码电子"
            entities["sub_category"] = "笔记本电脑"
        if "耳机" in message:
            entities["category"] = "数码电子"
            entities["sub_category"] = "真无线耳机"
        if "T恤" in message or "鞋" in message:
            entities["category"] = "服饰运动"
        if "咖啡" in message or "零食" in message:
            entities["category"] = "食品生活"
        preferences = self._extract_preferences(message)
        if preferences:
            entities["preferences"] = preferences
        return entities

    # 抽取预算上限。
    def _extract_budget(self, message: str) -> int | None:
        patterns = [
            r"预算\s*(\d+)",
            r"(\d+)\s*元?以内",
            r"不超过\s*(\d+)",
            r"低于\s*(\d+)",
            r"少于\s*(\d+)",
        ]
        for pattern in patterns:
            # 命中第一个预算表达后返回整数预算。
            match = re.search(pattern, message)
            if match:
                return int(match.group(1))
        return None

    # 抽取品牌约束。
    def _extract_brand(self, message: str) -> str | None:
        for keyword, brand in self.BRAND_ALIASES.items():
            # 品牌别名命中后统一映射为数据集中的品牌字段。
            if keyword in message:
                return brand
        return None

    # 抽取使用偏好，用于检索 query 和前端解释。
    def _extract_preferences(self, message: str) -> list[str]:
        preferences: list[str] = []
        preference_keywords = {
            "拍照": "拍照",
            "影像": "拍照",
            "续航": "续航",
            "长续航": "续航",
            "游戏": "游戏",
            "轻薄": "轻薄",
            "老人": "长辈使用",
            "妈妈": "长辈使用",
            "学生": "学生使用",
            "敏感肌": "敏感肌",
            "保湿": "保湿",
            "修护": "修护",
        }
        for keyword, preference in preference_keywords.items():
            # 保持偏好去重，避免同义词重复进入 Trace。
            if keyword in message and preference not in preferences:
                preferences.append(preference)
        return preferences


class LlmIntentRouter:
    # 初始化 LLM 意图路由器。
    def __init__(
        self,
        client: BailianClient | Any | None = None,
        fallback_router: IntentRouter | None = None,
        min_confidence: float = 0.55,
    ):
        # 百炼 Chat 客户端，测试可注入 fake。
        self.client = client or BailianClient()
        # LLM 不可用或输出异常时使用的规则兜底路由器。
        self.fallback_router = fallback_router or IntentRouter()
        # LLM 结果最低置信度，低于该值时回退到规则路由。
        self.min_confidence = min_confidence

    # 使用真实 LLM 识别意图并抽取实体。
    def route(self, message: str) -> IntentResult:
        try:
            result = self._route_with_llm(message)
        except Exception:
            # LLM 调用、JSON 解析或字段校验失败时，使用规则路由保证聊天链路可用。
            return self.fallback_router.route(message)

        if result.confidence < self.min_confidence:
            # 低置信度输出不直接驱动业务 Flow，避免误触发检索或交易动作。
            return self.fallback_router.route(message)
        return result

    # 调用百炼 Chat 模型并解析结构化路由结果。
    def _route_with_llm(self, message: str) -> IntentResult:
        response = self.client.chat([
            LlmMessage(role="system", content=self._system_prompt()),
            LlmMessage(role="user", content=f"用户输入：{message}"),
        ])
        data = self._loads_json(response.content)
        return self._build_intent_result(data)

    # 构造路由模型提示词。
    def _system_prompt(self) -> str:
        return "\n".join([
            "你是 MallPilot 电商导购系统的意图路由器，只输出 JSON，不输出 Markdown。",
            "可选 intent 只有：guide, product_qa, cart, order, after_sale, chitchat。",
            "guide 表示导购推荐；product_qa 表示围绕某个商品的参数、适配或优缺点提问；cart 表示加购或购物车；order 表示下单或结算；after_sale 表示退货、退款、售后；chitchat 表示问候、闲聊、天气、简单数学或非购物问题。",
            "entities 只允许包含 budget_max, brand, category, sub_category, preferences。",
            "category 优先使用：美妆护肤、数码电子、服饰运动、食品生活。",
            "sub_category 可使用智能手机、平板电脑、笔记本电脑、真无线耳机等商品库常见子类。",
            "preferences 必须是字符串数组。",
            "输出格式：{\"intent\":\"guide\",\"confidence\":0.0,\"reason\":\"简短原因\",\"entities\":{}}",
        ])

    # 解析 LLM 输出的 JSON，兼容模型偶尔包裹代码块的情况。
    def _loads_json(self, content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            # 去掉 Markdown 代码块外壳，只保留中间 JSON 文本。
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    # 将 LLM JSON 转成内部 IntentResult。
    def _build_intent_result(self, data: dict[str, Any]) -> IntentResult:
        intent = str(data.get("intent", "")).strip()
        if intent not in ALLOWED_INTENTS:
            raise ValueError(f"unsupported intent: {intent}")

        confidence = float(data.get("confidence", 0.0))
        entities = self._sanitize_entities(data.get("entities", {}))
        reason = str(data.get("reason", "LLM 路由识别")).strip() or "LLM 路由识别"
        return IntentResult(intent=intent, confidence=confidence, reason=reason, entities=entities)

    # 清洗 LLM 抽取的实体字段，避免未知字段进入后续检索过滤。
    def _sanitize_entities(self, raw_entities: Any) -> dict[str, Any]:
        if not isinstance(raw_entities, dict):
            return {}

        entities: dict[str, Any] = {}
        for key, value in raw_entities.items():
            # 只接收后续 Flow 和检索层认识的实体字段。
            if key not in ALLOWED_ENTITY_KEYS or value in (None, "", []):
                continue
            if key == "budget_max":
                entities[key] = int(value)
            elif key == "preferences":
                entities[key] = [str(item) for item in value] if isinstance(value, list) else [str(value)]
            else:
                entities[key] = str(value)
        return entities
