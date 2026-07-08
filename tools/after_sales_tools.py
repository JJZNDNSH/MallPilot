"""
MallPilot 售后工具注册模块。

这个模块负责注册面向售后 Agent 的退款、换货、投诉和政策类工具。
"""
from typing import Any, Dict, List, Optional

from core.commerce_store import CommerceStore
from mcp.tool_manager import MCPToolManager, Tool


# 做什么：注册售后类工具。
# 为什么：把退款、退货、换货、投诉和政策工具拆到独立目录维护。
def register_after_sales_tools(tool_manager: MCPToolManager, commerce_store: CommerceStore) -> None:
    # 做什么：构建售后对象型工具的统一降级结果。
    # 为什么：让退款、资格判断和政策查询失败时仍返回可解释结果。
    def after_sales_dict_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str) -> Dict[str, Any]:
        return {"fallback": True, "error": error, "message": "售后工具暂时不可用，请稍后重试或转人工核验。"}

    # 做什么：构建售后列表型工具的统一降级结果。
    # 为什么：让投诉列表和售后历史工具失败时返回一致结构。
    def after_sales_list_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str) -> List[Dict[str, Any]]:
        return [{"fallback": True, "error": error, "message": "售后工具暂时不可用，请稍后重试或转人工核验。"}]

    # 做什么：注册售后工单查询工具。
    # 为什么：售后工单仍然是退款、换货和投诉类咨询的主入口事实源。
    async def after_sales_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        ticket = commerce_store.get_after_sales_ticket(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )
        return ticket or {}

    tool_manager.register(
        Tool(
            name="after_sales_lookup",
            description="查询订单对应的售后工单",
            handler=after_sales_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=45.0,
            fallback=after_sales_dict_fallback,
        )
    )

    # 做什么：注册退款状态工具。
    # 为什么：退款问题通常只关心退款进度和当前售后状态。
    async def refund_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        refund = commerce_store.get_refund_status(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )
        return refund or {}

    tool_manager.register(
        Tool(
            name="refund_lookup",
            description="查询退款状态和售后进度",
            handler=refund_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=30.0,
            fallback=after_sales_dict_fallback,
        )
    )

    # 做什么：注册退货资格校验工具。
    # 为什么：售后 Agent 需要先判断用户是否处于退货政策窗口内。
    async def return_eligibility_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return commerce_store.evaluate_return_eligibility(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )

    tool_manager.register(
        Tool(
            name="return_eligibility_check",
            description="校验订单是否符合退货条件",
            handler=return_eligibility_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=30.0,
            fallback=after_sales_dict_fallback,
        )
    )

    # 做什么：注册换货资格校验工具。
    # 为什么：换货申请同样需要基于真实签收时间和当前售后状态判断。
    async def exchange_eligibility_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return commerce_store.evaluate_exchange_eligibility(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )

    tool_manager.register(
        Tool(
            name="exchange_eligibility_check",
            description="校验订单是否符合换货条件",
            handler=exchange_eligibility_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=30.0,
            fallback=after_sales_dict_fallback,
        )
    )

    # 做什么：注册售后政策查询工具。
    # 为什么：当用户问的是规则本身而不是单个订单进度时，需要返回可核验的政策文本。
    async def service_policy_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.lookup_service_policies(
            policy_type=str(params.get("policy_type", "")).strip() or None,
            keyword=str(params.get("keyword", "")),
            category=str(params.get("category", "")).strip() or None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="service_policy_lookup",
            description="查询退货、换货、退款和投诉政策",
            handler=service_policy_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "policy_type": {"type": "string"},
                    "keyword": {"type": "string"},
                    "category": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=300.0,
            fallback=after_sales_list_fallback,
        )
    )

    # 做什么：注册投诉查询工具。
    # 为什么：投诉与升级场景需要直接引用投诉工单，而不是只引用订单状态。
    async def complaint_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.get_complaint_summary(
            order_id=str(params.get("order_id", "")).strip() or None,
            user_id=str(params.get("user_id", "")).strip() or None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="complaint_lookup",
            description="查询投诉工单和升级记录",
            handler=complaint_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=45.0,
            fallback=after_sales_list_fallback,
        )
    )

    # 做什么：注册售后历史工具。
    # 为什么：让售后 Agent 能查看某个用户最近的售后记录，辅助判断当前问题背景。
    async def after_sales_history_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        user_id = str(params.get("user_id", "")).strip()
        ticket_type = str(params.get("ticket_type", "")).strip() or None
        if not user_id:
            return []
        return commerce_store.list_after_sales_tickets(
            user_id=user_id,
            limit=int(params.get("limit", 5)),
            ticket_type=ticket_type,
        )

    tool_manager.register(
        Tool(
            name="after_sales_history",
            description="查询用户最近的售后工单历史",
            handler=after_sales_history_handler,
            schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "ticket_type": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["user_id"],
            },
            cache_ttl=45.0,
            fallback=after_sales_list_fallback,
        )
    )
