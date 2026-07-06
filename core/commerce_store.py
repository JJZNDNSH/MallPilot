"""
MallPilot 结构化业务数据层。

这个模块负责管理商品与订单的 SQLite 数据，并为导购、订单、售后场景提供可复用的查询能力。
"""
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# 做什么：提供综合电商演示商品数据。
# 为什么：让导购 Agent 有稳定的结构化推荐依据。
DEMO_PRODUCTS: List[Dict[str, Any]] = [
    {
        "product_id": "P1001",
        "name": "星航 Air 轻薄笔记本 14",
        "category": "数码",
        "brand": "MallPilot Select",
        "price": 4999.0,
        "original_price": 5699.0,
        "stock": 42,
        "rating": 4.8,
        "sales_count": 1860,
        "tags": "轻薄办公,长续航,学生党",
        "summary": "14 英寸轻薄本，适合日常办公、上网课和出差携带。",
        "specs_json": json.dumps({"cpu": "i5", "memory": "16GB", "storage": "512GB SSD"}, ensure_ascii=False),
        "is_featured": 1,
    },
    {
        "product_id": "P1002",
        "name": "云鲸 Pro 降噪蓝牙耳机",
        "category": "数码",
        "brand": "云鲸",
        "price": 699.0,
        "original_price": 899.0,
        "stock": 88,
        "rating": 4.7,
        "sales_count": 3650,
        "tags": "主动降噪,通勤,音乐",
        "summary": "支持主动降噪和通透模式，适合通勤、运动和移动办公。",
        "specs_json": json.dumps({"battery": "30h", "noise_canceling": True, "weight": "4.5g"}, ensure_ascii=False),
        "is_featured": 1,
    },
    {
        "product_id": "P1003",
        "name": "极光 Max 拍照手机",
        "category": "数码",
        "brand": "极光",
        "price": 3299.0,
        "original_price": 3699.0,
        "stock": 56,
        "rating": 4.6,
        "sales_count": 2980,
        "tags": "拍照,续航,学生党",
        "summary": "主打夜景拍照和大电池，适合日常拍摄与轻度游戏。",
        "specs_json": json.dumps({"screen": "6.67英寸", "camera": "5000万像素", "battery": "5200mAh"}, ensure_ascii=False),
        "is_featured": 1,
    },
    {
        "product_id": "P1004",
        "name": "木语极简书桌",
        "category": "家居",
        "brand": "木语",
        "price": 899.0,
        "original_price": 1199.0,
        "stock": 19,
        "rating": 4.8,
        "sales_count": 730,
        "tags": "家居,收纳,极简",
        "summary": "适合小户型家庭和居家办公，配有隐藏式收纳抽屉。",
        "specs_json": json.dumps({"material": "E0级板材", "size": "120x60cm", "color": "原木色"}, ensure_ascii=False),
        "is_featured": 0,
    },
    {
        "product_id": "P1005",
        "name": "晴川 恒温电热水壶",
        "category": "小家电",
        "brand": "晴川",
        "price": 239.0,
        "original_price": 299.0,
        "stock": 120,
        "rating": 4.9,
        "sales_count": 5400,
        "tags": "恒温,母婴,家用",
        "summary": "支持多档恒温，适合泡茶、冲奶和日常家用。",
        "specs_json": json.dumps({"capacity": "1.7L", "temperature_levels": 5, "material": "304不锈钢"}, ensure_ascii=False),
        "is_featured": 1,
    },
    {
        "product_id": "P1006",
        "name": "青禾 柔雾吹风机",
        "category": "个护",
        "brand": "青禾",
        "price": 399.0,
        "original_price": 499.0,
        "stock": 67,
        "rating": 4.7,
        "sales_count": 2130,
        "tags": "护发,低噪,旅行",
        "summary": "轻量机身搭配负离子护发，适合日常快干和旅行携带。",
        "specs_json": json.dumps({"power": "1600W", "noise": "低噪", "weight": "410g"}, ensure_ascii=False),
        "is_featured": 0,
    },
    {
        "product_id": "P1007",
        "name": "山野 便携咖啡机",
        "category": "小家电",
        "brand": "山野",
        "price": 599.0,
        "original_price": 699.0,
        "stock": 25,
        "rating": 4.5,
        "sales_count": 920,
        "tags": "咖啡,便携,露营",
        "summary": "便携萃取设计，适合办公室、露营和自驾场景。",
        "specs_json": json.dumps({"pressure": "18bar", "battery": "可充电", "weight": "680g"}, ensure_ascii=False),
        "is_featured": 0,
    },
    {
        "product_id": "P1008",
        "name": "沐光 香氛洗衣凝珠",
        "category": "日用",
        "brand": "沐光",
        "price": 79.0,
        "original_price": 99.0,
        "stock": 240,
        "rating": 4.8,
        "sales_count": 8120,
        "tags": "家清,香氛,囤货",
        "summary": "一颗解决清洁与留香，适合家庭日常囤货。",
        "specs_json": json.dumps({"count": "52颗", "fragrance": "白茶", "suitable_for": "机洗"}, ensure_ascii=False),
        "is_featured": 1,
    },
    {
        "product_id": "P1009",
        "name": "岚影 智能投影仪",
        "category": "数码",
        "brand": "岚影",
        "price": 2599.0,
        "original_price": 2999.0,
        "stock": 33,
        "rating": 4.6,
        "sales_count": 1180,
        "tags": "投影,家庭影院,卧室",
        "summary": "支持自动对焦和侧投校正，适合卧室观影与租房党。",
        "specs_json": json.dumps({"brightness": "800CVIA", "resolution": "1080P", "speaker": "双扬声器"}, ensure_ascii=False),
        "is_featured": 1,
    },
    {
        "product_id": "P1010",
        "name": "知夏 亲肤四件套",
        "category": "家居",
        "brand": "知夏",
        "price": 269.0,
        "original_price": 329.0,
        "stock": 72,
        "rating": 4.7,
        "sales_count": 2560,
        "tags": "家纺,透气,四季通用",
        "summary": "亲肤柔软，适合宿舍、出租房和家庭卧室使用。",
        "specs_json": json.dumps({"material": "磨毛棉", "size": "1.5m", "season": "四季"}, ensure_ascii=False),
        "is_featured": 0,
    },
    {
        "product_id": "P1011",
        "name": "野橙 氨基酸洁面慕斯",
        "category": "个护",
        "brand": "野橙",
        "price": 89.0,
        "original_price": 109.0,
        "stock": 134,
        "rating": 4.8,
        "sales_count": 4870,
        "tags": "敏感肌,洁面,温和",
        "summary": "温和洁净不过度拔干，适合晨间清洁和敏感肌用户。",
        "specs_json": json.dumps({"volume": "160ml", "skin_type": "敏感肌", "foam": "绵密"}, ensure_ascii=False),
        "is_featured": 0,
    },
    {
        "product_id": "P1012",
        "name": "晨屿 折叠露营椅",
        "category": "家居",
        "brand": "晨屿",
        "price": 159.0,
        "original_price": 199.0,
        "stock": 51,
        "rating": 4.6,
        "sales_count": 1390,
        "tags": "露营,折叠,户外",
        "summary": "可折叠便携设计，适合阳台休闲、露营和自驾出行。",
        "specs_json": json.dumps({"load": "120kg", "material": "铝合金", "weight": "2.3kg"}, ensure_ascii=False),
        "is_featured": 0,
    },
]


