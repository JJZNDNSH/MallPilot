from uuid import uuid4


# 生成模拟订单预览。
def preview_order() -> dict:
    return {"items": [], "total_amount": 0, "requires_confirmation": True}


# 创建模拟订单。
def create_mock_order() -> dict:
    return {"order_id": f"ord_{uuid4().hex}", "status": "created"}
