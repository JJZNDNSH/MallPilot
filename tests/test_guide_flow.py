from mallpilot.app.agent.flows.guide_flow import GuideFlow
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.retrieval.product_search import HybridProductSearch


# 验证导购 Flow 会输出进度、商品卡片和结束事件。
def test_guide_flow_emits_thinking_product_card_and_final():
    docs = [
        {"product_id": "p_1", "title": "敏感肌修护精华", "content": "敏感肌 保湿 修护", "price": 199, "category": "美妆护肤"}
    ]
    flow = GuideFlow(search=HybridProductSearch.from_documents(docs))
    context = FlowContext(
        chat_id="chat_1",
        turn_id="turn_1",
        message="帮我找300元以内适合敏感肌的精华",
        entities={"category": "美妆护肤", "budget_max": 300},
    )

    events = flow.run(context)

    assert [event.type for event in events] == ["thinking", "product_card", "final"]
    assert events[1].payload["product_id"] == "p_1"
    assert events[1].payload["actions"][1]["type"] == "add_to_cart"


# 验证商品问答 Flow 在有证据时会输出 answer 和 final。
def test_product_qa_flow_emits_answer_with_evidence():
    from mallpilot.app.agent.flows.product_qa_flow import ProductQaFlow

    docs = [
        {"product_id": "p_1", "title": "敏感肌修护精华", "content": "敏感肌使用前建议先测试", "price": 199, "category": "美妆护肤"}
    ]
    flow = ProductQaFlow(search=HybridProductSearch.from_documents(docs))
    context = FlowContext(
        chat_id="chat_1",
        turn_id="turn_1",
        message="这款精华敏感肌能用吗",
        entities={"category": "美妆护肤"},
    )

    events = flow.run(context)

    assert [event.type for event in events] == ["answer", "final"]
    assert "敏感肌" in events[0].payload["text"]