# 做什么：提供综合电商演示订单数据。
# 为什么：让订单与售后 Agent 能演示真实的订单查询和售后上下文。
DEMO_ORDERS: List[Dict[str, Any]] = [
    {
        "order_id": "MP20260706001",
        "user_id": "anonymous",
        "status": "运输中",
        "total_amount": 3299.0,
        "payment_amount": 3099.0,
        "payment_method": "支付宝",
        "shipping_status": "运输中",
        "shipping_company": "顺丰速运",
        "tracking_no": "SF1029384756",
        "created_at": "2026-07-02 10:12:00",
        "paid_at": "2026-07-02 10:15:00",
        "shipped_at": "2026-07-03 08:20:00",
        "delivered_at": "",
        "coupon_code": "JULY200",
        "address_summary": "上海市浦东新区锦绣路 88 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1003", "product_name_snapshot": "极光 Max 拍照手机", "sku_snapshot": "星夜黑 12+256G", "quantity": 1, "unit_price": 3299.0},
        ],
    },
    {
        "order_id": "MP20260706002",
        "user_id": "anonymous",
        "status": "已支付",
        "total_amount": 898.0,
        "payment_amount": 898.0,
        "payment_method": "微信支付",
        "shipping_status": "待发货",
        "shipping_company": "",
        "tracking_no": "",
        "created_at": "2026-07-05 21:09:00",
        "paid_at": "2026-07-05 21:10:00",
        "shipped_at": "",
        "delivered_at": "",
        "coupon_code": "",
        "address_summary": "上海市静安区延平路 23 号",
        "invoice_title": "上海晨风科技有限公司",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1004", "product_name_snapshot": "木语极简书桌", "sku_snapshot": "原木色", "quantity": 1, "unit_price": 899.0},
        ],
    },
    {
        "order_id": "MP20260706003",
        "user_id": "anonymous",
        "status": "已签收",
        "total_amount": 239.0,
        "payment_amount": 239.0,
        "payment_method": "银行卡",
        "shipping_status": "已签收",
        "shipping_company": "京东物流",
        "tracking_no": "JD5566778899",
        "created_at": "2026-06-28 09:42:00",
        "paid_at": "2026-06-28 09:44:00",
        "shipped_at": "2026-06-29 13:00:00",
        "delivered_at": "2026-06-30 17:45:00",
        "coupon_code": "",
        "address_summary": "上海市虹口区东大名路 127 号",
        "invoice_title": "个人",
        "after_sales_status": "退款中",
        "items": [
            {"product_id": "P1005", "product_name_snapshot": "晴川 恒温电热水壶", "sku_snapshot": "奶油白", "quantity": 1, "unit_price": 239.0},
        ],
    },
    {
        "order_id": "MP20260706004",
        "user_id": "eval_user",
        "status": "运输中",
        "total_amount": 699.0,
        "payment_amount": 649.0,
        "payment_method": "微信支付",
        "shipping_status": "运输中",
        "shipping_company": "中通快递",
        "tracking_no": "ZT6677889900",
        "created_at": "2026-07-03 12:33:00",
        "paid_at": "2026-07-03 12:34:00",
        "shipped_at": "2026-07-04 09:10:00",
        "delivered_at": "",
        "coupon_code": "NEW50",
        "address_summary": "北京市朝阳区酒仙桥北路 10 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1002", "product_name_snapshot": "云鲸 Pro 降噪蓝牙耳机", "sku_snapshot": "月光白", "quantity": 1, "unit_price": 699.0},
        ],
    },
    {
        "order_id": "MP20260706005",
        "user_id": "eval_user",
        "status": "已签收",
        "total_amount": 399.0,
        "payment_amount": 399.0,
        "payment_method": "支付宝",
        "shipping_status": "已签收",
        "shipping_company": "圆通速递",
        "tracking_no": "YT7788990011",
        "created_at": "2026-06-25 18:23:00",
        "paid_at": "2026-06-25 18:25:00",
        "shipped_at": "2026-06-26 14:01:00",
        "delivered_at": "2026-06-27 16:30:00",
        "coupon_code": "",
        "address_summary": "杭州市西湖区古墩路 108 号",
        "invoice_title": "个人",
        "after_sales_status": "换货中",
        "items": [
            {"product_id": "P1006", "product_name_snapshot": "青禾 柔雾吹风机", "sku_snapshot": "薄荷绿", "quantity": 1, "unit_price": 399.0},
        ],
    },
    {
        "order_id": "MP20260706006",
        "user_id": "cli_user",
        "status": "待支付",
        "total_amount": 159.0,
        "payment_amount": 0.0,
        "payment_method": "未支付",
        "shipping_status": "未发货",
        "shipping_company": "",
        "tracking_no": "",
        "created_at": "2026-07-06 08:15:00",
        "paid_at": "",
        "shipped_at": "",
        "delivered_at": "",
        "coupon_code": "",
        "address_summary": "深圳市南山区科苑路 18 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1012", "product_name_snapshot": "晨屿 折叠露营椅", "sku_snapshot": "卡其色", "quantity": 1, "unit_price": 159.0},
        ],
    },
    {
        "order_id": "MP20260706007",
        "user_id": "guest_buyer",
        "status": "已发货",
        "total_amount": 599.0,
        "payment_amount": 569.0,
        "payment_method": "支付宝",
        "shipping_status": "已发货",
        "shipping_company": "顺丰速运",
        "tracking_no": "SF6655443322",
        "created_at": "2026-07-01 16:18:00",
        "paid_at": "2026-07-01 16:20:00",
        "shipped_at": "2026-07-02 10:00:00",
        "delivered_at": "",
        "coupon_code": "COFFEE30",
        "address_summary": "广州市天河区体育东路 36 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1007", "product_name_snapshot": "山野 便携咖啡机", "sku_snapshot": "深空灰", "quantity": 1, "unit_price": 599.0},
        ],
    },
    {
        "order_id": "MP20260706008",
        "user_id": "guest_buyer",
        "status": "已完成",
        "total_amount": 348.0,
        "payment_amount": 318.0,
        "payment_method": "微信支付",
        "shipping_status": "已签收",
        "shipping_company": "韵达快递",
        "tracking_no": "YD1122334455",
        "created_at": "2026-06-20 13:20:00",
        "paid_at": "2026-06-20 13:21:00",
        "shipped_at": "2026-06-21 10:40:00",
        "delivered_at": "2026-06-23 19:00:00",
        "coupon_code": "HOME30",
        "address_summary": "成都市高新区天府大道 66 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1010", "product_name_snapshot": "知夏 亲肤四件套", "sku_snapshot": "雾灰 1.5m", "quantity": 1, "unit_price": 269.0},
            {"product_id": "P1008", "product_name_snapshot": "沐光 香氛洗衣凝珠", "sku_snapshot": "白茶 52颗", "quantity": 1, "unit_price": 79.0},
        ],
    },
    {
        "order_id": "MP20260706009",
        "user_id": "gift_user",
        "status": "已支付",
        "total_amount": 2599.0,
        "payment_amount": 2499.0,
        "payment_method": "银行卡",
        "shipping_status": "待发货",
        "shipping_company": "",
        "tracking_no": "",
        "created_at": "2026-07-04 11:03:00",
        "paid_at": "2026-07-04 11:05:00",
        "shipped_at": "",
        "delivered_at": "",
        "coupon_code": "PROJ100",
        "address_summary": "武汉市武昌区中北路 17 号",
        "invoice_title": "武汉礼物有限公司",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1009", "product_name_snapshot": "岚影 智能投影仪", "sku_snapshot": "标准版", "quantity": 1, "unit_price": 2599.0},
        ],
    },
    {
        "order_id": "MP20260706010",
        "user_id": "vip_user",
        "status": "退款完成",
        "total_amount": 89.0,
        "payment_amount": 89.0,
        "payment_method": "微信支付",
        "shipping_status": "已签收",
        "shipping_company": "申通快递",
        "tracking_no": "ST0099887766",
        "created_at": "2026-06-15 20:08:00",
        "paid_at": "2026-06-15 20:09:00",
        "shipped_at": "2026-06-16 12:00:00",
        "delivered_at": "2026-06-17 15:00:00",
        "coupon_code": "",
        "address_summary": "南京市建邺区江东中路 89 号",
        "invoice_title": "个人",
        "after_sales_status": "退款完成",
        "items": [
            {"product_id": "P1011", "product_name_snapshot": "野橙 氨基酸洁面慕斯", "sku_snapshot": "160ml", "quantity": 1, "unit_price": 89.0},
        ],
    },
    {
        "order_id": "MP20260706011",
        "user_id": "vip_user",
        "status": "已完成",
        "total_amount": 4999.0,
        "payment_amount": 4699.0,
        "payment_method": "银行卡",
        "shipping_status": "已签收",
        "shipping_company": "京东物流",
        "tracking_no": "JD2233445566",
        "created_at": "2026-06-10 09:50:00",
        "paid_at": "2026-06-10 09:52:00",
        "shipped_at": "2026-06-11 11:15:00",
        "delivered_at": "2026-06-13 18:12:00",
        "coupon_code": "VIP300",
        "address_summary": "苏州市工业园区金鸡湖大道 18 号",
        "invoice_title": "苏州启航教育有限公司",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1001", "product_name_snapshot": "星航 Air 轻薄笔记本 14", "sku_snapshot": "银色 16GB+512GB", "quantity": 1, "unit_price": 4999.0},
        ],
    },
]


