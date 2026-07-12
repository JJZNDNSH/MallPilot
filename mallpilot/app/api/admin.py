from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

admin_router = APIRouter(prefix="/admin", tags=["admin"])
chat_router = APIRouter(tags=["chat-ui"])
OBSERVABILITY_ROOT = Path(__file__).resolve().parents[1] / "web" / "observability"
CHAT_ROOT = Path(__file__).resolve().parents[1] / "web" / "chat"


# 可观测控制台页面。
@admin_router.get("/observability")
def observability_page() -> HTMLResponse:
    return HTMLResponse((OBSERVABILITY_ROOT / "index.html").read_text(encoding="utf-8"))


# 可观测控制台静态脚本。
@admin_router.get("/static/app.js")
def observability_js() -> PlainTextResponse:
    return PlainTextResponse((OBSERVABILITY_ROOT / "app.js").read_text(encoding="utf-8"), media_type="application/javascript")


# 可观测控制台样式。
@admin_router.get("/static/style.css")
def observability_css() -> PlainTextResponse:
    return PlainTextResponse((OBSERVABILITY_ROOT / "style.css").read_text(encoding="utf-8"), media_type="text/css")


# 正式聊天工作台页面。
@chat_router.get("/chat")
def chat_page() -> HTMLResponse:
    return HTMLResponse((CHAT_ROOT / "index.html").read_text(encoding="utf-8"))


# 聊天工作台静态脚本。
@chat_router.get("/chat/static/app.js")
def chat_js() -> PlainTextResponse:
    return PlainTextResponse((CHAT_ROOT / "app.js").read_text(encoding="utf-8"), media_type="application/javascript")


# 聊天工作台样式。
@chat_router.get("/chat/static/style.css")
def chat_css() -> PlainTextResponse:
    return PlainTextResponse((CHAT_ROOT / "style.css").read_text(encoding="utf-8"), media_type="text/css")


# 兼容旧导入名。
router = admin_router
