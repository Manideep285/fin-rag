from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- core ---
    database_url: str = "postgresql+psycopg://finrag:finrag@db:5432/finrag"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # --- minio ---
    minio_endpoint: str = "store:9000"
    minio_access_key: str = "finrag"
    minio_secret_key: str = "finrag"
    minio_bucket: str = "rawfiles"
    minio_secure: bool = False

    # --- auth ---
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_ttl_hours: int = 24

    # --- LLM ---
    llm_provider: str = "openai"  # local | openai
    llm_base_url: str = "http://llm:8001/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "mistral-7b-instruct"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.2

    # --- embeddings / rerank ---
    embed_model: str = "BAAI/bge-base-en-v1.5"
    embed_dim: int = 768
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- chunking ---
    chunk_target_tokens: int = 350
    chunk_max_tokens: int = 400
    chunk_overlap_tokens: int = 40
    chunk_min_tokens: int = 50

    # --- retrieval ---
    bm25_top_k: int = 20
    vector_top_k: int = 20
    rrf_k: int = 60
    rerank_top_k: int = 10
    final_top_k: int = 5
    context_max_tokens: int = 3000

    # --- eval ---
    eval_sample_rate: float = 0.1  # 10%
    groundedness_threshold: float = 0.6


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
