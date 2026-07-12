# Sprint 1 Real Shopping Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real MallPilot shopping loop with PostgreSQL + pgvector chunk storage, Bailian LLM/embedding/rerank integration, database-backed retrieval, SSE Trace, and a usable chat UI.

**Architecture:** Keep the existing FastAPI + self-built Router/Flow architecture. Add focused infrastructure modules for settings, database sessions, migrations, Bailian model calls, pgvector ingestion/retrieval, Trace persistence, and static chat UI rendering. External model calls are hidden behind testable interfaces so tests use fakes and never call the real network.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL + pgvector, httpx, Pydantic Settings, vanilla HTML/CSS/JS, pytest.

## Global Constraints

- `.env` stores local secrets and must never be committed.
- Code, tests, docs, logs, and Trace must not include the real API key.
- Bailian models are configured through `BAILIAN_LLM_MODEL`, `BAILIAN_EMBEDDING_MODEL`, and `BAILIAN_RERANK_MODEL`.
- Text embeddings use `text-embedding-v4`; default dimension is `1024`.
- Rerank should prefer `qwen3-rerank`; `gte-rerank-v2` remains configurable.
- Use TDD for every behavior change: write failing test, verify red, implement, verify green.
- Keep existing Flow behavior compatible unless a task explicitly replaces mock output with model-backed output.
- Keep `.idea/` untracked and out of commits.

---

## File Structure

- `mallpilot/app/core/config.py`: extend settings for Bailian, database, embedding dimension, and frontend defaults.
- `mallpilot/app/db/session.py`: database engine/session helpers and FastAPI dependency.
- `mallpilot/app/models/product.py`: replace temporary vector storage with a pgvector-compatible `embedding` column on `KnowledgeChunk`.
- `mallpilot/app/models/vector.py`: custom SQLAlchemy vector type that compiles to `VECTOR(n)` on PostgreSQL and JSON on SQLite tests.
- `migrations/env.py`, `migrations/versions/202607120002_pgvector_core.py`, `alembic.ini`: Alembic setup and pgvector migration.
- `mallpilot/app/llm/bailian_client.py`: HTTP client for Bailian chat, embedding, and rerank.
- `mallpilot/app/llm/schemas.py`: `LlmMessage`, `LlmResult`, `RerankScore`.
- `mallpilot/app/services/embedding_service.py`: batches chunk text embedding calls.
- `scripts/ingest_products.py`: generate embeddings and persist chunks with vectors.
- `mallpilot/app/repositories/product_repo.py`: save chunks with embeddings and query candidates.
- `mallpilot/app/retrieval/db_product_search.py`: database-backed hybrid retrieval.
- `mallpilot/app/services/db_trace_service.py`: Trace persistence service.
- `mallpilot/app/services/chat_service.py`: wire real retrieval, LLM, rerank, and persistent Trace.
- `mallpilot/app/api/admin.py`, `mallpilot/app/api/chat.py`: serve chat UI and keep observability UI.
- `mallpilot/app/web/chat/index.html`, `app.js`, `style.css`: formal chat workspace.
- `tests/`: one focused test file per task.

---

### Task 1: Secure Settings And Database Session

**Files:**
- Modify: `mallpilot/app/core/config.py`
- Create: `mallpilot/app/db/__init__.py`
- Create: `mallpilot/app/db/session.py`
- Test: `tests/test_settings_and_db.py`

**Interfaces:**
- Produces: `Settings.bailian_api_key`, `Settings.dashscope_api_key`, `Settings.bailian_base_url`, `Settings.bailian_llm_model`, `Settings.bailian_embedding_model`, `Settings.bailian_rerank_model`, `Settings.embedding_dimension`.
- Produces: `create_engine_from_settings(database_url: str | None = None) -> Engine`
- Produces: `create_session_factory(engine: Engine) -> sessionmaker[Session]`
- Produces: `get_db() -> Iterator[Session]`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

from sqlalchemy import text

from mallpilot.app.core.config import Settings
from mallpilot.app.db.session import create_engine_from_settings, create_session_factory


def test_env_file_is_gitignored():
    assert ".env" in Path(".gitignore").read_text(encoding="utf-8")


