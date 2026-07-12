from uuid import uuid4


# 生成模拟售后预览。
def preview_after_sale() -> dict:
    return {"policy": "MVP 模拟售后，真实规则后续接入。", "requires_confirmation": True}


# 创建模拟售后申请。
def create_mock_return_request() -> dict:
    return {"return_id": f"ret_{uuid4().hex}", "status": "submitted"}
