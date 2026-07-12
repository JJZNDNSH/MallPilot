from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.tools.after_sale_tools import preview_after_sale


class AfterSaleFlow(BaseFlow):
    # 执行模拟售后流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        # 售后必须先展示预览和确认要求，不能直接创建退货申请。
        return [SseEvent(type="after_sale_preview", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload=preview_after_sale())]
