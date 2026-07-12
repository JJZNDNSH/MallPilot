from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.tools.cart_tools import CartStore


class CartFlow(BaseFlow):
    # 初始化购物车 Flow。
    def __init__(self, cart_store: CartStore):
        # 购物车存储。
        self.cart_store = cart_store

    # 执行购物车流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        product_id = context.entities.get("product_id")
        if not product_id:
            # 商品不明确时，前端展示 clarification 组件等待用户补充。
            return [SseEvent(
                type="clarification",
                chat_id=context.chat_id,
                turn_id=context.turn_id,
                seq=1,
                payload={"question": "你想把哪个商品加入购物车？", "required_slots": ["product_id"], "suggestions": []},
            )]

        item = self.cart_store.add_to_cart(product_id, context.entities.get("sku_id"), int(context.entities.get("quantity", 1)))
        return [SseEvent(type="cart_update", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload=item)]
