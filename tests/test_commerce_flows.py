from mallpilot.app.agent.flows.after_sale_flow import AfterSaleFlow
from mallpilot.app.agent.flows.cart_flow import CartFlow
from mallpilot.app.agent.flows.order_flow import OrderFlow
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.tools.cart_tools import CartStore


# 验证商品不明确时，购物车 Flow 会追问用户补充商品。
def test_cart_flow_emits_clarification_when_product_missing():
    flow = CartFlow(cart_store=CartStore())
    context = FlowContext(chat_id="chat_1", turn_id="turn_1", message="加入购物车")

    events = flow.run(context)

    assert events[0].type == "clarification"
    assert "product_id" in events[0].payload["required_slots"]


# 验证下单 Flow 必须先输出订单预览。
def test_order_flow_emits_order_preview():
    flow = OrderFlow()
    context = FlowContext(chat_id="chat_1", turn_id="turn_1", message="下单")

    events = flow.run(context)

    assert events[0].type == "order_preview"
    assert events[0].payload["requires_confirmation"] is True


# 验证售后 Flow 必须先输出售后预览。
def test_after_sale_flow_emits_after_sale_preview():
    flow = AfterSaleFlow()
    context = FlowContext(chat_id="chat_1", turn_id="turn_1", message="我要退货")

    events = flow.run(context)

    assert events[0].type == "after_sale_preview"
    assert events[0].payload["requires_confirmation"] is True
