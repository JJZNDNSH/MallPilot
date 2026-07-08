"""
MallPilot 结构化电商数据层。
这个模块负责使用 SQLAlchemy 管理商品、订单、支付、物流与售后数据，
并为导购、订单和售后 Agent 提供真实的 MySQL 查询能力。
"""
from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import create_engine
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


# 做什么：定义 SQLAlchemy ORM 基类。
# 为什么：统一声明所有业务表模型，便于建表和查询复用。
class Base(DeclarativeBase):
    pass


# 做什么：定义商品表模型。
# 为什么：让商品搜索、推荐、比价和库存查询都基于 ORM 访问真实 MySQL 数据。
class Product(Base):
    __tablename__ = "products"

    # 做什么：商品主键。
    # 为什么：用于唯一标识商品并与订单明细建立关联。
    product_id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="商品主键")
    # 做什么：商品名称。
    # 为什么：用于展示和搜索匹配。
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="商品名称")
    # 做什么：商品类目。
    # 为什么：用于导购分类筛选。
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="商品类目")
    # 做什么：商品品牌。
    # 为什么：用于展示品牌和品牌偏好推荐。
    brand: Mapped[str] = mapped_column(String(64), nullable=False, comment="商品品牌")
    # 做什么：商品售价。
    # 为什么：用于预算筛选和排序。
    price: Mapped[float] = mapped_column(Float, nullable=False, index=True, comment="商品售价")
    # 做什么：商品原价。
    # 为什么：用于展示优惠幅度。
    original_price: Mapped[float] = mapped_column(Float, nullable=False, comment="商品原价")
    # 做什么：库存数量。
    # 为什么：用于库存快照和可售判断。
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="库存数量")
    # 做什么：商品评分。
    # 为什么：用于推荐排序和展示。
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="商品评分")
    # 做什么：销量。
    # 为什么：用于热销排序和推荐排序。
    sales_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="销量")
    # 做什么：标签文本。
    # 为什么：用于关键词搜索和导购解释。
    tags: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="商品标签")
    # 做什么：商品简介。
    # 为什么：用于搜索召回和上下文构建。
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="商品简介")
    # 做什么：商品规格 JSON。
    # 为什么：用于详情展示和规格对比。
    specs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="商品规格 JSON")
    # 做什么：是否主推。
    # 为什么：用于首页或兜底推荐。
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否主推商品")


# 做什么：定义促销活动表模型。
# 为什么：让导购工具能够查询真实促销、优惠券和活动信息。
class Promotion(Base):
    __tablename__ = "promotions"

    # 做什么：活动主键。
    # 为什么：用于唯一标识促销记录。
    promotion_id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="活动主键")
    # 做什么：活动标题。
    # 为什么：用于对外展示活动名称。
    title: Mapped[str] = mapped_column(String(128), nullable=False, comment="活动标题")
    # 做什么：活动描述。
    # 为什么：用于说明适用场景和优惠力度。
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="活动描述")
    # 做什么：适用类目。
    # 为什么：用于按类目过滤活动。
    applies_to_category: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True, comment="适用类目")
    # 做什么：适用商品 ID。
    # 为什么：用于按单品绑定专属活动。
    applies_to_product_id: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True, comment="适用商品 ID")
    # 做什么：优惠券码。
    # 为什么：用于订单与优惠联动查询。
    coupon_code: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True, comment="优惠券码")
    # 做什么：折扣标签。
    # 为什么：用于导购描述优惠规则。
    discount_label: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="折扣标签")
    # 做什么：最低消费门槛。
    # 为什么：用于筛选预算适配活动。
    min_spend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="最低消费门槛")
    # 做什么：活动开始时间。
    # 为什么：用于判断活动是否生效。
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="活动开始时间")
    # 做什么：活动结束时间。
    # 为什么：用于判断活动是否过期。
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="活动结束时间")
    # 做什么：活动状态。
    # 为什么：用于快速过滤 active 活动。
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True, comment="活动状态")
    # 做什么：活动优先级。
    # 为什么：用于活动排序。
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=99, comment="活动优先级")


# 做什么：定义订单表模型。
# 为什么：让订单查询、支付查询、物流查询和售后判断都基于真实订单事实。
class Order(Base):
    __tablename__ = "orders"

    # 做什么：订单主键。
    # 为什么：用于唯一标识订单。
    order_id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="订单主键")
    # 做什么：用户标识。
    # 为什么：用于按用户筛选订单。
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="用户标识")
    # 做什么：订单状态。
    # 为什么：用于订单和售后流程判断。
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="订单状态")
    # 做什么：订单总金额。
    # 为什么：用于金额展示和交易统计。
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="订单总金额")
    # 做什么：实付金额。
    # 为什么：用于支付展示和退款计算。
    payment_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="实付金额")
    # 做什么：支付方式。
    # 为什么：用于支付信息展示。
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="支付方式")
    # 做什么：物流状态。
    # 为什么：用于物流和签收查询。
    shipping_status: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True, comment="物流状态")
    # 做什么：物流公司。
    # 为什么：用于物流展示和追踪。
    shipping_company: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="物流公司")
    # 做什么：运单号。
    # 为什么：用于追踪物流轨迹。
    tracking_no: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="运单号")
    # 做什么：下单时间。
    # 为什么：用于订单时间线和排序。
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="下单时间")
    # 做什么：支付时间。
    # 为什么：用于支付时间线和支付状态判断。
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="支付时间")
    # 做什么：发货时间。
    # 为什么：用于物流时间线和售后资格判断。
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="发货时间")
    # 做什么：签收时间。
    # 为什么：用于退换货时效判断。
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="签收时间")
    # 做什么：优惠券码。
    # 为什么：用于优惠券使用记录查询。
    coupon_code: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True, comment="优惠券码")
    # 做什么：地址摘要。
    # 为什么：用于订单上下文展示，不暴露完整隐私。
    address_summary: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="地址摘要")
    # 做什么：发票抬头。
    # 为什么：用于发票查询。
    invoice_title: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="发票抬头")
    # 做什么：售后状态。
    # 为什么：用于订单视角的售后摘要。
    after_sales_status: Mapped[str] = mapped_column(String(32), nullable=False, default="无", comment="售后状态")
    # 做什么：订单明细关系。
    # 为什么：用于一次性加载订单商品明细。
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    # 做什么：支付交易关系。
    # 为什么：用于查询真实支付流水。
    payment_transactions: Mapped[List["PaymentTransaction"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    # 做什么：物流轨迹关系。
    # 为什么：用于构建物流时间线。
    logistics_events: Mapped[List["LogisticsEvent"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    # 做什么：售后工单关系。
    # 为什么：用于从订单直接追踪售后情况。
    after_sales_tickets: Mapped[List["AfterSalesTicket"]] = relationship(back_populates="order", cascade="all, delete-orphan")


# 做什么：定义订单明细表模型。
# 为什么：让订单可以包含多商品并支持按明细查询。
class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "item_index", name="uq_order_items_order_index"),)

    # 做什么：明细自增主键。
    # 为什么：便于 ORM 管理多条订单明细。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="明细主键")
    # 做什么：订单编号。
    # 为什么：用于关联主订单。
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True, comment="订单编号")
    # 做什么：商品编号。
    # 为什么：用于关联商品信息。
    product_id: Mapped[str] = mapped_column(String(32), ForeignKey("products.product_id"), nullable=False, index=True, comment="商品编号")
    # 做什么：商品名称快照。
    # 为什么：用于订单快照展示，避免商品改名影响历史订单。
    product_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False, comment="商品名称快照")
    # 做什么：规格快照。
    # 为什么：用于订单明细展示规格。
    sku_snapshot: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="规格快照")
    # 做什么：购买数量。
    # 为什么：用于订单金额和明细展示。
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="购买数量")
    # 做什么：下单单价。
    # 为什么：用于保留历史成交价。
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="成交单价")
    # 做什么：明细顺序。
    # 为什么：用于按下单展示顺序返回商品列表。
    item_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="明细顺序")
    # 做什么：订单关系。
    # 为什么：用于从明细回到主订单。
    order: Mapped[Order] = relationship(back_populates="items")
    # 做什么：商品关系。
    # 为什么：用于需要时联动商品资料。
    product: Mapped[Product] = relationship()


# 做什么：定义支付交易表模型。
# 为什么：让支付查询和交易记录能够落到真实交易流水，而不是只看订单字段。
class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    # 做什么：交易流水主键。
    # 为什么：用于唯一标识支付流水。
    transaction_id: Mapped[str] = mapped_column(String(40), primary_key=True, comment="支付流水主键")
    # 做什么：订单编号。
    # 为什么：用于关联对应订单。
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True, comment="订单编号")
    # 做什么：用户标识。
    # 为什么：用于按用户过滤交易记录。
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="用户标识")
    # 做什么：交易阶段。
    # 为什么：用于区分支付、退款、补差价等流水。
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="交易阶段")
    # 做什么：渠道名称。
    # 为什么：用于展示支付渠道。
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="交易渠道")
    # 做什么：交易金额。
    # 为什么：用于支付和退款金额展示。
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="交易金额")
    # 做什么：交易状态。
    # 为什么：用于判断支付是否成功或退款是否完成。
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="交易状态")
    # 做什么：交易时间。
    # 为什么：用于排序和时间线展示。
    transacted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="交易时间")
    # 做什么：渠道流水号。
    # 为什么：用于支付核对和排障。
    channel_reference: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="渠道流水号")
    # 做什么：交易备注。
    # 为什么：用于补充说明交易含义。
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="交易备注")
    # 做什么：订单关系。
    # 为什么：用于从交易回溯订单。
    order: Mapped[Order] = relationship(back_populates="payment_transactions")


