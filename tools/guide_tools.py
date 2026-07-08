"""
MallPilot 导购工具注册模块。

这个模块负责注册面向导购 Agent 的商品、库存、活动和比价类工具。
"""
from typing import Any, Dict, List, Optional

from core.commerce_store import CommerceStore
from mcp.tool_manager import MCPToolManager, Tool


# 做什么：注册导购类工具。
# 为什么：把导购 Agent 常用的搜索、详情、对比、活动和送礼能力拆到独立目录维护。
def register_guide_tools(tool_manager: MCPToolManager, commerce_store: CommerceStore) -> None:
    # 做什么：构建导购列表型工具的统一降级结果。
    # 为什么：让商品搜索、推荐和活动查询失败时返回一致且可解释的结果。
    def guide_list_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str) -> List[Dict[str, Any]]:
        return [{"fallback": True, "error": error, "message": "导购工具暂时不可用，请稍后重试。"}]

    # 做什么：构建导购对象型工具的统一降级结果。
    # 为什么：让商品详情、库存和对比工具失败时也能给主链路明确反馈。
    def guide_dict_fallback(params: Dict[str, Any], context: Optional[Dict[str, Any]], error: str) -> Dict[str, Any]:
        return {"fallback": True, "error": error, "message": "导购工具暂时不可用，请稍后重试。"}

    # 做什么：注册商品搜索工具。
    # 为什么：搜索仍然是导购 Agent 最核心的商品召回入口。
    async def product_search_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.search_products(
            query=str(params.get("query", "")),
            category=str(params.get("category", "")).strip() or None,
            min_price=float(params["min_price"]) if params.get("min_price") is not None else None,
            max_price=float(params["max_price"]) if params.get("max_price") is not None else None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="product_search",
            description="搜索 MallPilot 商品库",
            handler=product_search_handler,
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=180.0,
            fallback=guide_list_fallback,
        )
    )

    # 做什么：注册商品推荐工具。
    # 为什么：让导购 Agent 在预算和模糊诉求场景下复用结构化推荐逻辑。
    async def product_recommendation_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.recommend_products(
            query=str(params.get("query", "")),
            category=str(params.get("category", "")).strip() or None,
            budget=float(params["budget"]) if params.get("budget") is not None else None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="product_recommendation",
            description="根据预算和关键词推荐商品",
            handler=product_recommendation_handler,
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "budget": {"type": "number"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=120.0,
            fallback=guide_list_fallback,
        )
    )

    # 做什么：注册商品详情工具。
    # 为什么：导购 Agent 在追问规格、品牌和卖点时需要单品详情。
    async def product_detail_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        product = commerce_store.get_product_detail(str(params.get("product_id", "")).strip())
        return product or {}

    tool_manager.register(
        Tool(
            name="product_detail",
            description="查询商品详情、规格和活动",
            handler=product_detail_handler,
            schema={
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                },
                "required": ["product_id"],
            },
            cache_ttl=300.0,
            fallback=guide_dict_fallback,
        )
    )

    # 做什么：注册商品对比工具。
    # 为什么：多商品对比是导购 Agent 的高频能力。
    async def product_compare_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        product_ids = [str(item).strip() for item in params.get("product_ids", []) if str(item).strip()]
        return commerce_store.compare_products(product_ids)

    tool_manager.register(
        Tool(
            name="product_compare",
            description="对比多款商品的价格、评分和规格",
            handler=product_compare_handler,
            schema={
                "type": "object",
                "properties": {
                    "product_ids": {"type": "array"},
                },
                "required": ["product_ids"],
            },
            cache_ttl=180.0,
            fallback=guide_list_fallback,
        )
    )

    # 做什么：注册库存查询工具。
    # 为什么：导购 Agent 在“有没有货”“哪款更容易买到”场景下需要库存事实。
    async def inventory_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        product_ids = [str(item).strip() for item in params.get("product_ids", []) if str(item).strip()]
        return commerce_store.get_inventory_snapshot(product_ids)

    tool_manager.register(
        Tool(
            name="inventory_lookup",
            description="查询商品库存快照",
            handler=inventory_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "product_ids": {"type": "array"},
                },
                "required": ["product_ids"],
            },
            cache_ttl=30.0,
            fallback=guide_list_fallback,
        )
    )

    # 做什么：注册类目热销工具。
    # 为什么：缺少明确搜索词时，导购 Agent 需要类目级热门候选做兜底。
    async def category_hot_products_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.list_category_hot_products(
            category=str(params.get("category", "")).strip() or None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="category_hot_products",
            description="查询某个类目的热销商品",
            handler=category_hot_products_handler,
            schema={
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=180.0,
            fallback=guide_list_fallback,
        )
    )

    # 做什么：注册价格带搜索工具。
    # 为什么：预算区间是导购类咨询里最常见的硬约束之一。
    async def price_band_search_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.search_price_band_products(
            query=str(params.get("query", "")),
            category=str(params.get("category", "")).strip() or None,
            min_price=float(params["min_price"]) if params.get("min_price") is not None else None,
            max_price=float(params["max_price"]) if params.get("max_price") is not None else None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="price_band_search",
            description="按价格带筛选商品",
            handler=price_band_search_handler,
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=120.0,
            fallback=guide_list_fallback,
        )
    )

    # 做什么：注册活动查询工具。
    # 为什么：导购 Agent 在报价和推荐时往往需要同步说明当前活动与券码。
    async def promotion_lookup_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.list_active_promotions(
            category=str(params.get("category", "")).strip() or None,
            product_id=str(params.get("product_id", "")).strip() or None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="promotion_lookup",
            description="查询当前可用促销活动和券码",
            handler=promotion_lookup_handler,
            schema={
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "product_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=60.0,
            fallback=guide_list_fallback,
        )
    )

    # 做什么：注册送礼推荐工具。
    # 为什么：礼物场景常常没有明确商品名，需要独立的候选生成逻辑。
    async def gift_recommendation_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return commerce_store.recommend_gifts(
            query=str(params.get("query", "")),
            recipient=str(params.get("recipient", "")),
            category=str(params.get("category", "")).strip() or None,
            budget=float(params["budget"]) if params.get("budget") is not None else None,
            limit=int(params.get("limit", 5)),
        )

    tool_manager.register(
        Tool(
            name="gift_recommendation",
            description="为送礼场景推荐商品",
            handler=gift_recommendation_handler,
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "recipient": {"type": "string"},
                    "category": {"type": "string"},
                    "budget": {"type": "number"},
                    "limit": {"type": "integer"},
                },
            },
            cache_ttl=120.0,
            fallback=guide_list_fallback,
        )
    )
