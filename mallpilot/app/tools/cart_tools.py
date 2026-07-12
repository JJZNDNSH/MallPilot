from uuid import uuid4


class CartStore:
    # 初始化内存购物车。
    def __init__(self):
        # 购物车项列表。
        self.items: list[dict] = []

    # 加入购物车。
    def add_to_cart(self, product_id: str, sku_id: str | None, quantity: int) -> dict:
        item = {
            "cart_item_id": f"ci_{uuid4().hex}",
            "product_id": product_id,
            "sku_id": sku_id,
            "quantity": quantity,
            "status": "added",
        }
        self.items.append(item)
        return item