# 做什么：定义物流事件表模型。
# 为什么：让物流查询能够返回完整轨迹。
class LogisticsEvent(Base):
    __tablename__ = "logistics_events"

    # 做什么：物流事件主键。
    # 为什么：用于唯一标识物流轨迹节点。
    event_id: Mapped[str] = mapped_column(String(40), primary_key=True, comment="物流事件主键")
    # 做什么：订单编号。
    # 为什么：用于关联对应订单。
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True, comment="订单编号")
    # 做什么：事件时间。
    # 为什么：用于构建物流时间线。
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="事件时间")
    # 做什么：事件状态。
    # 为什么：用于展示物流节点类型。
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="事件状态")
    # 做什么：事件详情。
    # 为什么：用于展示物流节点说明。
    detail: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="事件详情")
    # 做什么：订单关系。
    # 为什么：用于从物流节点回到订单。
    order: Mapped[Order] = relationship(back_populates="logistics_events")


# 做什么：定义售后工单表模型。
# 为什么：让退款、换货、投诉等查询都基于真实售后记录。
class AfterSalesTicket(Base):
    __tablename__ = "after_sales_tickets"

    # 做什么：售后工单主键。
    # 为什么：用于唯一标识售后记录。
    ticket_id: Mapped[str] = mapped_column(String(40), primary_key=True, comment="售后工单主键")
    # 做什么：订单编号。
    # 为什么：用于关联售后对应订单。
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True, comment="订单编号")
    # 做什么：用户标识。
    # 为什么：用于按用户查询售后历史。
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="用户标识")
    # 做什么：工单类型。
    # 为什么：用于区分退款、换货、投诉等。
    ticket_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="工单类型")
    # 做什么：工单状态。
    # 为什么：用于展示售后进度。
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="工单状态")
    # 做什么：售后原因。
    # 为什么：用于解释用户诉求。
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="售后原因")
    # 做什么：退款金额。
    # 为什么：用于退款工单展示金额。
    refund_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="退款金额")
    # 做什么：申请时间。
    # 为什么：用于售后时间线和排序。
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="申请时间")
    # 做什么：更新时间。
    # 为什么：用于展示最新售后进度。
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="更新时间")
    # 做什么：处理说明。
    # 为什么：用于展示客服处理结果。
    resolution_note: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="处理说明")
    # 做什么：订单关系。
    # 为什么：用于从售后工单回溯订单。
    order: Mapped[Order] = relationship(back_populates="after_sales_tickets")


# 做什么：定义服务政策表模型。
# 为什么：让售后规则查询能够访问真实规则数据。
class ServicePolicy(Base):
    __tablename__ = "service_policies"

    # 做什么：政策主键。
    # 为什么：用于唯一标识政策记录。
    policy_id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="政策主键")
    # 做什么：政策类型。
    # 为什么：用于区分退款、换货、运费、投诉等规则。
    policy_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="政策类型")
    # 做什么：政策标题。
    # 为什么：用于展示规则名称。
    title: Mapped[str] = mapped_column(String(128), nullable=False, comment="政策标题")
    # 做什么：政策内容。
    # 为什么：用于返回可解释规则文本。
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="政策内容")
    # 做什么：适用类目。
    # 为什么：用于按商品类目过滤规则。
    applies_to_category: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True, comment="适用类目")
    # 做什么：适用状态。
    # 为什么：用于按订单或售后状态筛选规则。
    applies_to_status: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="适用状态")
    # 做什么：优先级。
    # 为什么：用于规则排序。
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=99, comment="优先级")


# 做什么：提供综合电商演示商品数据。
# 为什么：让导购 Agent 能基于更丰富的真实 MySQL 数据做搜索和推荐。
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
        "summary": "14 英寸轻薄本，适合日常办公、网课和出差携带。",
        "specs_json": json.dumps({"cpu": "i5", "memory": "16GB", "storage": "512GB SSD", "battery": "14h"}, ensure_ascii=False),
        "is_featured": True,
    },
    {
        "product_id": "P1002",
        "name": "云雀 Pro 降噪蓝牙耳机",
        "category": "数码",
        "brand": "云雀",
        "price": 699.0,
        "original_price": 899.0,
        "stock": 88,
        "rating": 4.7,
        "sales_count": 3650,
        "tags": "主动降噪,通勤,音乐",
        "summary": "支持主动降噪和通透模式，适合通勤、运动和移动办公。",
        "specs_json": json.dumps({"battery": "30h", "noise_canceling": True, "weight": "4.5g"}, ensure_ascii=False),
        "is_featured": True,
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
        "tags": "拍照,续航,学生党,手机",
        "summary": "主打夜景拍照和大电池，适合日常拍摄与轻度游戏。",
        "specs_json": json.dumps({"screen": "6.67英寸", "camera": "5000万像素", "battery": "5200mAh"}, ensure_ascii=False),
        "is_featured": True,
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
        "is_featured": False,
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
        "is_featured": True,
    },
    {
        "product_id": "P1006",
        "name": "青岚 柔雾吹风机",
        "category": "个护",
        "brand": "青岚",
        "price": 399.0,
        "original_price": 499.0,
        "stock": 67,
        "rating": 4.7,
        "sales_count": 2130,
        "tags": "护发,低噪,旅行",
        "summary": "轻量机身搭配负离子护发，适合日常快干和旅行携带。",
        "specs_json": json.dumps({"power": "1600W", "noise": "低噪", "weight": "410g"}, ensure_ascii=False),
        "is_featured": False,
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
        "is_featured": False,
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
        "is_featured": True,
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
        "is_featured": True,
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
        "is_featured": False,
    },
    {
        "product_id": "P1011",
        "name": "禾沐 氨基酸洁面慕斯",
        "category": "个护",
        "brand": "禾沐",
        "price": 89.0,
        "original_price": 109.0,
        "stock": 134,
        "rating": 4.8,
        "sales_count": 4870,
        "tags": "敏感肌,洁面,温和",
        "summary": "温和洁净不过度拔干，适合晨间清洁和敏感肌用户。",
        "specs_json": json.dumps({"volume": "160ml", "skin_type": "敏感肌", "foam": "绵密"}, ensure_ascii=False),
        "is_featured": False,
    },
    {
        "product_id": "P1012",
        "name": "晓野 折叠露营椅",
        "category": "家居",
        "brand": "晓野",
        "price": 159.0,
        "original_price": 199.0,
        "stock": 51,
        "rating": 4.6,
        "sales_count": 1390,
        "tags": "露营,折叠,户外",
        "summary": "可折叠便携设计，适合阳台休闲、露营和自驾出行。",
        "specs_json": json.dumps({"load": "120kg", "material": "铝合金", "weight": "2.3kg"}, ensure_ascii=False),
        "is_featured": False,
    },
    {
        "product_id": "P1013",
        "name": "远峰 Turbo 长续航手机",
        "category": "数码",
        "brand": "远峰",
        "price": 2899.0,
        "original_price": 3199.0,
        "stock": 95,
        "rating": 4.8,
        "sales_count": 4260,
        "tags": "手机,续航,游戏,快充",
        "summary": "6000mAh 大电池搭配 80W 快充，适合重度通勤和长时间外出。",
        "specs_json": json.dumps({"screen": "6.78英寸", "battery": "6000mAh", "charge": "80W", "memory": "12GB+256GB"}, ensure_ascii=False),
        "is_featured": True,
    },
    {
        "product_id": "P1014",
        "name": "青岳 Lite 影像手机",
        "category": "数码",
        "brand": "青岳",
        "price": 2599.0,
        "original_price": 2899.0,
        "stock": 77,
        "rating": 4.7,
        "sales_count": 3510,
        "tags": "手机,拍照,续航,轻薄",
        "summary": "5500mAh 长续航机身兼顾轻薄手感，适合拍照和日常高频使用。",
        "specs_json": json.dumps({"screen": "6.67英寸", "battery": "5500mAh", "camera": "5000万像素 OIS", "weight": "188g"}, ensure_ascii=False),
        "is_featured": True,
    },
    {
        "product_id": "P1015",
        "name": "曜石 Note 超能续航手机",
        "category": "数码",
        "brand": "曜石",
        "price": 2199.0,
        "original_price": 2499.0,
        "stock": 118,
        "rating": 4.7,
        "sales_count": 5620,
        "tags": "手机,续航,学生党,大电池",
        "summary": "6200mAh 电池主打超长续航和高性价比，适合预算 3000 内购机。",
        "specs_json": json.dumps({"screen": "6.72英寸", "battery": "6200mAh", "memory": "8GB+256GB", "charge": "67W"}, ensure_ascii=False),
        "is_featured": True,
    },
    {
        "product_id": "P1016",
        "name": "岚海 Watch S 智能手表",
        "category": "数码",
        "brand": "岚海",
        "price": 899.0,
        "original_price": 1099.0,
        "stock": 83,
        "rating": 4.6,
        "sales_count": 2420,
        "tags": "手表,健康,运动,续航",
        "summary": "支持 14 天续航、心率血氧监测和百种运动模式。",
        "specs_json": json.dumps({"battery": "14天", "screen": "1.43英寸 AMOLED", "gps": True}, ensure_ascii=False),
        "is_featured": False,
    },
    {
        "product_id": "P1017",
        "name": "森屿 宠物净味空气净化器",
        "category": "小家电",
        "brand": "森屿",
        "price": 1399.0,
        "original_price": 1699.0,
        "stock": 41,
        "rating": 4.8,
        "sales_count": 1580,
        "tags": "净化器,宠物家庭,除味",
        "summary": "针对宠物异味和浮毛设计，适合小户型宠物家庭。",
        "specs_json": json.dumps({"cadf": "400m3/h", "noise": "28dB", "area": "40㎡"}, ensure_ascii=False),
        "is_featured": True,
    },
    {
        "product_id": "P1018",
        "name": "溪谷 速热破壁豆浆机",
        "category": "小家电",
        "brand": "溪谷",
        "price": 459.0,
        "original_price": 559.0,
        "stock": 64,
        "rating": 4.7,
        "sales_count": 2790,
        "tags": "早餐,破壁,家用",
        "summary": "支持免泡豆和 20 分钟快煮，适合上班族早餐场景。",
        "specs_json": json.dumps({"capacity": "1.2L", "preset": 8, "clean": "自动清洗"}, ensure_ascii=False),
        "is_featured": False,
    },
]