def test_settings_expose_bailian_and_embedding_defaults(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "test-key")
    settings = Settings()
    assert settings.bailian_api_key == "test-key"
    assert settings.bailian_llm_model == "qwen-plus"
    assert settings.bailian_embedding_model == "text-embedding-v4"
    assert settings.bailian_rerank_model == "qwen3-rerank"
    assert settings.embedding_dimension == 1024


def test_create_session_factory_runs_sqlite_query():
    engine = create_engine_from_settings("sqlite+pysqlite:///:memory:")
    SessionLocal = create_session_factory(engine)
    with SessionLocal() as session:
        assert session.execute(text("select 1")).scalar_one() == 1
```

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_settings_and_db.py -v`
Expected: FAIL because `mallpilot.app.db.session` does not exist and settings fields are missing.

- [ ] **Step 3: Implement settings and session helpers**

Add settings fields with Chinese comments. Implement `create_engine_from_settings`, `create_session_factory`, and `get_db` with Chinese comments before methods and key lifecycle logic.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_settings_and_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/core/config.py mallpilot/app/db tests/test_settings_and_db.py
git commit -m "feat: add settings and database session"
```

---

### Task 2: Alembic And Pgvector Model Support

**Files:**
- Create: `mallpilot/app/models/vector.py`
- Modify: `mallpilot/app/models/product.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/versions/202607120002_pgvector_core.py`
- Test: `tests/test_pgvector_migration.py`

**Interfaces:**
- Produces: `Vector(dimensions: int)` SQLAlchemy type.
- Produces: `KnowledgeChunk.embedding: Mapped[list[float] | None]`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

from sqlalchemy import create_engine

from mallpilot.app.models.base import Base
from mallpilot.app.models.product import KnowledgeChunk


def test_knowledge_chunk_has_embedding_column_on_metadata():
    assert "embedding" in KnowledgeChunk.__table__.columns


def test_sqlite_metadata_can_create_vector_backed_tables():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    assert "knowledge_chunks" in Base.metadata.tables


def test_migration_enables_pgvector_and_embedding_column():
    migration = Path("migrations/versions/202607120002_pgvector_core.py").read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "knowledge_chunks" in migration
    assert "embedding" in migration
    assert "VECTOR(1024)" in migration
```

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_pgvector_migration.py -v`
Expected: FAIL because vector type, migration, or embedding column is missing.

- [ ] **Step 3: Implement vector type and migration**

Implement `Vector` so PostgreSQL compiles as `VECTOR(dimensions)` and SQLite tests compile as JSON/Text-compatible storage. Add `KnowledgeChunk.embedding`. Add Alembic env and migration that creates pgvector extension and core tables.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_pgvector_migration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/models alembic.ini migrations tests/test_pgvector_migration.py
git commit -m "feat: add pgvector migration support"
```

---

### Task 3: Bailian Client

**Files:**
- Create: `mallpilot/app/llm/__init__.py`
- Create: `mallpilot/app/llm/schemas.py`
- Create: `mallpilot/app/llm/bailian_client.py`
- Test: `tests/test_bailian_client.py`

**Interfaces:**
- Produces: `LlmMessage(role: str, content: str)`
- Produces: `LlmResult(content: str, model: str, raw: dict[str, Any])`
- Produces: `RerankScore(index: int, score: float)`
- Produces: `BailianClient.chat(messages: list[LlmMessage]) -> LlmResult`
- Produces: `BailianClient.embed_texts(texts: list[str], text_type: str = "document") -> list[list[float]]`
- Produces: `BailianClient.rerank(query: str, documents: list[str], top_n: int | None = None) -> list[RerankScore]`

- [ ] **Step 1: Write failing tests**

Use `httpx.MockTransport` to assert:

```python
def test_bailian_client_chat_maps_openai_compatible_response():
    ...
    result = client.chat([LlmMessage(role="user", content="你好")])
    assert result.content == "你好，我是 MallPilot"
```

```python
def test_bailian_client_embed_texts_maps_embeddings():
    ...
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
```

