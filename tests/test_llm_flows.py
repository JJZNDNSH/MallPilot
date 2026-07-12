from mallpilot.app.agent.flows.guide_flow import GuideFlow
from mallpilot.app.agent.flows.product_qa_flow import ProductQaFlow
from mallpilot.app.agent.schemas import ProductCandidate
from mallpilot.app.agent.state import FlowContext


class FakeSearch:
    # 返回稳定候选商品。
    def search(self, query: str, filters: dict):
        return (
            [
                ProductCandidate(
                    product_id="p_1",
                    title="保湿修护精华",
                    category="美妆护肤",
                    price=199,
                    score=0.9,
                    evidence=[{"source": "test", "summary": "适合敏感肌保湿修护"}],
                )
            ],
            [],
        )


class FakeLlmService:
    # 生成导购总结。
    def generate_guide_summary(self, message: str, candidates: list[ProductCandidate]) -> str:
        return f"模型推荐：{candidates[0].title}"

    # 生成商品问答答案。
    def answer_product_question(self, message: str, evidence: list[dict]) -> str:
        return f"模型回答：{evidence[0]['summary']}"


# 验证导购 Flow 注入 LLM 服务后会输出模型生成的总结。
def test_guide_flow_uses_llm_service_for_summary():
    flow = GuideFlow(search=FakeSearch(), llm_service=FakeLlmService())
    context = FlowContext(chat_id="chat_1", turn_id="turn_1", message="推荐保湿精华", entities={})

    events = flow.run(context)

    assert [event.type for event in events] == ["thinking", "product_card", "answer", "final"]
    assert events[2].payload["text"] == "模型推荐：保湿修护精华"


# 验证商品问答 Flow 注入 LLM 服务后会输出模型生成的答案。
def test_product_qa_flow_uses_llm_service_for_answer():
    flow = ProductQaFlow(search=FakeSearch(), llm_service=FakeLlmService())
    context = FlowContext(chat_id="chat_1", turn_id="turn_1", message="敏感肌能用吗", entities={})

    events = flow.run(context)

    assert [event.type for event in events] == ["answer", "final"]
    assert events[0].payload["text"] == "模型回答：适合敏感肌保湿修护"
