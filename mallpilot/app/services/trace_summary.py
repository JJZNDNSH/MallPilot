from typing import Any

from mallpilot.app.agent.schemas import TraceEvent


# Trace 阶段展示顺序。
GROUP_ORDER = ["router", "retrieval", "rerank", "llm", "sse", "error", "other"]


# 构造空 Trace 摘要。
def build_empty_trace_summary(turn_id: str) -> dict[str, Any]:
    return {
        "turn_id": turn_id,
        "input": None,
        "event_count": 0,
        "error_count": 0,
        "total_duration_ms": 0,
        "groups": [],
        "events": [],
    }


# 根据事件类型判断观测阶段。
def trace_group_name(event: TraceEvent) -> str:
    if event.status == "error" or event.event_type.endswith(".error"):
        return "error"
    prefix = event.event_type.split(".", maxsplit=1)[0]
    if prefix in {"router", "retrieval", "rerank", "llm", "sse"}:
        return prefix
    return "other"


# 将 Trace 事件聚合成前端可直接渲染的 summary。
def build_trace_summary(turn_id: str, events: list[TraceEvent]) -> dict[str, Any]:
    if not events:
        return build_empty_trace_summary(turn_id)

    # 按事件时间排序，保证摘要中的事件顺序稳定。
    sorted_events = sorted(events, key=lambda event: event.timestamp)
    input_event = next((event for event in sorted_events if event.event_type == "user.message"), None)
    execution_events = [event for event in sorted_events if event.event_type != "user.message"]
    groups: dict[str, dict[str, Any]] = {}

    for event in execution_events:
        group_name = trace_group_name(event)
        if group_name not in groups:
            # 初始化阶段分组摘要。
            groups[group_name] = {
                "name": group_name,
                "event_count": 0,
                "error_count": 0,
                "duration_ms": 0,
                "status": "ok",
                "events": [],
            }

        group = groups[group_name]
        duration_ms = event.duration_ms or 0
        group["event_count"] += 1
        group["duration_ms"] += duration_ms
        group["events"].append(event.model_dump(mode="json"))
        if event.status == "error":
            # 错误事件会提升所在分组的错误状态。
            group["error_count"] += 1
            group["status"] = "error"

    # 按固定阶段顺序输出分组，避免依赖输入事件顺序。
    ordered_groups = [groups[name] for name in GROUP_ORDER if name in groups]
    return {
        "turn_id": turn_id,
        "input": _build_input_payload(input_event),
        "event_count": len(execution_events),
        "error_count": sum(1 for event in execution_events if event.status == "error"),
        "total_duration_ms": sum(event.duration_ms or 0 for event in execution_events),
        "groups": ordered_groups,
        "events": [event.model_dump(mode="json") for event in execution_events],
    }


# 构造顶部用户输入展示数据。
def _build_input_payload(event: TraceEvent | None) -> dict[str, Any] | None:
    if event is None:
        return None
    return {
        "message": event.payload.get("message", ""),
        "timestamp": event.timestamp.isoformat(),
    }
