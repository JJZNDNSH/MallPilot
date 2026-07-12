from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库连接字符串。
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/mallpilot"
    # 商品数据目录。
    dataset_dir: str = "data/ecommerce_agent_dataset"
    # 是否启用 mock LLM。
    use_mock_llm: bool = True


# 获取应用配置。
def get_settings() -> Settings:
    return Settings()