# 做什么：提供综合电商演示订单数据。
# 为什么：让订单 Agent 和售后 Agent 能基于真实订单事实工作。
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
        "delivered_at": None,
        "coupon_code": "JULY200",
        "address_summary": "上海市浦东新区锦绣路 88 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1003", "product_name_snapshot": "极光 Max 拍照手机", "sku_snapshot": "星夜黑 12GB+256GB", "quantity": 1, "unit_price": 3299.0},
        ],
    },
    {
        "order_id": "MP20260706002",
        "user_id": "anonymous",
        "status": "已支付",
        "total_amount": 899.0,
        "payment_amount": 899.0,
        "payment_method": "微信支付",
        "shipping_status": "待发货",
        "shipping_company": "",
        "tracking_no": "",
        "created_at": "2026-07-05 21:09:00",
        "paid_at": "2026-07-05 21:10:00",
        "shipped_at": None,
        "delivered_at": None,
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
        "delivered_at": None,
        "coupon_code": "NEW50",
        "address_summary": "北京市朝阳区酒仙桥北路 10 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1002", "product_name_snapshot": "云雀 Pro 降噪蓝牙耳机", "sku_snapshot": "月光白", "quantity": 1, "unit_price": 699.0},
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
            {"product_id": "P1006", "product_name_snapshot": "青岚 柔雾吹风机", "sku_snapshot": "薄荷绿", "quantity": 1, "unit_price": 399.0},
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
        "paid_at": None,
        "shipped_at": None,
        "delivered_at": None,
        "coupon_code": "",
        "address_summary": "深圳市南山区科技路 18 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1012", "product_name_snapshot": "晓野 折叠露营椅", "sku_snapshot": "卡其色", "quantity": 1, "unit_price": 159.0},
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
        "delivered_at": None,
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
        "shipped_at": None,
        "delivered_at": None,
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
            {"product_id": "P1011", "product_name_snapshot": "禾沐 氨基酸洁面慕斯", "sku_snapshot": "160ml", "quantity": 1, "unit_price": 89.0},
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
    {
        "order_id": "MP20260706012",
        "user_id": "phone_user",
        "status": "已完成",
        "total_amount": 2899.0,
        "payment_amount": 2699.0,
        "payment_method": "支付宝",
        "shipping_status": "已签收",
        "shipping_company": "顺丰速运",
        "tracking_no": "SF8811223344",
        "created_at": "2026-07-02 19:45:00",
        "paid_at": "2026-07-02 19:46:00",
        "shipped_at": "2026-07-03 12:40:00",
        "delivered_at": "2026-07-04 14:20:00",
        "coupon_code": "JULY200",
        "address_summary": "西安市雁塔区科技二路 9 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1013", "product_name_snapshot": "远峰 Turbo 长续航手机", "sku_snapshot": "冰川蓝 12GB+256GB", "quantity": 1, "unit_price": 2899.0},
        ],
    },
    {
        "order_id": "MP20260706013",
        "user_id": "phone_user",
        "status": "已完成",
        "total_amount": 2199.0,
        "payment_amount": 2199.0,
        "payment_method": "微信支付",
        "shipping_status": "已签收",
        "shipping_company": "中通快递",
        "tracking_no": "ZT1100223344",
        "created_at": "2026-06-18 10:10:00",
        "paid_at": "2026-06-18 10:12:00",
        "shipped_at": "2026-06-19 11:30:00",
        "delivered_at": "2026-06-21 15:40:00",
        "coupon_code": "",
        "address_summary": "重庆市渝北区金开大道 101 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1015", "product_name_snapshot": "曜石 Note 超能续航手机", "sku_snapshot": "曜黑 8GB+256GB", "quantity": 1, "unit_price": 2199.0},
        ],
    },
    {
        "order_id": "MP20260706014",
        "user_id": "family_user",
        "status": "已发货",
        "total_amount": 1858.0,
        "payment_amount": 1798.0,
        "payment_method": "银行卡",
        "shipping_status": "已发货",
        "shipping_company": "京东物流",
        "tracking_no": "JD8899001122",
        "created_at": "2026-07-06 15:40:00",
        "paid_at": "2026-07-06 15:42:00",
        "shipped_at": "2026-07-07 09:30:00",
        "delivered_at": None,
        "coupon_code": "HOME60",
        "address_summary": "天津市南开区复康路 55 号",
        "invoice_title": "个人",
        "after_sales_status": "无",
        "items": [
            {"product_id": "P1017", "product_name_snapshot": "森屿 宠物净味空气净化器", "sku_snapshot": "标准版", "quantity": 1, "unit_price": 1399.0},
            {"product_id": "P1018", "product_name_snapshot": "溪谷 速热破壁豆浆机", "sku_snapshot": "奶咖色", "quantity": 1, "unit_price": 459.0},
        ],
    },
]


# 做什么：提供综合电商演示促销数据。
# 为什么：让导购和订单工具都能解释当前促销与券码使用情况。
DEMO_PROMOTIONS: List[Dict[str, Any]] = [
    {
        "promotion_id": "PR20260701",
        "title": "数码焕新季满 3000 减 200",
        "description": "适用于数码类商品的大额换新优惠，适合预算在 3000 元以上的购机用户。",
        "applies_to_category": "数码",
        "applies_to_product_id": "",
        "coupon_code": "JULY200",
        "discount_label": "满3000减200",
        "min_spend": 3000.0,
        "starts_at": "2026-07-01 00:00:00",
        "ends_at": "2026-07-31 23:59:59",
        "status": "active",
        "priority": 1,
    },
    {
        "promotion_id": "PR20260702",
        "title": "新客耳机首单立减 50",
        "description": "适用于耳机和可穿戴产品的新客优惠。",
        "applies_to_category": "数码",
        "applies_to_product_id": "P1002",
        "coupon_code": "NEW50",
        "discount_label": "首单减50",
        "min_spend": 399.0,
        "starts_at": "2026-07-01 00:00:00",
        "ends_at": "2026-07-20 23:59:59",
        "status": "active",
        "priority": 2,
    },
    {
        "promotion_id": "PR20260703",
        "title": "投影好礼立减 100",
        "description": "适合送礼和家庭观影场景的单品优惠。",
        "applies_to_category": "数码",
        "applies_to_product_id": "P1009",
        "coupon_code": "PROJ100",
        "discount_label": "立减100",
        "min_spend": 2000.0,
        "starts_at": "2026-07-01 00:00:00",
        "ends_at": "2026-07-31 23:59:59",
        "status": "active",
        "priority": 3,
    },
    {
        "promotion_id": "PR20260704",
        "title": "居家组合满 300 减 30",
        "description": "适用于家居日用商品的组合购买优惠。",
        "applies_to_category": "家居",
        "applies_to_product_id": "",
        "coupon_code": "HOME30",
        "discount_label": "满300减30",
        "min_spend": 300.0,
        "starts_at": "2026-06-15 00:00:00",
        "ends_at": "2026-07-31 23:59:59",
        "status": "active",
        "priority": 4,
    },
    {
        "promotion_id": "PR20260705",
        "title": "咖啡露营装备减 30",
        "description": "适用于便携咖啡机和露营相关设备的轻促销活动。",
        "applies_to_category": "小家电",
        "applies_to_product_id": "P1007",
        "coupon_code": "COFFEE30",
        "discount_label": "立减30",
        "min_spend": 499.0,
        "starts_at": "2026-06-20 00:00:00",
        "ends_at": "2026-07-20 23:59:59",
        "status": "active",
        "priority": 5,
    },
]


