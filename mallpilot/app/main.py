from fastapi import FastAPI


# 创建 FastAPI 应用，后续任务会在这里注册路由。
def create_app() -> FastAPI:
    app = FastAPI(title="MallPilot", version="0.1.0")
    return app


# FastAPI 默认应用实例。
app = create_app()
