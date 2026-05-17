from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://finrag:finrag@db:5432/finrag"
    minio_endpoint: str = "store:9000"
    minio_access_key: str = "finrag"
    minio_secret_key: str = "finrag"
    minio_bucket: str = "rawfiles"
    minio_secure: bool = False

    embed_model: str = "BAAI/bge-base-en-v1.5"
    embed_dim: int = 768
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    chunk_target_tokens: int = 350
    chunk_max_tokens: int = 400
    chunk_overlap_tokens: int = 40
    chunk_min_tokens: int = 50

    worker_poll_interval: int = 5
    worker_http_port: int = 9100
    log_level: str = "INFO"

    llm_provider: str = "openai"
    llm_base_url: str = "http://llm:8001/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "mistral-7b-instruct"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
