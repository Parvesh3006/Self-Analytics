from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://selfanalytics:selfanalytics@127.0.0.1:5544/selfanalytics"
    redis_url: str = "redis://127.0.0.1:6380/0"
    data_dir: Path = ROOT / "data"

    ollama_url: str = "http://127.0.0.1:11434"
    ollama_extract_model: str = "qwen3:4b"
    ollama_assistant_model: str = "qwen3:8b"
    ollama_embed_model: str = "bge-m3"

    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jooble_api_key: str = ""
    careerjet_api_key: str = ""
    usajobs_email: str = ""
    usajobs_api_key: str = ""
    reed_api_key: str = ""
    findwork_api_key: str = ""
    francetravail_client_id: str = ""
    francetravail_client_secret: str = ""

    brave_api_key: str = ""
    tavily_api_key: str = ""
    searxng_url: str = ""

    llm_fallback: str = "none"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""

    app_password: str = ""

    # Identifies the crawler honestly. Deliberately generic: no personal contact details.
    user_agent: str = "SelfAnalyticsBot/0.1 (personal job-market research; respects robots.txt)"
    crawl_delay_seconds: float = 3.0
    crawl_max_pages: int = 60
    crawl_max_depth: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()