```python
def test_bailian_client_rerank_maps_scores_without_leaking_key():
    ...
    assert [score.index for score in scores] == [1, 0]
```

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_bailian_client.py -v`
Expected: FAIL because client module is missing.

- [ ] **Step 3: Implement HTTP client**

Use official endpoints:
- Chat: OpenAI-compatible `/chat/completions` under `https://dashscope.aliyuncs.com/compatible-mode/v1`.
- Embeddings: OpenAI-compatible `/embeddings` under the same base URL.
- Rerank: for `qwen3-rerank`, call `/reranks` under compatible API; for `gte-rerank-v2`, call DashScope rerank endpoint when a workspace URL is configured.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_bailian_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/llm tests/test_bailian_client.py
git commit -m "feat: add bailian model client"
```

---

### Task 4: Embedding Ingestion Into Pgvector Chunks

**Files:**
- Modify: `mallpilot/app/repositories/product_repo.py`
- Modify: `scripts/ingest_products.py`
- Create: `mallpilot/app/services/embedding_service.py`
- Test: `tests/test_embedding_ingestion.py`

**Interfaces:**
- Produces: `EmbeddingService.embed_chunks(chunks: list[dict[str, Any]]) -> list[list[float]]`
- Produces: `ProductRepository.save_chunks_with_embeddings(chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> None`
- Produces: `run_ingestion(database_url: str | None = None, dataset_dir: str | None = None, embedding_service: EmbeddingService | None = None) -> int`

- [ ] **Step 1: Write failing tests**

Test that a fake embedding service writes a fixed vector to each chunk and that `run_ingestion` returns the number of products imported.

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_embedding_ingestion.py -v`
Expected: FAIL because `EmbeddingService` and vector-aware repository methods are missing.

- [ ] **Step 3: Implement embedding ingestion**

Batch chunk texts into `BailianClient.embed_texts`, validate vector length equals `Settings.embedding_dimension`, and persist with `KnowledgeChunk.embedding`.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_embedding_ingestion.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/repositories/product_repo.py mallpilot/app/services/embedding_service.py scripts/ingest_products.py tests/test_embedding_ingestion.py
git commit -m "feat: ingest product chunks with embeddings"
```

---

### Task 5: Database Hybrid Retrieval And Bailian Rerank

**Files:**
- Create: `mallpilot/app/retrieval/db_product_search.py`
- Modify: `mallpilot/app/retrieval/product_search.py`
- Modify: `mallpilot/app/repositories/product_repo.py`
- Test: `tests/test_db_product_search.py`

**Interfaces:**
- Produces: `DatabaseProductSearch.search(query: str, filters: dict[str, Any] | None = None, image_embedding: list[float] | None = None, top_k: int = 5) -> tuple[list[ProductCandidate], list[TraceEvent]]`

- [ ] **Step 1: Write failing tests**

Use fake repository candidates and fake reranker. Assert Trace events include `retrieval.bm25`, `retrieval.vector`, `retrieval.rrf`, and `rerank.bailian`.

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_db_product_search.py -v`
Expected: FAIL because `DatabaseProductSearch` is missing.

- [ ] **Step 3: Implement database retrieval facade**

Reuse tokenization and RRF from the MVP. Use SQLAlchemy query methods for structured filtering and vector candidate retrieval. In SQLite tests, compute vector similarity in Python; in PostgreSQL, use pgvector distance SQL.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_db_product_search.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/retrieval mallpilot/app/repositories/product_repo.py tests/test_db_product_search.py
git commit -m "feat: add database hybrid retrieval"
```

---

### Task 6: LLM-Backed Guide And QA Flows

**Files:**
- Create: `mallpilot/app/services/llm_service.py`
- Modify: `mallpilot/app/agent/flows/guide_flow.py`
- Modify: `mallpilot/app/agent/flows/product_qa_flow.py`
- Test: `tests/test_llm_flows.py`

**Interfaces:**
- Produces: `LlmService.generate_guide_summary(message: str, candidates: list[ProductCandidate]) -> str`
- Produces: `LlmService.answer_product_question(message: str, evidence: list[dict[str, Any]]) -> str`

- [ ] **Step 1: Write failing tests**

Use a fake LLM service and assert GuideFlow emits an LLM-generated final summary and ProductQaFlow emits an LLM-generated answer.

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_llm_flows.py -v`
Expected: FAIL because flows do not accept or use `LlmService`.

- [ ] **Step 3: Implement LLM service and inject into flows**

Keep fallback copy for tests and no-candidate cases, but use `LlmService` when supplied.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_llm_flows.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/services/llm_service.py mallpilot/app/agent/flows tests/test_llm_flows.py
git commit -m "feat: use bailian llm in guide flows"
```

---

### Task 7: Persistent Trace In Chat Service

**Files:**
- Create: `mallpilot/app/services/db_trace_service.py`
- Modify: `mallpilot/app/services/chat_service.py`
- Modify: `mallpilot/app/api/trace.py`
- Test: `tests/test_chat_trace_persistence.py`

**Interfaces:**
- Produces: `DbTraceService.record(event: TraceEvent) -> None`
- Produces: `DbTraceService.list_events(turn_id: str) -> list[TraceEvent]`

- [ ] **Step 1: Write failing tests**

Assert chat streaming records router, retrieval, LLM, and SSE Trace events through an injected fake trace service.

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_chat_trace_persistence.py -v`
Expected: FAIL because chat service does not record all required events.

- [ ] **Step 3: Implement persistent Trace service**

Store Trace through repository and update Trace API to use the service. Keep in-memory service as a test/demo fallback.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_chat_trace_persistence.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/services mallpilot/app/api/trace.py tests/test_chat_trace_persistence.py
git commit -m "feat: persist chat trace events"
```

---

### Task 8: Formal Chat Frontend

**Files:**
- Create: `mallpilot/app/web/chat/index.html`
- Create: `mallpilot/app/web/chat/app.js`
- Create: `mallpilot/app/web/chat/style.css`
- Modify: `mallpilot/app/api/admin.py`
- Test: `tests/test_chat_frontend.py`

**Interfaces:**
- Produces: `GET /chat` serving the chat workspace.
- Produces: static assets under `/chat/static/app.js` and `/chat/static/style.css`.

- [ ] **Step 1: Write failing tests**

Assert `/chat` loads, contains `MallPilot`, and references chat static assets.

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_chat_frontend.py -v`
Expected: FAIL because `/chat` does not exist.

- [ ] **Step 3: Implement chat UI**

Build vanilla HTML/CSS/JS with three panes: sessions, chat stream, Trace summary. JS parses SSE events and renders `thinking`, `product_card`, `clarification`, `answer`, `order_preview`, `after_sale_preview`, and `final`.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_chat_frontend.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/web/chat mallpilot/app/api/admin.py tests/test_chat_frontend.py
git commit -m "feat: add chat frontend"
```

---

### Task 9: End-To-End Wiring And Verification

**Files:**
- Modify: `mallpilot/app/services/chat_service.py`
- Modify: `mallpilot/app/main.py`
- Modify: `README.md`
- Test: `tests/test_real_loop_contract.py`

**Interfaces:**
- Produces: app startup path that can use Bailian-backed components when settings are present.
- Produces: README commands for database setup, migration, ingestion, server startup, and UI URLs.

- [ ] **Step 1: Write failing tests**

Assert app routes include `/chat`, `/admin/observability`, `/api/chat/stream`, and that settings-backed service construction does not expose secrets in repr/Trace payloads.

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_real_loop_contract.py -v`
Expected: FAIL because final wiring/docs are incomplete.

- [ ] **Step 3: Implement final wiring and docs**

Wire defaults conservatively: if database or Bailian is unavailable, tests can inject fakes; production settings use real services. Add README without secrets.

- [ ] **Step 4: Verify green and full suite**

Run:

```bash
pytest tests/test_real_loop_contract.py -v
pytest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app README.md tests/test_real_loop_contract.py
git commit -m "feat: wire real shopping loop"
```

---

## Self-Review

Spec coverage:

- `.env` security: Task 1.
- PostgreSQL + pgvector: Task 2.
- Bailian LLM, embedding, rerank: Tasks 3, 4, 5, 6.
- Chunk embedding ingestion: Task 4.
- Database retrieval: Task 5.
- Formal frontend: Task 8.
- Trace observability: Task 7 and Task 9.
- Full verification and docs: Task 9.

Placeholder scan:

- No unresolved placeholders are intentionally left in the plan.

Type consistency:

- `BailianClient`, `EmbeddingService`, `DatabaseProductSearch`, `LlmService`, and `DbTraceService` names match their consuming tasks.
