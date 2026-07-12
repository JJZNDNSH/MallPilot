from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

router = APIRouter(prefix="/admin", tags=["admin"])
WEB_ROOT = Path(__file__).resolve().parents[1] / "web" / "observability"


# 可观测控制台页面。
@router.get("/observability")
def observability_page() -> HTMLResponse:
    return HTMLResponse((WEB_ROOT / "index.html").read_text(encoding="utf-8"))


# 控制台静态脚本。
@router.get("/static/app.js")
def observability_js() -> PlainTextResponse:
    return PlainTextResponse((WEB_ROOT / "app.js").read_text(encoding="utf-8"), media_type="application/javascript")


# 控制台样式。
@router.get("/static/style.css")
def observability_css() -> PlainTextResponse:
    return PlainTextResponse((WEB_ROOT / "style.css").read_text(encoding="utf-8"), media_type="text/css")
