from collections import defaultdict

from mallpilot.app.agent.schemas import TraceEvent


class TraceService:
    # 初始化内存 Trace Store，后续任务替换为数据库实现。
    def __init__(self):
        # 按 turn_id 保存 Trace 事件。
        self._events_by_turn: dict[str, list[TraceEvent]] = defaultdict(list)

    # 记录 Trace 事件。
    def record(self, event: TraceEvent) -> None:
        self._events_by_turn[event.turn_id].append(event)

    # 查询某一轮的 Trace 事件。
    def list_events(self, turn_id: str) -> list[TraceEvent]:
        return list(self._events_by_turn.get(turn_id, []))
