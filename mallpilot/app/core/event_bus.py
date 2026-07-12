from mallpilot.app.agent.schemas import SseEvent


class EventBus:
    # 将业务事件序列化为 SSE 文本。
    def emit(self, event: SseEvent) -> str:
        payload = event.model_dump_json()
        return f"event: message\ndata: {payload}\n\n"