class CommerceStore:
    """MallPilot 商品与订单数据访问层。"""

    # 做什么：初始化数据库路径与演示数据开关。
    # 为什么：统一管理 SQLite 文件位置，并支持启动时自动灌入演示数据。
    def __init__(self, db_path: str, seed_demo_data: bool = True):
        self.db_path = str(Path(db_path).expanduser().resolve())  # 数据库文件路径。
        self.seed_demo_data = seed_demo_data  # 是否自动写入演示数据。

    # 做什么：初始化数据库并补齐演示数据。
    # 为什么：保证 API、工具与评测在首次启动时就能工作。
    def initialize(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            self._create_tables(conn)
            if self.seed_demo_data:
                self._seed_demo_data(conn)

    # 做什么：搜索商品。
    # 为什么：为导购咨询、商品搜索接口和工具调用提供统一结果。
    def search_products(
        self,
        query: str = "",
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        sql = [
            "SELECT product_id, name, category, brand, price, original_price, stock, rating, sales_count, tags, summary, specs_json, is_featured",
            "FROM products",
            "WHERE 1 = 1",
        ]
        params: List[Any] = []

        # 做什么：按关键词匹配商品名称、品牌、标签和简介。
        # 为什么：导购问题通常是自然语言，不能只靠精确字段查询。
        if query.strip():
            search_terms = self._extract_search_terms(query)
            if search_terms:
                # 做什么：为每个搜索词追加一组模糊匹配条件。
                # 为什么：让“预算 3000 想买续航好的手机”这类自然语言也能命中商品库。
                for term in search_terms:
                    like_value = f"%{term}%"
                    sql.append(
                        "AND (name LIKE ? OR brand LIKE ? OR category LIKE ? OR tags LIKE ? OR summary LIKE ?)"
                    )
                    params.extend([like_value, like_value, like_value, like_value, like_value])
            else:
                like_value = f"%{query.strip()}%"
                sql.append(
                    "AND (name LIKE ? OR brand LIKE ? OR category LIKE ? OR tags LIKE ? OR summary LIKE ?)"
                )
                params.extend([like_value, like_value, like_value, like_value, like_value])

        # 做什么：按类目过滤商品。
        # 为什么：缩小候选集，避免不同类目干扰推荐。
        if category:
            sql.append("AND category = ?")
            params.append(category)

        # 做什么：按价格下限过滤。
        # 为什么：让预算型推荐更贴近用户期望。
        if min_price is not None:
            sql.append("AND price >= ?")
            params.append(min_price)

        # 做什么：按价格上限过滤。
        # 为什么：让预算型推荐更贴近用户期望。
        if max_price is not None:
            sql.append("AND price <= ?")
            params.append(max_price)

        sql.append("ORDER BY is_featured DESC, rating DESC, sales_count DESC, price ASC")
        sql.append("LIMIT ?")
        params.append(max(1, min(limit, 20)))

        with self._connect() as conn:
            rows = conn.execute("\n".join(sql), params).fetchall()
        return [self._row_to_product(row) for row in rows]

    # 做什么：按订单号查询订单详情。
    # 为什么：为订单咨询、售后咨询和订单查询接口提供结构化结果。
    def lookup_order(self, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT order_id, user_id, status, total_amount, payment_amount, payment_method,
                       shipping_status, shipping_company, tracking_no, created_at, paid_at,
                       shipped_at, delivered_at, coupon_code, address_summary, invoice_title,
                       after_sales_status
                FROM orders
                WHERE order_id = ?
                """,
                (order_id,),
            ).fetchone()
            if row is None:
                return None
            if user_id and row["user_id"] != user_id:
                return None
            item_rows = conn.execute(
                """
                SELECT product_id, product_name_snapshot, sku_snapshot, quantity, unit_price
                FROM order_items
                WHERE order_id = ?
                ORDER BY rowid ASC
                """,
                (order_id,),
            ).fetchall()
        return self._row_to_order(row, item_rows)

    # 做什么：查询某个用户最近的订单摘要。
    # 为什么：用户没给订单号时，仍然可以给订单或售后 Agent 一个轻量上下文。
    def recent_orders(self, user_id: str, limit: int = 2) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT order_id, user_id, status, total_amount, payment_amount, payment_method,
                       shipping_status, shipping_company, tracking_no, created_at, paid_at,
                       shipped_at, delivered_at, coupon_code, address_summary, invoice_title,
                       after_sales_status
                FROM orders
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, max(1, min(limit, 5))),
            ).fetchall()
        return [self._row_to_order(row, []) for row in rows]

    # 做什么：构建商品上下文文本。
    # 为什么：把结构化商品结果变成 Agent 可直接消费的 prompt 片段。
    def build_product_context(self, message: str, limit: int = 3) -> str:
        budget = self._extract_budget(message)
        category = self._extract_category(message)
        search_terms = self._extract_search_terms(message)
        products = self.search_products(
            query=message.strip(),
            category=category,
            max_price=budget,
            limit=limit,
        )
        # 做什么：先在保留商品语义的前提下放宽预算约束。
        # 为什么：当用户预算略低于现有商品价格时，仍然应该优先返回相关类目的候选，而不是跑题商品。
        if not products and search_terms:
            products = self.search_products(
                query=" ".join(search_terms),
                category=category,
                max_price=None,
                limit=limit,
            )

        # 做什么：仅在没有明确商品语义时退回到类目和预算检索。
        # 为什么：避免把“想买手机”误兜底成其他数码商品。
        if not products and not search_terms and (category or budget is not None):
            products = self.search_products(
                query="",
                category=category,
                max_price=budget,
                limit=limit,
            )
        if not products:
            return ""

        lines = ["[商品库结果]"]
        for index, product in enumerate(products, start=1):
            lines.append(
                f"{index}. {product['name']} | 类目: {product['category']} | 品牌: {product['brand']} | "
                f"价格: {product['price']} 元 | 评分: {product['rating']}"
            )
            lines.append(f"   标签: {product['tags']}")
            lines.append(f"   简介: {product['summary']}")
        lines.append("请优先基于以上商品库结果做导购推荐、对比或预算建议。")
        return "\n".join(lines)

    # 做什么：构建订单上下文文本。
    # 为什么：把订单状态、物流和售后信息拼成 Agent 可直接引用的事实。
    def build_order_context(self, message: str, user_id: str) -> str:
        order_id = self.extract_order_id(message)
        if order_id:
            order = self.lookup_order(order_id=order_id, user_id=user_id or None) or self.lookup_order(order_id=order_id)
            if order is None:
                return ""
            return self._format_order_context(order)

        recent_orders = self.recent_orders(user_id=user_id, limit=2) if user_id else []
        if not recent_orders:
            return ""

        lines = ["[最近订单摘要]"]
        for index, order in enumerate(recent_orders, start=1):
            lines.append(
                f"{index}. 订单号: {order['order_id']} | 状态: {order['status']} | 物流: {order['shipping_status']} | "
                f"售后: {order['after_sales_status']}"
            )
        lines.append("用户没有明确提供订单号时，只能参考最近订单摘要，不能臆造具体处理结果。")
        return "\n".join(lines)

    # 做什么：统计当前商品数和订单数。
    # 为什么：让健康检查和调试接口能快速确认演示数据是否已初始化。
    def stats(self) -> Dict[str, int]:
        with self._connect() as conn:
            product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            item_count = conn.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
        return {
            "products": int(product_count),
            "orders": int(order_count),
            "order_items": int(item_count),
        }

    # 做什么：从自然语言中提取订单号。
    # 为什么：让对话链路无需额外参数也能命中订单查询。
    @staticmethod
    def extract_order_id(message: str) -> str:
        matched = re.search(r"(MP\d{8,})", message.upper())
        return matched.group(1) if matched else ""

    # 做什么：建立 SQLite 连接。
    # 为什么：统一 Row 工厂，减少后续结果转换代码。
    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    # 做什么：创建商品、订单和订单明细表。
    # 为什么：把导购、订单、售后演示数据拆成清晰的结构化模型。
    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                brand TEXT NOT NULL,
                price REAL NOT NULL,
                original_price REAL NOT NULL,
                stock INTEGER NOT NULL,
                rating REAL NOT NULL,
                sales_count INTEGER NOT NULL,
                tags TEXT NOT NULL,
                summary TEXT NOT NULL,
                specs_json TEXT NOT NULL,
                is_featured INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                total_amount REAL NOT NULL,
                payment_amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                shipping_status TEXT NOT NULL,
                shipping_company TEXT NOT NULL,
                tracking_no TEXT NOT NULL,
                created_at TEXT NOT NULL,
                paid_at TEXT NOT NULL,
                shipped_at TEXT NOT NULL,
                delivered_at TEXT NOT NULL,
                coupon_code TEXT NOT NULL,
                address_summary TEXT NOT NULL,
                invoice_title TEXT NOT NULL,
                after_sales_status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_items (
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name_snapshot TEXT NOT NULL,
                sku_snapshot TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                PRIMARY KEY (order_id, product_id, sku_snapshot)
            );
            """
        )
        conn.commit()

    # 做什么：幂等写入演示数据。
    # 为什么：让多次启动不会重复插入，同时保证测试与演示数据稳定可查。
    def _seed_demo_data(self, conn: sqlite3.Connection) -> None:
        conn.executemany(
            """
            INSERT OR REPLACE INTO products (
                product_id, name, category, brand, price, original_price, stock,
                rating, sales_count, tags, summary, specs_json, is_featured
            ) VALUES (
                :product_id, :name, :category, :brand, :price, :original_price, :stock,
                :rating, :sales_count, :tags, :summary, :specs_json, :is_featured
            )
            """,
            DEMO_PRODUCTS,
        )

        order_rows = [{key: value for key, value in order.items() if key != "items"} for order in DEMO_ORDERS]
        item_rows = [
            {
                "order_id": order["order_id"],
                "product_id": item["product_id"],
                "product_name_snapshot": item["product_name_snapshot"],
                "sku_snapshot": item["sku_snapshot"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
            }
            for order in DEMO_ORDERS
            for item in order["items"]
        ]

        conn.executemany(
            """
            INSERT OR REPLACE INTO orders (
                order_id, user_id, status, total_amount, payment_amount, payment_method,
                shipping_status, shipping_company, tracking_no, created_at, paid_at,
                shipped_at, delivered_at, coupon_code, address_summary, invoice_title,
                after_sales_status
            ) VALUES (
                :order_id, :user_id, :status, :total_amount, :payment_amount, :payment_method,
                :shipping_status, :shipping_company, :tracking_no, :created_at, :paid_at,
                :shipped_at, :delivered_at, :coupon_code, :address_summary, :invoice_title,
                :after_sales_status
            )
            """,
            order_rows,
        )

        conn.executemany(
            """
            INSERT OR REPLACE INTO order_items (
                order_id, product_id, product_name_snapshot, sku_snapshot, quantity, unit_price
            ) VALUES (
                :order_id, :product_id, :product_name_snapshot, :sku_snapshot, :quantity, :unit_price
            )
            """,
            item_rows,
        )
        conn.commit()

    # 做什么：把 SQLite 行对象转换成商品字典。
    # 为什么：避免 API 层直接依赖 Row 对象结构。
    @staticmethod
    def _row_to_product(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "product_id": row["product_id"],
            "name": row["name"],
            "category": row["category"],
            "brand": row["brand"],
            "price": row["price"],
            "original_price": row["original_price"],
            "stock": row["stock"],
            "rating": row["rating"],
            "sales_count": row["sales_count"],
            "tags": row["tags"],
            "summary": row["summary"],
            "specs": json.loads(row["specs_json"] or "{}"),
            "is_featured": bool(row["is_featured"]),
        }

    # 做什么：把 SQLite 行对象转换成订单字典。
    # 为什么：让订单接口、对话上下文和工具层使用统一结构。
    @staticmethod
    def _row_to_order(row: sqlite3.Row, item_rows: List[sqlite3.Row]) -> Dict[str, Any]:
        return {
            "order_id": row["order_id"],
            "user_id": row["user_id"],
            "status": row["status"],
            "total_amount": row["total_amount"],
            "payment_amount": row["payment_amount"],
            "payment_method": row["payment_method"],
            "shipping_status": row["shipping_status"],
            "shipping_company": row["shipping_company"],
            "tracking_no": row["tracking_no"],
            "created_at": row["created_at"],
            "paid_at": row["paid_at"],
            "shipped_at": row["shipped_at"],
            "delivered_at": row["delivered_at"],
            "coupon_code": row["coupon_code"],
            "address_summary": row["address_summary"],
            "invoice_title": row["invoice_title"],
            "after_sales_status": row["after_sales_status"],
            "items": [
                {
                    "product_id": item["product_id"],
                    "product_name_snapshot": item["product_name_snapshot"],
                    "sku_snapshot": item["sku_snapshot"],
                    "quantity": item["quantity"],
                    "unit_price": item["unit_price"],
                }
                for item in item_rows
            ],
        }

    # 做什么：从用户消息提取预算上限。
    # 为什么：预算型导购问题是综合电商最常见的推荐约束。
    @staticmethod
    def _extract_budget(message: str) -> Optional[float]:
        matched = re.search(r"(\d{2,5})\s*元", message)
        if matched:
            return float(matched.group(1))
        matched = re.search(r"预算\s*(\d{2,5})", message)
        if matched:
            return float(matched.group(1))
        return None

    # 做什么：从用户消息提取类目。
    # 为什么：提升导购检索的相关性，减少跨类目噪声。
    @staticmethod
    def _extract_category(message: str) -> Optional[str]:
        categories = {
            "手机": "数码",
            "耳机": "数码",
            "笔记本": "数码",
            "投影": "数码",
            "书桌": "家居",
            "四件套": "家居",
            "露营椅": "家居",
            "水壶": "小家电",
            "咖啡机": "小家电",
            "吹风机": "个护",
            "洁面": "个护",
            "凝珠": "日用",
        }
        for keyword, category in categories.items():
            if keyword in message:
                return category
        return None

    # 做什么：从自然语言中提取更适合商品库检索的关键词。
    # 为什么：把预算、语气词等噪音剥离掉，提升结构化商品检索命中率。
    @staticmethod
    def _extract_search_terms(message: str) -> List[str]:
        hint_terms = [
            "手机",
            "耳机",
            "笔记本",
            "投影",
            "书桌",
            "水壶",
            "吹风机",
            "咖啡机",
            "凝珠",
            "四件套",
            "洁面",
            "露营椅",
            "拍照",
            "续航",
            "降噪",
            "轻薄",
            "便携",
            "护发",
            "家用",
            "送礼",
            "露营",
        ]
        terms: List[str] = []
        for term in hint_terms:
            if term in message and term not in terms:
                terms.append(term)

        ascii_terms = re.findall(r"[A-Za-z0-9]{2,}", message)
        for term in ascii_terms:
            if term.isdigit():
                continue
            if term.lower() in {"mp", "2026"}:
                continue
            if term not in terms:
                terms.append(term)
        return terms[:4]

    # 做什么：格式化订单事实为 prompt 上下文。
    # 为什么：让 Agent 能直接引用物流、支付和售后状态，不再凭空猜测。
    @staticmethod
    def _format_order_context(order: Dict[str, Any]) -> str:
        lines = [
            "[订单库结果]",
            f"订单号: {order['order_id']}",
            f"订单状态: {order['status']}",
            f"物流状态: {order['shipping_status']}",
            f"物流公司: {order['shipping_company'] or '待分配'}",
            f"运单号: {order['tracking_no'] or '待生成'}",
            f"实付金额: {order['payment_amount']} 元",
            f"支付方式: {order['payment_method']}",
            f"优惠券: {order['coupon_code'] or '无'}",
            f"发票抬头: {order['invoice_title']}",
            f"售后状态: {order['after_sales_status']}",
            f"收货地址摘要: {order['address_summary']}",
        ]
        if order["items"]:
            lines.append("订单商品:")
            for item in order["items"]:
                lines.append(
                    f"- {item['product_name_snapshot']} | 规格: {item['sku_snapshot']} | 数量: {item['quantity']} | 单价: {item['unit_price']} 元"
                )
        lines.append("请严格基于以上订单事实回答，不要虚构物流进度、退款结果或发票状态。")
        return "\n".join(lines)
