from typing import Any

from pgvector.sqlalchemy import Vector as PgVector
from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


class Vector(TypeDecorator[Any]):
    # 默认底层类型使用 pgvector，PostgreSQL 会直接复用官方向量类型实现。
    impl = PgVector
    # 标记该自定义类型可安全参与 SQLAlchemy 编译缓存。
    cache_ok = True

    # 初始化向量字段类型。
    def __init__(self, dimensions: int):
        # 记录向量维度，必须与 embedding 模型输出维度一致。
        self.dimensions = dimensions
        super().__init__()

    # 按数据库方言选择实际底层类型。
    def load_dialect_impl(self, dialect: Any):
        if dialect.name == "sqlite":
            # SQLite 测试环境没有 pgvector，退化为 JSON 存储。
            return dialect.type_descriptor(JSON())
        # PostgreSQL 直接使用 pgvector 官方 SQLAlchemy 类型。
        return dialect.type_descriptor(PgVector(self.dimensions))

    # 在写入前统一把输入值规范成 float 列表。
    def process_bind_param(self, value: Any, dialect: Any) -> list[float] | None:
        if value is None:
            return None
        # 统一转换为 float，避免 int / Decimal 等类型混用。
        return [float(item) for item in value]

    # 在读取后统一返回 list[float]。
    def process_result_value(self, value: Any, dialect: Any) -> list[float] | None:
        if value is None:
            return None

        # SQLite JSON 回读通常已经是 list；PostgreSQL pgvector 回读可能是 list、tuple 或 numpy 数组。
        if isinstance(value, (list, tuple)):
            return [float(item) for item in value]

        # 兼容 numpy.ndarray 等可迭代对象。
        if hasattr(value, "tolist"):
            return [float(item) for item in value.tolist()]

        # 极端情况下数据库若返回单个数值，降级包装成单元素列表，避免 ORM 回读报错。
        return [float(value)]
