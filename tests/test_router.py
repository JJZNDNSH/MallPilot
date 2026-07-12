from mallpilot.app.agent.router import IntentRouter, LlmIntentRouter
from mallpilot.app.llm.schemas import LlmResult


class FakeRouterClient:
    # 初始化 fake LLM 路由客户端。
    def __init__(self, content: str):
        # fake LLM 返回文本。
        self.content = content
        # 已收到的 Chat 消息。
        self.messages = []

    # 模拟百炼 Chat 返回。
    def chat(self, messages):
        self.messages = messages
        return LlmResult(content=self.content, model="fake-router")


# 验证导购需求会被路由到 guide，并抽取预算和品类。
def test_router_detects_guide_intent():
    router = IntentRouter()
    result = router.route("帮我找300元以内适合敏感肌的精华")

    assert result.intent == "guide"
    assert result.entities["budget_max"] == 300
    assert result.entities["category"] == "美妆护肤"


# 验证售后请求不会进入导购流，而是路由到 after_sale。
def test_router_detects_after_sale_intent():
    router = IntentRouter()
    result = router.route("我要退货，订单号是123")

    assert result.intent == "after_sale"


# 验证简单问候不会进入导购检索流。
def test_router_detects_chitchat_intent():
    router = IntentRouter()
    result = router.route("你好")

    assert result.intent == "chitchat"
    assert result.entities == {}


# 验证导购约束会抽取品牌、子品类和使用偏好。
def test_router_extracts_brand_sub_category_and_preferences():
    router = IntentRouter()
    result = router.route("预算3000以内，想买苹果手机，拍照好续航强")

    assert result.intent == "guide"
    assert result.entities["budget_max"] == 3000
    assert result.entities["brand"] == "Apple 苹果"
    assert result.entities["category"] == "数码电子"
    assert result.entities["sub_category"] == "智能手机"
    assert result.entities["preferences"] == ["拍照", "续航"]


# 验证 LLM Router 会解析模型返回的结构化 JSON。
def test_llm_router_uses_model_json_for_guide_intent():
    router = LlmIntentRouter(client=FakeRouterClient(
        '{"intent":"guide","confidence":0.92,"reason":"用户在找手机","entities":{"budget_max":3000,"brand":"Apple 苹果","category":"数码电子","sub_category":"智能手机","preferences":["拍照","续航"]}}'
    ))

    result = router.route("预算3000以内，想买苹果手机，拍照好续航强")

    assert result.intent == "guide"
    assert result.confidence == 0.92
    assert result.entities["budget_max"] == 3000
    assert result.entities["brand"] == "Apple 苹果"
    assert result.entities["preferences"] == ["拍照", "续航"]


# 验证 LLM Router 能把非购物数学问题识别为闲聊。
def test_llm_router_detects_math_as_chitchat():
    router = LlmIntentRouter(client=FakeRouterClient(
        '{"intent":"chitchat","confidence":0.96,"reason":"简单数学问题","entities":{}}'
    ))

    result = router.route("1+1等于几")

    assert result.intent == "chitchat"
    assert result.entities == {}


# 验证 LLM 输出异常时会回退到规则路由。
def test_llm_router_falls_back_to_rule_router_on_bad_json():
    router = LlmIntentRouter(client=FakeRouterClient("不是 JSON"))

    result = router.route("帮我找300元以内适合敏感肌的精华")

    assert result.intent == "guide"
    assert result.entities["budget_max"] == 300
    assert result.entities["category"] == "美妆护肤"
