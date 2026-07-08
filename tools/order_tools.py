"""
MallPilot 订单工具注册模块。

这个模块负责注册面向订单 Agent 的订单、物流、发票、支付和优惠券类工具。
"""
from typing import Any, Dict, List, Optional

from core.commerce_store import CommerceStore
from mcp.tool_manager import MCPToolManager, Tool


# 做什么：注册订单类工具。
# 为什么：把订单 Agent 常用的查询能力拆到独立目录维护，并统一走工具框架。
def register_order_tools(tool_manager: MCPToolManager, commerce_store: CommerceStore) -> None:
    # 做什么：构建订单对象型工具的统一降级结果。
    # 为什么：让订单详情、物流、支付和发票工具失败时仍能返回可解释结果。
    def order_dict_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str) -> Dict[str, Any]:
        return {"fallback": True, "error": error, "message": "订单工具暂时不可用，请稍后重试或转人工核验。"}

    # 做什么：构建订单列表型工具的统一降级结果。
    # 为什么：让最近订单和订单明细工具失败时返回一致结构。
    def order_list_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str) -> List[Dict[str, Any]]:
        return [{"fallback": True, "error": error, "message": "订单工具暂时不可用，请稍后重试或转人工核验。"}]

    # 做什么：注册订单详情工具。
    # 为什么：订单详情仍是订单 Agent 的主入口能力。
    async def order_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        order_id = str(params.get("order_id", "")).strip()
        user_id = str(params.get("user_id", "")).strip() or None
        if order_id:
            order = commerce_store.lookup_order(order_id=order_id, user_id=user_id)
            return {"order": order}
        recent_orders = commerce_store.recent_orders(user_id=user_id or "", limit=int(params.get("limit", 2))) if user_id else []
        return {"recent_orders": recent_orders}

    tool_manager.register(
        Tool(
            name="order_lookup",
            description="查询 MallPilot 订单与售后数据",
            handler=order_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=60.0,
            fallback=order_dict_fallback,
        )
    )

    # 做什么：注册最近订单工具。
    # 为什么：用户没有提供订单号时，订单 Agent 需要最近订单做上下文。
    async def recent_orders_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        user_id = str(params.get("user_id", "")).strip()
        status = str(params.get("status", "")).strip() or None
        if not user_id:
            return []
        return commerce_store.list_user_orders(user_id=user_id, status=status, limit=int(params.get("limit", 5)))

    tool_manager.register(
        Tool(
            name="recent_orders",
            description="查询某个用户最近的订单列表",
            handler=recent_orders_handler,
            schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "status": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["user_id"],
            },
            cache_ttl=45.0,
            fallback=order_list_fallback,
        )
    )

    # 做什么：注册订单时间线工具。
    # 为什么：物流和履约追踪经常需要完整时间线而不是单一状态。
    async def order_timeline_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        timeline = commerce_store.get_order_timeline(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )
        return timeline or {}

    tool_manager.register(
        Tool(
            name="order_timeline",
            description="查询订单履约时间线",
            handler=order_timeline_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=30.0,
            fallback=order_dict_fallback,
        )
    )

    # 做什么：注册物流查询工具。
    # 为什么：订单和投诉场景都需要更细粒度的物流快照。
    async def logistics_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        logistics = commerce_store.get_logistics_snapshot(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )
        return logistics or {}

    tool_manager.register(
        Tool(
            name="logistics_lookup",
            description="查询订单物流状态与轨迹",
            handler=logistics_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=20.0,
            fallback=order_dict_fallback,
        )
    )

    # 做什么：注册支付查询工具。
    # 为什么：支付状态、支付方式和实付金额常常需要单独回答。
    async def payment_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payment = commerce_store.get_payment_snapshot(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )
        return payment or {}

    tool_manager.register(
        Tool(
            name="payment_lookup",
            description="查询订单支付状态和支付方式",
            handler=payment_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=60.0,
            fallback=order_dict_fallback,
        )
    )

    # 做什么：注册发票查询工具。
    # 为什么：发票问题常常只需要发票抬头和支付事实，不必加载完整订单。
    async def invoice_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        invoice = commerce_store.get_invoice_snapshot(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )
        return invoice or {}

    tool_manager.register(
        Tool(
            name="invoice_lookup",
            description="查询订单发票相关信息",
            handler=invoice_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=120.0,
            fallback=order_dict_fallback,
        )
    )

    # 做什么：注册订单明细工具。
    # 为什么：订单 Agent 在核对商品、规格和数量时只需要明细列表。
    async def order_items_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.get_order_items(
            order_id=str(params.get("order_id", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
        )

    tool_manager.register(
        Tool(
            name="order_items_lookup",
            description="查询订单商品明细",
            handler=order_items_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                "required": ["order_id"],
            },
            cache_ttl=60.0,
            fallback=order_list_fallback,
        )
    )

    # 做什么：注册优惠券查询工具。
    # 为什么：订单 Agent 在核对优惠时需要知道某张券的使用情况。
    async def coupon_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return commerce_store.lookup_coupon_usage(
            coupon_code=str(params.get("coupon_code", "")).strip(),
            user_id=str(params.get("user_id", "")).strip() or None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="coupon_lookup",
            description="查询优惠券使用情况",
            handler=coupon_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "coupon_code": {"type": "string"},
                    "user_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["coupon_code"],
            },
            cache_ttl=90.0,
            fallback=order_dict_fallback,
        )
    )
