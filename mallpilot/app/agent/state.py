from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowContext:
    # 当前会话 ID。
    chat_id: str
    # 当前轮次 ID。
    turn_id: str
    # 用户输入。
    message: str
    # Router 输出的实体。
    entities: dict[str, Any] = field(default_factory=dict)
    # 附件列表。
    attachments: list[dict[str, Any]] = field(default_factory=list)
