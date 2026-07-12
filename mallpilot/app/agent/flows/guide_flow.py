from typing import Any

from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.retrieval.product_search import HybridProductSearch
from mallpilot.app.services.llm_service import LlmService
from mallpilot.app.tools.product_tools import build_product_card


class GuideFlow(BaseFlow):
    # 初始化导购 Flow。
    def __init__(self, search: HybridProductSearch | Any, llm_service: LlmService | Any | None = None):
        # 混合检索服务。
        self.search = search
        # 可选 LLM 服务，传入时用于生成导购总结。
        self.llm_service = llm_service

    # 执行导购推荐流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        events: list[SseEvent] = []
        seq = 1

        # 发送公开进度事件。
        events.append(SseEvent(
            type="thinking",
            chat_id=context.chat_id,
            turn_id=context.turn_id,
            seq=seq,
            payload={"message": "正在根据你的需求检索商品", "stage": "retrieval"},
        ))
        seq += 1

        candidates, _trace = self.search.search(context.message, context.entities)
        if not candidates:
            # 无结果时返回可恢复回答，而不是直接失败。
            events.append(SseEvent(
                type="answer",
                chat_id=context.chat_id,
                turn_id=context.turn_id,
                seq=seq,
                payload={"text": "没有找到完全满足条件的商品，可以放宽预算或减少限制。"},
            ))
            seq += 1
        else:
            # 有结果时输出商品卡片事件。
            events.append(SseEvent(
                type="product_card",
                chat_id=context.chat_id,
                turn_id=context.turn_id,
                seq=seq,
                payload=build_product_card(candidates[0]),
            ))
            seq += 1

            if self.llm_service is not None:
                # 注入 LLM 服务时，额外输出模型生成的导购总结。
                summary = self.llm_service.generate_guide_summary(context.message, candidates)
                events.append(SseEvent(
                    type="answer",
                    chat_id=context.chat_id,
                    turn_id=context.turn_id,
                    seq=seq,
                    payload={"text": summary},
                ))
                seq += 1

        events.append(SseEvent(
            type="final",
            chat_id=context.chat_id,
            turn_id=context.turn_id,
            seq=seq,
            payload={"status": "completed"},
        ))
        return events
