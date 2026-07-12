from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from mallpilot.app.agent.schemas import ChatRequest
from mallpilot.app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


# 用户侧 Chat SSE 接口。
@router.post("/stream")
def stream_chat(request: ChatRequest) -> StreamingResponse:
    # 每次请求构建运行时服务，确保数据库 session 和 Trace 服务按请求生命周期工作。
    service = ChatService.from_runtime()
    return StreamingResponse(service.stream(request), media_type="text/event-stream")
