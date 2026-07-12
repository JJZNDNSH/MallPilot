from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库连接字符串。
    database_url: str = "postgresql+psycopg://postgres:postgres@192.168.154.128:5432/mallpilot"
    # 商品数据目录。
    dataset_dir: str = "data/ecommerce_agent_dataset"
    # 是否启用 mock LLM。
    use_mock_llm: bool = True
    # 百炼 API Key，优先从本地 .env 或环境变量读取。
    bailian_api_key: str | None = None
    # DashScope API Key，兼容百炼 OpenAI 风格接口。
    dashscope_api_key: str | None = None
    # 百炼 OpenAI 兼容接口基础地址。
    bailian_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 百炼导购对话模型名称。
    bailian_llm_model: str = "qwen-plus"
    # 百炼文本向量模型名称。
    bailian_embedding_model: str = "text-embedding-v4"
    # 百炼重排模型名称。
    bailian_rerank_model: str = "qwen3-rerank"
    # 文本向量维度，需与入库和 pgvector migration 保持一致。
    embedding_dimension: int = 1024

    # Pydantic Settings 从本地 .env 读取密钥，但 .env 不进入 git。
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# 获取应用配置。
def get_settings() -> Settings:
    return Settings()