# 做什么：提供综合电商演示支付流水数据。
# 为什么：让订单 Agent 真实读取支付、退款与补偿交易记录。
DEMO_PAYMENT_TRANSACTIONS: List[Dict[str, Any]] = [
    {"transaction_id": "TX202607020001", "order_id": "MP20260706001", "user_id": "anonymous", "transaction_type": "payment", "channel": "支付宝", "amount": 3099.0, "status": "success", "transacted_at": "2026-07-02 10:15:12", "channel_reference": "ALI78345001", "note": "订单支付成功"},
    {"transaction_id": "TX202607050001", "order_id": "MP20260706002", "user_id": "anonymous", "transaction_type": "payment", "channel": "微信支付", "amount": 899.0, "status": "success", "transacted_at": "2026-07-05 21:10:09", "channel_reference": "WX99231001", "note": "订单支付成功"},
    {"transaction_id": "TX202606280001", "order_id": "MP20260706003", "user_id": "anonymous", "transaction_type": "payment", "channel": "银行卡", "amount": 239.0, "status": "success", "transacted_at": "2026-06-28 09:44:11", "channel_reference": "BANK5512001", "note": "订单支付成功"},
    {"transaction_id": "TX202607010001", "order_id": "MP20260706003", "user_id": "anonymous", "transaction_type": "refund", "channel": "原路退回", "amount": 239.0, "status": "processing", "transacted_at": "2026-07-01 09:30:00", "channel_reference": "RF2393001", "note": "退款审核通过，待原路退回"},
    {"transaction_id": "TX202607030001", "order_id": "MP20260706004", "user_id": "eval_user", "transaction_type": "payment", "channel": "微信支付", "amount": 649.0, "status": "success", "transacted_at": "2026-07-03 12:34:21", "channel_reference": "WX99118273", "note": "订单支付成功"},
    {"transaction_id": "TX202606250001", "order_id": "MP20260706005", "user_id": "eval_user", "transaction_type": "payment", "channel": "支付宝", "amount": 399.0, "status": "success", "transacted_at": "2026-06-25 18:25:10", "channel_reference": "ALI38921002", "note": "订单支付成功"},
    {"transaction_id": "TX202607010002", "order_id": "MP20260706007", "user_id": "guest_buyer", "transaction_type": "payment", "channel": "支付宝", "amount": 569.0, "status": "success", "transacted_at": "2026-07-01 16:20:45", "channel_reference": "ALI56987230", "note": "订单支付成功"},
    {"transaction_id": "TX202606200001", "order_id": "MP20260706008", "user_id": "guest_buyer", "transaction_type": "payment", "channel": "微信支付", "amount": 318.0, "status": "success", "transacted_at": "2026-06-20 13:21:03", "channel_reference": "WX77120300", "note": "订单支付成功"},
    {"transaction_id": "TX202607040001", "order_id": "MP20260706009", "user_id": "gift_user", "transaction_type": "payment", "channel": "银行卡", "amount": 2499.0, "status": "success", "transacted_at": "2026-07-04 11:05:16", "channel_reference": "BANK9088123", "note": "订单支付成功"},
    {"transaction_id": "TX202606150001", "order_id": "MP20260706010", "user_id": "vip_user", "transaction_type": "payment", "channel": "微信支付", "amount": 89.0, "status": "success", "transacted_at": "2026-06-15 20:09:23", "channel_reference": "WX19283010", "note": "订单支付成功"},
    {"transaction_id": "TX202606180001", "order_id": "MP20260706010", "user_id": "vip_user", "transaction_type": "refund", "channel": "原路退回", "amount": 89.0, "status": "success", "transacted_at": "2026-06-18 14:02:00", "channel_reference": "RF0008910", "note": "退款已原路退回"},
    {"transaction_id": "TX202606100001", "order_id": "MP20260706011", "user_id": "vip_user", "transaction_type": "payment", "channel": "银行卡", "amount": 4699.0, "status": "success", "transacted_at": "2026-06-10 09:52:09", "channel_reference": "BANK7766120", "note": "订单支付成功"},
    {"transaction_id": "TX202607020002", "order_id": "MP20260706012", "user_id": "phone_user", "transaction_type": "payment", "channel": "支付宝", "amount": 2699.0, "status": "success", "transacted_at": "2026-07-02 19:46:31", "channel_reference": "ALI23399881", "note": "订单支付成功"},
    {"transaction_id": "TX202606180002", "order_id": "MP20260706013", "user_id": "phone_user", "transaction_type": "payment", "channel": "微信支付", "amount": 2199.0, "status": "success", "transacted_at": "2026-06-18 10:12:28", "channel_reference": "WX00228193", "note": "订单支付成功"},
    {"transaction_id": "TX202607060001", "order_id": "MP20260706014", "user_id": "family_user", "transaction_type": "payment", "channel": "银行卡", "amount": 1798.0, "status": "success", "transacted_at": "2026-07-06 15:42:16", "channel_reference": "BANK2177001", "note": "订单支付成功"},
]


# 做什么：提供综合电商演示物流轨迹数据。
# 为什么：让物流与订单时间线查询可返回真实轨迹节点。
DEMO_LOGISTICS_EVENTS: List[Dict[str, Any]] = [
    {"event_id": "LE0001", "order_id": "MP20260706001", "event_time": "2026-07-03 08:20:00", "status": "已发货", "detail": "包裹已由上海浦东仓发出"},
    {"event_id": "LE0002", "order_id": "MP20260706001", "event_time": "2026-07-03 23:16:00", "status": "运输中", "detail": "包裹到达苏州转运中心"},
    {"event_id": "LE0003", "order_id": "MP20260706001", "event_time": "2026-07-04 11:40:00", "status": "运输中", "detail": "包裹离开苏州转运中心前往上海"},
    {"event_id": "LE0004", "order_id": "MP20260706003", "event_time": "2026-06-29 13:00:00", "status": "已发货", "detail": "包裹已由上海仓发出"},
    {"event_id": "LE0005", "order_id": "MP20260706003", "event_time": "2026-06-30 09:12:00", "status": "派送中", "detail": "配送员正在派送"},
    {"event_id": "LE0006", "order_id": "MP20260706003", "event_time": "2026-06-30 17:45:00", "status": "已签收", "detail": "前台代收签收"},
    {"event_id": "LE0007", "order_id": "MP20260706004", "event_time": "2026-07-04 09:10:00", "status": "已发货", "detail": "包裹已由北京仓发出"},
    {"event_id": "LE0008", "order_id": "MP20260706004", "event_time": "2026-07-04 20:35:00", "status": "运输中", "detail": "包裹到达北京分拨中心"},
    {"event_id": "LE0009", "order_id": "MP20260706005", "event_time": "2026-06-26 14:01:00", "status": "已发货", "detail": "包裹已由杭州仓发出"},
    {"event_id": "LE0010", "order_id": "MP20260706005", "event_time": "2026-06-27 09:20:00", "status": "派送中", "detail": "快递员即将上门派送"},
    {"event_id": "LE0011", "order_id": "MP20260706005", "event_time": "2026-06-27 16:30:00", "status": "已签收", "detail": "本人签收"},
    {"event_id": "LE0012", "order_id": "MP20260706007", "event_time": "2026-07-02 10:00:00", "status": "已发货", "detail": "广州仓已出库"},
    {"event_id": "LE0013", "order_id": "MP20260706008", "event_time": "2026-06-21 10:40:00", "status": "已发货", "detail": "成都仓已出库"},
    {"event_id": "LE0014", "order_id": "MP20260706008", "event_time": "2026-06-23 19:00:00", "status": "已签收", "detail": "门卫代收签收"},
    {"event_id": "LE0015", "order_id": "MP20260706012", "event_time": "2026-07-03 12:40:00", "status": "已发货", "detail": "西安仓已出库"},
    {"event_id": "LE0016", "order_id": "MP20260706012", "event_time": "2026-07-04 09:12:00", "status": "派送中", "detail": "快递员正在联系收件人"},
    {"event_id": "LE0017", "order_id": "MP20260706012", "event_time": "2026-07-04 14:20:00", "status": "已签收", "detail": "本人签收"},
    {"event_id": "LE0018", "order_id": "MP20260706013", "event_time": "2026-06-19 11:30:00", "status": "已发货", "detail": "重庆仓已出库"},
    {"event_id": "LE0019", "order_id": "MP20260706013", "event_time": "2026-06-21 15:40:00", "status": "已签收", "detail": "智能柜签收"},
    {"event_id": "LE0020", "order_id": "MP20260706014", "event_time": "2026-07-07 09:30:00", "status": "已发货", "detail": "天津仓已出库"},
]


# 做什么：提供综合电商演示售后工单数据。
# 为什么：让售后工具能够查询退款、换货、投诉等真实记录。
DEMO_AFTER_SALES_TICKETS: List[Dict[str, Any]] = [
    {
        "ticket_id": "AS2026070001",
        "order_id": "MP20260706003",
        "user_id": "anonymous",
        "ticket_type": "refund",
        "status": "处理中",
        "reason": "水壶加热异响，申请退款",
        "refund_amount": 239.0,
        "requested_at": "2026-07-01 09:10:00",
        "updated_at": "2026-07-01 10:00:00",
        "resolution_note": "已通过审核，等待原路退款到账。",
    },
    {
        "ticket_id": "AS2026070002",
        "order_id": "MP20260706005",
        "user_id": "eval_user",
        "ticket_type": "exchange",
        "status": "换货中",
        "reason": "吹风机外壳有轻微划痕，申请换货",
        "refund_amount": 0.0,
        "requested_at": "2026-06-28 10:05:00",
        "updated_at": "2026-06-29 15:20:00",
        "resolution_note": "换货申请已通过，等待用户寄回旧件。",
    },
    {
        "ticket_id": "AS2026070003",
        "order_id": "MP20260706010",
        "user_id": "vip_user",
        "ticket_type": "refund",
        "status": "已完成",
        "reason": "洁面慕斯泵头损坏",
        "refund_amount": 89.0,
        "requested_at": "2026-06-17 11:00:00",
        "updated_at": "2026-06-18 14:05:00",
        "resolution_note": "退款已原路退回。",
    },
    {
        "ticket_id": "AS2026070004",
        "order_id": "MP20260706012",
        "user_id": "phone_user",
        "ticket_type": "consult",
        "status": "已回复",
        "reason": "咨询是否支持 80W 原装快充",
        "refund_amount": 0.0,
        "requested_at": "2026-07-05 09:20:00",
        "updated_at": "2026-07-05 09:25:00",
        "resolution_note": "客服已确认标配支持 80W 快充。",
    },
    {
        "ticket_id": "AS2026070005",
        "order_id": "MP20260706014",
        "user_id": "family_user",
        "ticket_type": "complaint",
        "status": "待处理",
        "reason": "希望修改送货时间，客服回电较慢",
        "refund_amount": 0.0,
        "requested_at": "2026-07-07 18:10:00",
        "updated_at": "2026-07-07 18:10:00",
        "resolution_note": "已升级配送服务专员跟进。",
    },
]


