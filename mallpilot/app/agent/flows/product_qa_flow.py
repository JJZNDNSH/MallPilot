from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.retrieval.product_search import HybridProductSearch


class ProductQaFlow(BaseFlow):
    # 初始化商品问答 Flow。
    def __init__(self, search: HybridProductSearch):
        # 混合检索服务。
        self.search = search

    # 执行商品问答流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        candidates, _trace = self.search.search(context.message, context.entities)
        answer = "没有找到足够证据回答这个商品问题。"

        # 有证据时基于检索证据生成第一版回答。
        if candidates and candidates[0].evidence:
            evidence = candidates[0].evidence[0].get("summary", "")
            answer = f"根据商品知识，{evidence}"

        return [
            SseEvent(type="answer", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload={"text": answer}),
            SseEvent(type="final", chat_id=context.chat_id, turn_id=context.turn_id, seq=2, payload={"status": "completed"}),
        ]
