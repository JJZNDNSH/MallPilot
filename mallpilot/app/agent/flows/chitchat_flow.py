from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext


class ChitchatFlow(BaseFlow):
    # 执行闲聊 Flow。
    def run(self, context: FlowContext) -> list[SseEvent]:
        # 闲聊只返回引导话术，不触发商品检索。
        return [
            SseEvent(
                type="answer",
                chat_id=context.chat_id,
                turn_id=context.turn_id,
                seq=1,
                payload={"text": "你好，我是 MallPilot。你可以告诉我预算、品类或使用场景，我来帮你筛选商品。"},
            ),
            SseEvent(
                type="final",
                chat_id=context.chat_id,
                turn_id=context.turn_id,
                seq=2,
                payload={"status": "completed"},
            ),
        ]
