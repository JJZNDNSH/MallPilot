from mallpilot.app.agent.schemas import ProductCandidate
from mallpilot.app.llm.bailian_client import BailianClient
from mallpilot.app.llm.schemas import LlmMessage


class LlmService:
    # 初始化 LLM 应用服务。
    def __init__(self, client: BailianClient | None = None):
        # 百炼客户端，测试可注入 fake。
        self.client = client or BailianClient()

    # 生成导购总结。
    def generate_guide_summary(self, message: str, candidates: list[ProductCandidate]) -> str:
        product_lines = [
            f"- {candidate.title}，价格 {candidate.price}，证据：{candidate.evidence[0].get('summary', '') if candidate.evidence else ''}"
            for candidate in candidates[:3]
        ]
        prompt = "\n".join([
            "你是 MallPilot 导购助手，请基于候选商品给出简短、可信的推荐总结。",
            f"用户需求：{message}",
            "候选商品：",
            *product_lines,
        ])
        result = self.client.chat([
            LlmMessage(role="system", content="你是专业、克制、可靠的电商导购助手。"),
            LlmMessage(role="user", content=prompt),
        ])
        return result.content

    # 生成商品问答答案。
    def answer_product_question(self, message: str, evidence: list[dict]) -> str:
        evidence_lines = [f"- {item.get('summary', '')}" for item in evidence[:5]]
        prompt = "\n".join([
            "请只基于证据回答用户的商品问题；证据不足时说明需要更多信息。",
            f"用户问题：{message}",
            "证据：",
            *evidence_lines,
        ])
        result = self.client.chat([
            LlmMessage(role="system", content="你是严谨的商品问答助手。"),
            LlmMessage(role="user", content=prompt),
        ])
        return result.content
