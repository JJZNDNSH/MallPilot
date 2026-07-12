from typing import Any

from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.retrieval.product_search import HybridProductSearch
from mallpilot.app.services.llm_service import LlmService


class ProductQaFlow(BaseFlow):
    # 初始化商品问答 Flow。
    def __init__(self, search: HybridProductSearch | Any, llm_service: LlmService | Any | None = None):
        # 混合检索服务。
        self.search = search
        # 可选 LLM 服务，传入时用于基于证据生成答案。
        self.llm_service = llm_service

    # 执行商品问答流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        candidates, _trace = self.search.search(context.message, context.entities)
        answer = "没有找到足够证据回答这个商品问题。"

        if candidates and candidates[0].evidence:
            if self.llm_service is not None:
                # 注入 LLM 服务时，使用模型基于证据生成回答。
                answer = self.llm_service.answer_product_question(context.message, candidates[0].evidence)
            else:
                # 未注入 LLM 服务时保持第一阶段的轻量回答。
                evidence = candidates[0].evidence[0].get("summary", "")
                answer = f"根据商品知识：{evidence}"

        return [
            SseEvent(type="answer", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload={"text": answer}),
            SseEvent(type="final", chat_id=context.chat_id, turn_id=context.turn_id, seq=2, payload={"status": "completed"}),
        ]
