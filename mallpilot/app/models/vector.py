from typing import Any

from sqlalchemy import JSON
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import TypeDecorator


class Vector(TypeDecorator[list[float] | None]):
    # SQLite 测试中使用 JSON 存储，PostgreSQL 编译时输出 pgvector 类型。
    impl = JSON
    # SQLAlchemy 缓存编译结果所需标记。
    cache_ok = True

    # 初始化向量字段类型。
    def __init__(self, dimensions: int):
        # 向量维度，需要与 embedding 模型输出保持一致。
        self.dimensions = dimensions
        super().__init__()

    # 绑定参数前校验向量格式。
    def process_bind_param(self, value: Any, dialect: Any) -> list[float] | None:
        if value is None:
            return None

        # pgvector 和 SQLite 测试都使用 Python list 作为内部表示。
        return [float(item) for item in value]

    # 读取结果后保持 list[float] 表示。
    def process_result_value(self, value: Any, dialect: Any) -> list[float] | None:
        if value is None:
            return None

        # PostgreSQL 驱动或 SQLite JSON 都可能返回可迭代数值。
        return [float(item) for item in value]


# PostgreSQL 方言下把字段编译成 pgvector 的 VECTOR(n)。
@compiles(Vector, "postgresql")
def compile_vector_postgresql(type_: Vector, compiler: Any, **kwargs: Any) -> str:
    return f"VECTOR({type_.dimensions})"
