from mallpilot.app.agent.router import IntentRouter


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
