import re

from mallpilot.app.agent.schemas import IntentResult


class IntentRouter:
    # 路由用户意图，MVP 先用规则实现，后续可替换为 LLM JSON 路由。
    def route(self, message: str) -> IntentResult:
        if any(word in message for word in ["退货", "退款", "售后", "取消订单"]):
            return IntentResult(intent="after_sale", confidence=0.9, reason="命中售后关键词", entities=self._extract_entities(message))
        if any(word in message for word in ["下单", "购买", "结算"]):
            return IntentResult(intent="order", confidence=0.85, reason="命中下单关键词", entities=self._extract_entities(message))
        if any(word in message for word in ["购物车", "加入", "加购"]):
            return IntentResult(intent="cart", confidence=0.85, reason="命中购物车关键词", entities=self._extract_entities(message))
        if any(word in message for word in ["这款", "参数", "能用吗", "怎么样"]):
            return IntentResult(intent="product_qa", confidence=0.7, reason="命中商品问答关键词", entities=self._extract_entities(message))

        # 没命中强业务动作时，默认进入导购推荐流。
        return IntentResult(intent="guide", confidence=0.75, reason="默认导购推荐", entities=self._extract_entities(message))

    # 抽取第一版常用实体。
    def _extract_entities(self, message: str) -> dict:
        entities: dict = {}
        budget_match = re.search(r"(\d+)\s*元?以内", message)
        if budget_match:
            entities["budget_max"] = int(budget_match.group(1))
        if any(word in message for word in ["精华", "敏感肌", "保湿", "护肤"]):
            entities["category"] = "美妆护肤"
        if "手机" in message or "iPhone" in message:
            entities["category"] = "数码电子"
        if "T恤" in message or "鞋" in message:
            entities["category"] = "服饰运动"
        if "咖啡" in message or "零食" in message:
            entities["category"] = "食品生活"
        return entities
