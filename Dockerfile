# MallPilot 综合电商导购助手 - Docker 多阶段构建
# 做什么：区分依赖安装、生产镜像和开发镜像；为什么：兼顾体积、运行安全和本地调试体验。

FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

FROM base AS dependencies

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 做什么：预下载 Chroma 内置 ONNX 模型。
# 为什么：避免容器首次启动时再联网拉取，导致启动时间过长。
RUN mkdir -p /root/.cache/chroma/onnx_models/all-MiniLM-L6-v2 && \
    curl -L --retry 3 --retry-delay 5 -o /root/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx.tar.gz \
    https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz && \
    cd /root/.cache/chroma/onnx_models/all-MiniLM-L6-v2 && \
    tar -xzf onnx.tar.gz && \
    rm onnx.tar.gz

FROM base AS production

RUN useradd -m -u 1000 mallpilot

COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin
COPY --from=dependencies --chown=mallpilot:mallpilot /root/.cache/chroma /home/mallpilot/.cache/chroma
COPY --chown=mallpilot:mallpilot . .

RUN mkdir -p /app/data/chroma /app/data/sqlite /app/logs /app/config && \
    chown mallpilot:mallpilot /app/data /app/data/chroma /app/data/sqlite /app/logs /app/config

USER mallpilot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM dependencies AS development

COPY . .

RUN mkdir -p /app/data/chroma /app/data/sqlite /app/logs /app/config /app/tests && \
    chmod -R 777 /app/data /app/logs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
