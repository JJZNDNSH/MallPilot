from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.tools.order_tools import preview_order


class OrderFlow(BaseFlow):
    # 执行模拟下单流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        # 下单必须先给用户订单预览，不能直接创建订单。
        return [SseEvent(type="order_preview", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload=preview_order())]