# 做什么：提供综合电商演示售后政策数据。
# 为什么：让售后 Agent 在规则咨询场景下也能返回结构化规则结果。
DEMO_SERVICE_POLICIES: List[Dict[str, Any]] = [
    {
        "policy_id": "PL0001",
        "policy_type": "refund",
        "title": "普通商品 7 天无理由退货",
        "content": "已签收且不影响二次销售的商品，可在签收后 7 天内申请无理由退货。",
        "applies_to_category": "",
        "applies_to_status": "已签收,已完成",
        "priority": 1,
    },
    {
        "policy_id": "PL0002",
        "policy_type": "exchange",
        "title": "质量问题 15 天内换货",
        "content": "如商品存在性能故障或明显外观损坏，可在签收后 15 天内申请换货。",
        "applies_to_category": "",
        "applies_to_status": "已签收,已完成",
        "priority": 2,
    },
    {
        "policy_id": "PL0003",
        "policy_type": "invoice",
        "title": "电子发票开具规则",
        "content": "订单支付成功后可开具电子发票，发票抬头默认取下单时填写的信息。",
        "applies_to_category": "",
        "applies_to_status": "已支付,已发货,已签收,已完成",
        "priority": 3,
    },
    {
        "policy_id": "PL0004",
        "policy_type": "complaint",
        "title": "投诉升级处理规则",
        "content": "投诉工单提交后 24 小时内首次响应，如涉及配送或售后争议会升级人工专员处理。",
        "applies_to_category": "",
        "applies_to_status": "",
        "priority": 4,
    },
    {
        "policy_id": "PL0005",
        "policy_type": "shipping",
        "title": "家居大件发货说明",
        "content": "家居大件商品通常在支付后 48 小时内发货，偏远地区配送时效会顺延。",
        "applies_to_category": "家居",
        "applies_to_status": "已支付,待发货",
        "priority": 5,
    },
]


