"""Service configuration (data-model.md §8). Values are read from the environment and from .env."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Norm search
    retrieval_k: int = 5
    confidence_threshold: float = 0.3
    embed_model: str = "intfloat/multilingual-e5-large"
    chroma_path: str = "data/chroma"
    chroma_collection: str = "ar_law"

    # Generative model (provider fixed in plan.md R3)
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5-5"
    llm_max_attempts: int = 3
    llm_timeout_s: float = 30.0
    llm_concurrency: int = 5
    anthropic_api_key: SecretStr | None = None

    # Upload and OCR
    max_upload_mb: int = 10
    ocr_enabled: bool = False
    ocr_lang: str = "spa"

    # Report storage (spec §4, AC15)
    reports_db_path: str = "data/reports.db"
    report_retention_days: int = 30
