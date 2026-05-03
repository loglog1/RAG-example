from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_api_key: str
    llm_api_base: str = "https://api.openai.com/v1"
    llm_chat_model: str = "gpt-4o"

    embedding_api_key: str
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"

    chroma_persist_dir: str = "./chroma_db"
    top_k_chunks: int = 10
    top_k_recommend: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