# 做什么：封装结构化电商数据访问能力。
# 为什么：让业务层只依赖稳定方法，不需要感知底层是 SQLAlchemy 还是具体 MySQL 表结构。
class CommerceStore:
    # 做什么：初始化 SQLAlchemy 版业务数据层。
    # 为什么：统一管理 MySQL 连接、建表、种子数据和后续查询入口。
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        seed_demo_data: bool = True,
        charset: str = "utf8mb4",
        connect_timeout: int = 5,
    ) -> None:
        # 做什么：保存数据库主机。
        # 为什么：后续构建 SQLAlchemy 连接 URL 需要复用。
        self.host = host
        # 做什么：保存数据库端口。
        # 为什么：后续构建 SQLAlchemy 连接 URL 需要复用。
        self.port = port
        # 做什么：保存数据库用户名。
        # 为什么：后续建立数据库连接需要身份认证。
        self.user = user
        # 做什么：保存数据库密码。
        # 为什么：后续建立数据库连接需要身份认证。
        self.password = password
        # 做什么：保存数据库名。
        # 为什么：后续建库、建表和查询都依赖该名称。
        self.database = database
        # 做什么：记录是否需要写入演示数据。
        # 为什么：便于在测试或生产场景灵活控制是否灌入种子数据。
        self.seed_demo_data = seed_demo_data
        # 做什么：保存字符集。
        # 为什么：保证中文商品和订单数据读写正常。
        self.charset = charset
        # 做什么：保存连接超时秒数。
        # 为什么：避免数据库不可达时请求长期挂起。
        self.connect_timeout = connect_timeout
        # 做什么：缓存 SQLAlchemy 引擎实例。
        # 为什么：避免每次查询重复创建连接池。
        self._engine = None
        # 做什么：缓存会话工厂。
        # 为什么：统一创建数据库会话。
        self._session_factory: Optional[sessionmaker[Session]] = None

    # 做什么：初始化数据库、表结构和演示数据。
    # 为什么：确保服务启动后工具查询能直接命中真实 MySQL 数据。
    def initialize(self) -> None:
        self._ensure_database()
        self._engine = create_engine(
            self._database_url(),
            pool_pre_ping=True,
            future=True,
            connect_args={"connect_timeout": self.connect_timeout},
        )
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self._engine)
        if self.seed_demo_data:
            self._seed_demo_data()

    # 做什么：返回当前数据层统计信息。
    # 为什么：便于健康检查和调试确认数据是否真的来自 MySQL。
    def stats(self) -> Dict[str, Any]:
        with self._session() as session:
            return {
                "backend": "mysql+sqlalchemy",
                "database": self.database,
                "products": self._count_table(session, Product),
                "orders": self._count_table(session, Order),
                "order_items": self._count_table(session, OrderItem),
                "payment_transactions": self._count_table(session, PaymentTransaction),
                "logistics_events": self._count_table(session, LogisticsEvent),
                "after_sales_tickets": self._count_table(session, AfterSalesTicket),
                "service_policies": self._count_table(session, ServicePolicy),
            }

    # 做什么：搜索商品。
    # 为什么：为商品检索接口和导购工具提供真实商品库查询能力。
    def search_products(
        self,
        query: str = "",
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        normalized_limit = self._normalize_limit(limit, 20)
        terms = self._extract_search_terms(query)
        with self._session() as session:
            products = self._query_products(session, category, min_price, max_price)
            ranked = sorted(
                products,
                key=lambda item: self._score_product(item, terms, query, max_price),
                reverse=True,
            )
            return [self._product_to_dict(item) for item in ranked[:normalized_limit]]

    # 做什么：获取商品详情。
    # 为什么：为单品详情、规格追问和活动说明提供完整商品信息。
    def get_product_detail(self, product_id: str) -> Optional[Dict[str, Any]]:
        if not product_id:
            return None
        with self._session() as session:
            product = session.get(Product, product_id)
            if product is None:
                return None
            payload = self._product_to_dict(product)
            payload["promotions"] = self.list_active_promotions(product_id=product_id, limit=5)
            return payload

    # 做什么：推荐商品。
    # 为什么：让导购场景能基于预算、类目和关键词做更贴近用户诉求的候选推荐。
    def recommend_products(
        self,
        query: str,
        category: Optional[str] = None,
        budget: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        inferred_category = category or self._extract_category(query)
        primary = self.search_products(query=query, category=inferred_category, max_price=budget, limit=limit)
        if primary:
            return primary
        # 做什么：在严格预算无结果时适度放宽价格上限。
        # 为什么：避免因为促销前后价差导致推荐完全为空。
        relaxed_budget = budget * 1.15 if budget else None
        fallback = self.search_products(query=query, category=inferred_category, max_price=relaxed_budget, limit=limit)
        if fallback:
            return fallback
        return self.list_category_hot_products(category=inferred_category, limit=limit)

    # 做什么：按价格带搜索商品。
    # 为什么：为预算区间型查询提供直接入口。
    def search_price_band_products(
        self,
        query: str = "",
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        return self.search_products(query=query, category=category, min_price=min_price, max_price=max_price, limit=limit)

    # 做什么：列出类目热销商品。
    # 为什么：在搜索词不明确时提供兜底候选。
    def list_category_hot_products(self, category: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        normalized_limit = self._normalize_limit(limit, 20)
        with self._session() as session:
            stmt = select(Product)
            if category:
                stmt = stmt.where(Product.category == category)
            stmt = stmt.order_by(desc(Product.sales_count), desc(Product.rating), Product.price.asc()).limit(normalized_limit)
            return [self._product_to_dict(item) for item in session.scalars(stmt).all()]

    # 做什么：推荐礼品商品。
    # 为什么：送礼场景往往需求模糊，需要结合收礼对象和预算给出候选。
    def recommend_gifts(
        self,
        query: str,
        recipient: str = "",
        category: Optional[str] = None,
        budget: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        enriched_query = " ".join(part for part in [query, recipient, "送礼"] if part).strip()
        return self.recommend_products(query=enriched_query, category=category, budget=budget, limit=limit)

    # 做什么：比较多个商品。
    # 为什么：让导购 Agent 能直接给出结构化横向对比结果。
    def compare_products(self, product_ids: List[str]) -> List[Dict[str, Any]]:
        if not product_ids:
            return []
        with self._session() as session:
            stmt = select(Product).where(Product.product_id.in_(product_ids))
            products = {item.product_id: item for item in session.scalars(stmt).all()}
            return [self._product_to_dict(products[product_id]) for product_id in product_ids if product_id in products]

    # 做什么：获取库存快照。
    # 为什么：为库存查询工具提供简洁稳定的库存结果。
    def get_inventory_snapshot(self, product_ids: List[str]) -> List[Dict[str, Any]]:
        if not product_ids:
            return []
        with self._session() as session:
            stmt = select(Product).where(Product.product_id.in_(product_ids))
            rows = session.scalars(stmt).all()
            return [
                {
                    "product_id": item.product_id,
                    "name": item.name,
                    "stock": item.stock,
                    "in_stock": item.stock > 0,
                }
                for item in rows
            ]

    # 做什么：列出当前有效促销。
    # 为什么：让导购和订单工具都能读取当前可用活动。
    def list_active_promotions(
        self,
        category: Optional[str] = None,
        product_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        normalized_limit = self._normalize_limit(limit, 20)
        now = datetime.now()
        with self._session() as session:
            # 做什么：先按活动时间窗口筛选。
            # 为什么：优先返回当前时间真正生效的活动。
            strict_stmt = select(Promotion).where(
                Promotion.status == "active",
                Promotion.starts_at <= now,
                Promotion.ends_at >= now,
            )
            if category:
                strict_stmt = strict_stmt.where(or_(Promotion.applies_to_category == "", Promotion.applies_to_category == category))
            if product_id:
                strict_stmt = strict_stmt.where(or_(Promotion.applies_to_product_id == "", Promotion.applies_to_product_id == product_id))
            strict_stmt = strict_stmt.order_by(Promotion.priority.asc(), Promotion.min_spend.asc()).limit(normalized_limit)
            strict_rows = session.scalars(strict_stmt).all()
            if strict_rows:
                return [self._promotion_to_dict(item) for item in strict_rows]

            # 做什么：当运行环境时间与演示数据时间轴不一致时退回到 active 状态筛选。
            # 为什么：避免活动数据因为系统时钟不一致而整体查空，影响导购演示。
            fallback_stmt = select(Promotion).where(Promotion.status == "active")
            if category:
                fallback_stmt = fallback_stmt.where(or_(Promotion.applies_to_category == "", Promotion.applies_to_category == category))
            if product_id:
                fallback_stmt = fallback_stmt.where(or_(Promotion.applies_to_product_id == "", Promotion.applies_to_product_id == product_id))
            fallback_stmt = fallback_stmt.order_by(Promotion.priority.asc(), Promotion.min_spend.asc()).limit(normalized_limit)
            return [self._promotion_to_dict(item) for item in session.scalars(fallback_stmt).all()]

    # 做什么：查询订单详情。
    # 为什么：订单、支付、物流和售后工具都要先基于真实订单事实工作。
    def lookup_order(self, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not order_id:
            return None
        with self._session() as session:
            order = self._get_order_entity(session, order_id, user_id)
            return self._order_to_dict(order) if order else None

    # 做什么：查询最近订单。
    # 为什么：当用户没有明确给出订单号时，可先用最近订单做上下文兜底。
    def recent_orders(self, user_id: str, limit: int = 2) -> List[Dict[str, Any]]:
        return self.list_user_orders(user_id=user_id, status=None, limit=limit)

    # 做什么：列出用户订单。
    # 为什么：为最近订单工具和上下文构建提供订单列表。
    def list_user_orders(self, user_id: str, status: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        if not user_id:
            return []
        normalized_limit = self._normalize_limit(limit, 20)
        with self._session() as session:
            stmt = (
                select(Order)
                .options(joinedload(Order.items))
                .where(Order.user_id == user_id)
                .order_by(desc(Order.created_at))
                .limit(normalized_limit)
            )
            if status:
                stmt = stmt.where(Order.status == status)
            return [self._order_to_dict(item) for item in session.scalars(stmt).unique().all()]

    # 做什么：获取订单明细。
    # 为什么：为订单商品核对工具返回结构化明细。
    def get_order_items(self, order_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._session() as session:
            order = self._get_order_entity(session, order_id, user_id)
            if order is None:
                return []
            return [self._order_item_to_dict(item) for item in sorted(order.items, key=lambda item: item.item_index)]

    # 做什么：获取订单时间线。
    # 为什么：让订单工具能返回从下单到签收的完整节点。
    def get_order_timeline(self, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._session() as session:
            order = self._get_order_entity(session, order_id, user_id)
            if order is None:
                return None
            events: List[Dict[str, Any]] = []
            self._append_timeline_event(events, order.created_at, "已下单", "订单已创建")
            self._append_timeline_event(events, order.paid_at, "已支付", f"支付方式：{order.payment_method}")
            self._append_timeline_event(events, order.shipped_at, "已发货", f"物流公司：{order.shipping_company or '待分配'}")
            self._append_timeline_event(events, order.delivered_at, "已签收", "订单已签收")
            for event in sorted(order.logistics_events, key=lambda item: item.event_time):
                events.append(
                    {
                        "event_time": self._format_datetime(event.event_time),
                        "status": event.status,
                        "detail": event.detail,
                    }
                )
            events.sort(key=lambda item: item["event_time"])
            return {"order_id": order.order_id, "status": order.status, "timeline": events}

    # 做什么：获取物流快照。
    # 为什么：为物流工具提供状态、物流商和轨迹的集中结果。
    def get_logistics_snapshot(self, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._session() as session:
            order = self._get_order_entity(session, order_id, user_id)
            if order is None:
                return None
            return {
                "order_id": order.order_id,
                "shipping_status": order.shipping_status,
                "shipping_company": order.shipping_company,
                "tracking_no": order.tracking_no,
                "shipped_at": self._format_datetime(order.shipped_at),
                "delivered_at": self._format_datetime(order.delivered_at),
                "events": [
                    {
                        "event_time": self._format_datetime(event.event_time),
                        "status": event.status,
                        "detail": event.detail,
                    }
                    for event in sorted(order.logistics_events, key=lambda item: item.event_time)
                ],
            }

    # 做什么：获取支付快照。
    # 为什么：让支付查询读取真实交易流水而不是模型猜测。
    def get_payment_snapshot(self, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._session() as session:
            order = self._get_order_entity(session, order_id, user_id)
            if order is None:
                return None
            transactions = sorted(order.payment_transactions, key=lambda item: item.transacted_at, reverse=True)
            latest = transactions[0] if transactions else None
            return {
                "order_id": order.order_id,
                "payment_method": order.payment_method,
                "payment_amount": order.payment_amount,
                "paid_at": self._format_datetime(order.paid_at),
                "latest_transaction": self._payment_to_dict(latest) if latest else None,
                "transactions": [self._payment_to_dict(item) for item in transactions],
            }

    # 做什么：获取发票快照。
    # 为什么：为发票查询工具提供订单发票相关事实。
    def get_invoice_snapshot(self, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._session() as session:
            order = self._get_order_entity(session, order_id, user_id)
            if order is None:
                return None
            return {
                "order_id": order.order_id,
                "invoice_title": order.invoice_title,
                "payment_status": order.status,
                "payment_amount": order.payment_amount,
                "paid_at": self._format_datetime(order.paid_at),
                "coupon_code": order.coupon_code,
            }

    # 做什么：查询优惠券使用记录。
    # 为什么：让订单 Agent 能说明某张券被哪些订单使用过。
    def lookup_coupon_usage(self, coupon_code: str, user_id: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        if not coupon_code:
            return {"coupon_code": coupon_code, "usage_count": 0, "orders": []}
        normalized_limit = self._normalize_limit(limit, 20)
        with self._session() as session:
            stmt = select(Order).where(Order.coupon_code == coupon_code).order_by(desc(Order.created_at)).limit(normalized_limit)
            if user_id:
                stmt = stmt.where(Order.user_id == user_id)
            orders = session.scalars(stmt).all()
            return {
                "coupon_code": coupon_code,
                "usage_count": len(orders),
                "orders": [
                    {
                        "order_id": item.order_id,
                        "user_id": item.user_id,
                        "status": item.status,
                        "payment_amount": item.payment_amount,
                        "created_at": self._format_datetime(item.created_at),
                    }
                    for item in orders
                ],
            }

    # 做什么：获取订单对应售后工单。
    # 为什么：售后 Agent 需要直接读到最新售后工单事实。
    def get_after_sales_ticket(self, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not order_id:
            return None
        with self._session() as session:
            stmt = select(AfterSalesTicket).where(AfterSalesTicket.order_id == order_id).order_by(desc(AfterSalesTicket.updated_at))
            if user_id:
                stmt = stmt.where(AfterSalesTicket.user_id == user_id)
            ticket = session.scalars(stmt.limit(1)).first()
            return self._ticket_to_dict(ticket) if ticket else None

    # 做什么：列出用户售后工单。
    # 为什么：让售后历史工具和投诉汇总工具读取用户维度售后记录。
    def list_after_sales_tickets(self, user_id: str, limit: int = 5, ticket_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if not user_id:
            return []
        normalized_limit = self._normalize_limit(limit, 20)
        with self._session() as session:
            stmt = select(AfterSalesTicket).where(AfterSalesTicket.user_id == user_id).order_by(desc(AfterSalesTicket.updated_at)).limit(normalized_limit)
            if ticket_type:
                stmt = stmt.where(AfterSalesTicket.ticket_type == ticket_type)
            return [self._ticket_to_dict(item) for item in session.scalars(stmt).all()]

    # 做什么：获取退款状态。
    # 为什么：退款查询只关心退款类工单及其金额和状态。
    def get_refund_status(self, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not order_id:
            return None
        with self._session() as session:
            stmt = (
                select(AfterSalesTicket)
                .where(AfterSalesTicket.order_id == order_id, AfterSalesTicket.ticket_type == "refund")
                .order_by(desc(AfterSalesTicket.updated_at))
            )
            if user_id:
                stmt = stmt.where(AfterSalesTicket.user_id == user_id)
            ticket = session.scalars(stmt.limit(1)).first()
            if ticket is None:
                return None
            return {
                "order_id": order_id,
                "ticket_id": ticket.ticket_id,
                "status": ticket.status,
                "refund_amount": ticket.refund_amount,
                "updated_at": self._format_datetime(ticket.updated_at),
                "resolution_note": ticket.resolution_note,
            }

    # 做什么：评估退货资格。
    # 为什么：售后 Agent 需要基于真实签收时间和售后状态做规则判断。
    def evaluate_return_eligibility(self, order_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._session() as session:
            order = self._get_order_entity(session, order_id, user_id)
            if order is None:
                return {"eligible": False, "reason": "未找到对应订单"}
            if order.delivered_at is None:
                return {"eligible": False, "reason": "订单尚未签收，暂不支持发起退货"}
            if order.after_sales_status in {"退款完成", "退款中"}:
                return {"eligible": False, "reason": "该订单已有退款流程，请勿重复申请"}
            within_days = datetime.now() - order.delivered_at <= timedelta(days=7)
            return {
                "eligible": within_days,
                "reason": "订单签收 7 天内且无重复退款记录" if within_days else "已超过 7 天无理由退货时效",
                "delivered_at": self._format_datetime(order.delivered_at),
            }

    # 做什么：评估换货资格。
    # 为什么：售后 Agent 需要基于真实签收时间和售后状态判断是否还能换货。
    def evaluate_exchange_eligibility(self, order_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._session() as session:
            order = self._get_order_entity(session, order_id, user_id)
            if order is None:
                return {"eligible": False, "reason": "未找到对应订单"}
            if order.delivered_at is None:
                return {"eligible": False, "reason": "订单尚未签收，暂不支持发起换货"}
            if order.after_sales_status in {"换货中", "换货完成"}:
                return {"eligible": False, "reason": "该订单已有换货流程，请勿重复申请"}
            within_days = datetime.now() - order.delivered_at <= timedelta(days=15)
            return {
                "eligible": within_days,
                "reason": "订单签收 15 天内且无重复换货记录" if within_days else "已超过质量问题换货时效",
                "delivered_at": self._format_datetime(order.delivered_at),
            }

    # 做什么：查询服务政策。
    # 为什么：让售后 Agent 在规则类问题上直接查询本地政策数据。
    def lookup_service_policies(
        self,
        policy_type: Optional[str] = None,
        keyword: str = "",
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        normalized_limit = self._normalize_limit(limit, 20)
        with self._session() as session:
            stmt = select(ServicePolicy)
            if policy_type:
                stmt = stmt.where(ServicePolicy.policy_type == policy_type)
            if category:
                stmt = stmt.where(or_(ServicePolicy.applies_to_category == "", ServicePolicy.applies_to_category == category))
            if keyword:
                like_expr = f"%{keyword}%"
                stmt = stmt.where(or_(ServicePolicy.title.like(like_expr), ServicePolicy.content.like(like_expr)))
            stmt = stmt.order_by(ServicePolicy.priority.asc()).limit(normalized_limit)
            return [self._policy_to_dict(item) for item in session.scalars(stmt).all()]

    # 做什么：查询投诉摘要。
    # 为什么：投诉和升级场景需要直接读到投诉工单记录。
    def get_complaint_summary(self, order_id: Optional[str] = None, user_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        normalized_limit = self._normalize_limit(limit, 20)
        with self._session() as session:
            stmt = (
                select(AfterSalesTicket)
                .where(AfterSalesTicket.ticket_type == "complaint")
                .order_by(desc(AfterSalesTicket.updated_at))
                .limit(normalized_limit)
            )
            if order_id:
                stmt = stmt.where(AfterSalesTicket.order_id == order_id)
            if user_id:
                stmt = stmt.where(AfterSalesTicket.user_id == user_id)
            return [self._ticket_to_dict(item) for item in session.scalars(stmt).all()]

    # 做什么：提取订单号。
    # 为什么：便于从自然语言里识别订单查询对象。
    def extract_order_id(self, message: str) -> Optional[str]:
        matched = re.search(r"(MP\d{8,})", message, re.IGNORECASE)
        return matched.group(1).upper() if matched else None

    # 做什么：构建商品上下文文本。
    # 为什么：在主对话链路里把真实商品事实注入给 LLM，降低幻觉。
    def build_product_context(self, message: str) -> str:
        category = self._extract_category(message)
        budget = self._extract_budget(message)
        products = self.recommend_products(query=message, category=category, budget=budget, limit=3)
        if not products:
            return ""
        lines = ["[商品库结果]"]
        for index, item in enumerate(products, start=1):
            lines.append(
                f"{index}. {item['name']} | 类目: {item['category']} | 品牌: {item['brand']} | 价格: {item['price']} 元 | 评分: {item['rating']}"
            )
            lines.append(f"   标签: {item['tags']}")
            lines.append(f"   简介: {item['summary']}")
        lines.append("请严格基于以上商品事实推荐或对比，不要编造不存在的规格、价格和活动。")
        return "\n".join(lines)

    # 做什么：构建订单上下文文本。
    # 为什么：在主对话链路里把真实订单、物流和售后事实注入给 LLM。
    def build_order_context(self, message: str, user_id: str) -> str:
        order_id = self.extract_order_id(message)
        if order_id:
            order = self.lookup_order(order_id=order_id, user_id=user_id)
            return self._format_order_context(order) if order else ""
        recent_orders = self.recent_orders(user_id=user_id, limit=2)
        if not recent_orders:
            return ""
        lines = ["[最近订单摘要]"]
        for index, item in enumerate(recent_orders, start=1):
            lines.append(
                f"{index}. 订单号: {item['order_id']} | 状态: {item['status']} | 物流: {item['shipping_status']} | 售后: {item['after_sales_status']}"
            )
        lines.append("用户未提供明确订单号时，只能基于最近订单摘要做保守说明。")
        return "\n".join(lines)

    # 做什么：确保数据库存在。
    # 为什么：SQLAlchemy 建表前必须先保证目标数据库已创建。
    def _ensure_database(self) -> None:
        safe_db_name = self._safe_identifier(self.database)
        admin_url = URL.create(
            "mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=None,
            query={"charset": self.charset},
        )
        admin_engine = create_engine(
            admin_url,
            pool_pre_ping=True,
            future=True,
            connect_args={"connect_timeout": self.connect_timeout},
            isolation_level="AUTOCOMMIT",
        )
        try:
            with admin_engine.connect() as conn:
                conn.execute(
                    text(
                        f"CREATE DATABASE IF NOT EXISTS `{safe_db_name}` "
                        f"CHARACTER SET {self.charset} COLLATE {self.charset}_unicode_ci"
                    )
                )
        finally:
            admin_engine.dispose()

    # 做什么：写入演示数据。
    # 为什么：保证本地和测试环境能直接拿到足够多的真实商品、订单和交易记录。
    def _seed_demo_data(self) -> None:
        with self._session() as session:
            for row in DEMO_PRODUCTS:
                session.merge(Product(**row))
            for row in DEMO_PROMOTIONS:
                session.merge(Promotion(**self._normalize_datetime_fields(row, ["starts_at", "ends_at"])))
            for row in DEMO_ORDERS:
                order_payload = {key: value for key, value in row.items() if key != "items"}
                session.merge(
                    Order(
                        **self._normalize_datetime_fields(
                            order_payload,
                            ["created_at", "paid_at", "shipped_at", "delivered_at"],
                        )
                    )
                )
            session.flush()
            for row in DEMO_ORDERS:
                for index, item in enumerate(row["items"], start=1):
                    existing = session.scalar(
                        select(OrderItem).where(OrderItem.order_id == row["order_id"], OrderItem.item_index == index)
                    )
                    payload = {
                        "order_id": row["order_id"],
                        "product_id": item["product_id"],
                        "product_name_snapshot": item["product_name_snapshot"],
                        "sku_snapshot": item["sku_snapshot"],
                        "quantity": item["quantity"],
                        "unit_price": item["unit_price"],
                        "item_index": index,
                    }
                    if existing:
                        for key, value in payload.items():
                            setattr(existing, key, value)
                    else:
                        session.add(OrderItem(**payload))
            for row in DEMO_PAYMENT_TRANSACTIONS:
                session.merge(
                    PaymentTransaction(
                        **self._normalize_datetime_fields(row, ["transacted_at"])
                    )
                )
            for row in DEMO_LOGISTICS_EVENTS:
                session.merge(
                    LogisticsEvent(
                        **self._normalize_datetime_fields(row, ["event_time"])
                    )
                )
            for row in DEMO_AFTER_SALES_TICKETS:
                session.merge(
                    AfterSalesTicket(
                        **self._normalize_datetime_fields(row, ["requested_at", "updated_at"])
                    )
                )
            for row in DEMO_SERVICE_POLICIES:
                session.merge(ServicePolicy(**row))
            session.commit()

    # 做什么：返回数据库 URL。
    # 为什么：统一让引擎和管理连接都复用相同连接信息。
    def _database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
            query={"charset": self.charset},
        )

    # 做什么：创建会话上下文。
    # 为什么：统一处理查询提交和异常回滚。
    @contextmanager
    def _session(self) -> Generator[Session, None, None]:
        if self._session_factory is None:
            raise RuntimeError("CommerceStore 尚未初始化")
        session = self._session_factory()
        try:
            yield session
        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()

    # 做什么：查询商品候选集。
    # 为什么：把数据库过滤逻辑统一收口，便于搜索和推荐复用。
    def _query_products(
        self,
        session: Session,
        category: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
    ) -> List[Product]:
        stmt = select(Product)
        if category:
            stmt = stmt.where(Product.category == category)
        if min_price is not None:
            stmt = stmt.where(Product.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Product.price <= max_price)
        stmt = stmt.order_by(desc(Product.is_featured), desc(Product.rating), desc(Product.sales_count))
        return session.scalars(stmt).all()

    # 做什么：获取订单实体。
    # 为什么：让多个订单类方法共享统一的订单加载和用户归属校验逻辑。
    def _get_order_entity(self, session: Session, order_id: str, user_id: Optional[str]) -> Optional[Order]:
        if not order_id:
            return None
        stmt = (
            select(Order)
            .options(
                joinedload(Order.items),
                joinedload(Order.payment_transactions),
                joinedload(Order.logistics_events),
                joinedload(Order.after_sales_tickets),
            )
            .where(Order.order_id == order_id)
        )
        if user_id:
            stmt = stmt.where(Order.user_id == user_id)
        return session.scalars(stmt).unique().first()

    # 做什么：统计表记录数。
    # 为什么：健康检查需要快速确认各类种子数据是否落库成功。
    def _count_table(self, session: Session, model: Any) -> int:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)

    # 做什么：将 ORM 商品对象转为字典。
    # 为什么：对外屏蔽 ORM 细节，统一工具层返回格式。
    def _product_to_dict(self, product: Product) -> Dict[str, Any]:
        return {
            "product_id": product.product_id,
            "name": product.name,
            "category": product.category,
            "brand": product.brand,
            "price": self._to_float(product.price),
            "original_price": self._to_float(product.original_price),
            "stock": int(product.stock),
            "rating": self._to_float(product.rating),
            "sales_count": int(product.sales_count),
            "tags": product.tags,
            "summary": product.summary,
            "specs": self._loads_json(product.specs_json),
            "is_featured": bool(product.is_featured),
        }

    # 做什么：将促销对象转为字典。
    # 为什么：统一工具层活动查询返回结构。
    def _promotion_to_dict(self, promotion: Promotion) -> Dict[str, Any]:
        return {
            "promotion_id": promotion.promotion_id,
            "title": promotion.title,
            "description": promotion.description,
            "applies_to_category": promotion.applies_to_category,
            "applies_to_product_id": promotion.applies_to_product_id,
            "coupon_code": promotion.coupon_code,
            "discount_label": promotion.discount_label,
            "min_spend": self._to_float(promotion.min_spend),
            "starts_at": self._format_datetime(promotion.starts_at),
            "ends_at": self._format_datetime(promotion.ends_at),
            "status": promotion.status,
            "priority": promotion.priority,
        }

    # 做什么：将订单对象转为字典。
    # 为什么：统一订单查询、上下文构建和工具层的返回格式。
    def _order_to_dict(self, order: Order) -> Dict[str, Any]:
        return {
            "order_id": order.order_id,
            "user_id": order.user_id,
            "status": order.status,
            "total_amount": self._to_float(order.total_amount),
            "payment_amount": self._to_float(order.payment_amount),
            "payment_method": order.payment_method,
            "shipping_status": order.shipping_status,
            "shipping_company": order.shipping_company,
            "tracking_no": order.tracking_no,
            "created_at": self._format_datetime(order.created_at),
            "paid_at": self._format_datetime(order.paid_at),
            "shipped_at": self._format_datetime(order.shipped_at),
            "delivered_at": self._format_datetime(order.delivered_at),
            "coupon_code": order.coupon_code,
            "address_summary": order.address_summary,
            "invoice_title": order.invoice_title,
            "after_sales_status": order.after_sales_status,
            "items": [self._order_item_to_dict(item) for item in sorted(order.items, key=lambda item: item.item_index)],
        }

    # 做什么：将订单明细对象转为字典。
    # 为什么：统一订单商品明细返回结构。
    def _order_item_to_dict(self, item: OrderItem) -> Dict[str, Any]:
        return {
            "product_id": item.product_id,
            "product_name_snapshot": item.product_name_snapshot,
            "sku_snapshot": item.sku_snapshot,
            "quantity": int(item.quantity),
            "unit_price": self._to_float(item.unit_price),
        }

    # 做什么：将支付交易对象转为字典。
    # 为什么：统一支付流水展示格式。
    def _payment_to_dict(self, payment: Optional[PaymentTransaction]) -> Optional[Dict[str, Any]]:
        if payment is None:
            return None
        return {
            "transaction_id": payment.transaction_id,
            "transaction_type": payment.transaction_type,
            "channel": payment.channel,
            "amount": self._to_float(payment.amount),
            "status": payment.status,
            "transacted_at": self._format_datetime(payment.transacted_at),
            "channel_reference": payment.channel_reference,
            "note": payment.note,
        }

    # 做什么：将售后工单对象转为字典。
    # 为什么：统一退款、换货和投诉返回结构。
    def _ticket_to_dict(self, ticket: AfterSalesTicket) -> Dict[str, Any]:
        return {
            "ticket_id": ticket.ticket_id,
            "order_id": ticket.order_id,
            "user_id": ticket.user_id,
            "ticket_type": ticket.ticket_type,
            "status": ticket.status,
            "reason": ticket.reason,
            "refund_amount": self._to_float(ticket.refund_amount),
            "requested_at": self._format_datetime(ticket.requested_at),
            "updated_at": self._format_datetime(ticket.updated_at),
            "resolution_note": ticket.resolution_note,
        }

    # 做什么：将服务政策对象转为字典。
    # 为什么：统一规则查询结果结构。
    def _policy_to_dict(self, policy: ServicePolicy) -> Dict[str, Any]:
        return {
            "policy_id": policy.policy_id,
            "policy_type": policy.policy_type,
            "title": policy.title,
            "content": policy.content,
            "applies_to_category": policy.applies_to_category,
            "applies_to_status": policy.applies_to_status,
            "priority": policy.priority,
        }

    # 做什么：给商品打分。
    # 为什么：在 MySQL 提供候选后，再用业务规则做轻量相关性排序。
    def _score_product(self, product: Product, terms: List[str], raw_query: str, budget: Optional[float]) -> float:
        haystacks = [
            product.name.lower(),
            product.tags.lower(),
            product.summary.lower(),
            product.specs_json.lower(),
        ]
        score = float(product.rating) * 10 + min(int(product.sales_count), 10000) / 100
        if product.is_featured:
            score += 2
        if budget is not None and float(product.price) <= budget:
            score += 6
        # 做什么：对命中名称、标签和规格的商品额外加权。
        # 为什么：让“续航好的手机”这类自然语言更容易匹配到合适商品。
        for term in terms:
            lowered = term.lower()
            if lowered in product.name.lower():
                score += 15
            if lowered in product.tags.lower():
                score += 10
            if lowered in product.summary.lower():
                score += 7
            if lowered in product.specs_json.lower():
                score += 5
        if raw_query and "续航" in raw_query and "battery" in product.specs_json.lower():
            score += 12
        if raw_query and "手机" in raw_query and "手机" in product.tags:
            score += 10
        return score

    # 做什么：归一化时间字段。
    # 为什么：让种子数据在写入 ORM 前统一转成 datetime 或 None。
    @staticmethod
    def _normalize_datetime_fields(payload: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        normalized = dict(payload)
        for field_name in fields:
            value = normalized.get(field_name)
            if value in ("", None):
                normalized[field_name] = None
            elif isinstance(value, str):
                normalized[field_name] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return normalized

    # 做什么：安全解析 JSON。
    # 为什么：避免坏数据导致商品详情读取异常。
    @staticmethod
    def _loads_json(raw: str) -> Dict[str, Any]:
        try:
            value = json.loads(raw or "{}")
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    # 做什么：格式化日期时间。
    # 为什么：统一所有工具返回的时间字符串格式。
    @staticmethod
    def _format_datetime(value: Optional[datetime]) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""

    # 做什么：把数值转为 float。
    # 为什么：避免 Decimal 等类型直接透传到接口层。
    @staticmethod
    def _to_float(value: Any) -> float:
        if isinstance(value, Decimal):
            return float(value)
        return float(value or 0.0)

    # 做什么：限制返回条数。
    # 为什么：避免工具或接口一次拉取过多结果。
    @staticmethod
    def _normalize_limit(limit: int, max_limit: int) -> int:
        return max(1, min(int(limit), max_limit))

    # 做什么：安全校验数据库标识符。
    # 为什么：避免在建库时拼接非法数据库名。
    @staticmethod
    def _safe_identifier(value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_]+", value):
            raise ValueError(f"非法数据库标识符: {value}")
        return value

    # 做什么：向时间线追加事件。
    # 为什么：减少时间线构建时的重复空值判断。
    @staticmethod
    def _append_timeline_event(events: List[Dict[str, Any]], event_time: Optional[datetime], status: str, detail: str) -> None:
        if event_time:
            events.append({"event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"), "status": status, "detail": detail})

    # 做什么：从用户消息提取预算上限。
    # 为什么：预算是导购推荐里最常见的硬约束之一。
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
    # 为什么：提升导购检索相关性，减少跨类目噪声。
    @staticmethod
    def _extract_category(message: str) -> Optional[str]:
        categories = {
            "手机": "数码",
            "耳机": "数码",
            "笔记本": "数码",
            "投影": "数码",
            "手表": "数码",
            "书桌": "家居",
            "四件套": "家居",
            "露营椅": "家居",
            "水壶": "小家电",
            "咖啡机": "小家电",
            "净化器": "小家电",
            "豆浆机": "小家电",
            "吹风机": "个护",
            "洁面": "个护",
            "凝珠": "日用",
        }
        for keyword, category in categories.items():
            if keyword in message:
                return category
        return None

    # 做什么：提取商品搜索关键词。
    # 为什么：把预算词、语气词等噪声剔除后，提升商品匹配命中率。
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
            "快充",
        ]
        terms: List[str] = []
        for term in hint_terms:
            if term in message and term not in terms:
                terms.append(term)
        ascii_terms = re.findall(r"[A-Za-z0-9]{2,}", message)
        for term in ascii_terms:
            if term.isdigit():
                continue
            if term.lower() in {"mp", "mallpilot", "2026"}:
                continue
            if term not in terms:
                terms.append(term)
        return terms[:6]

    # 做什么：格式化订单事实为 prompt 上下文。
    # 为什么：让 Agent 直接引用物流、支付和售后状态，避免凭空猜测。
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
