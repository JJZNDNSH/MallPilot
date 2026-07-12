from fastapi import FastAPI

from mallpilot.app.api.admin import router as admin_router
from mallpilot.app.api.chat import router as chat_router
from mallpilot.app.api.trace import router as trace_router


# 创建 FastAPI 应用，注册用户侧和后台侧路由。
def create_app() -> FastAPI:
    app = FastAPI(title="MallPilot", version="0.1.0")
    app.include_router(chat_router)
    app.include_router(trace_router)
    app.include_router(admin_router)
    return app


# FastAPI 默认应用实例。
app = create_app()
