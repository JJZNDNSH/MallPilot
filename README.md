# MallPilot

MallPilot 是一个 Python/FastAPI 导购 Agent 原型，包含商品入库、pgvector 检索、百炼模型客户端、SSE 聊天接口、正式聊天界面和可观测控制台。

## 本地配置

创建 `.env`，并确保它不进入 git：

```text
BAILIAN_API_KEY=your_api_key
DASHSCOPE_API_KEY=your_api_key
BAILIAN_LLM_MODEL=qwen-plus
BAILIAN_EMBEDDING_MODEL=text-embedding-v4
BAILIAN_RERANK_MODEL=qwen3-rerank
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/mallpilot
USE_MOCK_LLM=false
```

## 数据库

PostgreSQL 需要启用 pgvector。创建数据库后执行迁移：

```powershell
alembic upgrade head
```

导入商品数据并生成 chunk embedding：

```powershell
python -m scripts.ingest_products
```

## 启动

```powershell
uvicorn mallpilot.app.main:app --host 127.0.0.1 --port 8000
```

页面：

- 聊天工作台：http://127.0.0.1:8000/chat
- 可观测控制台：http://127.0.0.1:8000/admin/observability

## 测试

```powershell
pytest -v
```
