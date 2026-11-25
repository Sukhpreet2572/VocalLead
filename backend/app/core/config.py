"""Typed backend-only settings; root .env never depends on the launch directory."""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore",
        hide_input_in_errors=True,
    )
    app_name: str = "VocaLead AI"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_url: SecretStr = SecretStr("sqlite:///./data/vocalead.db")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    livekit_url: str = ""
    livekit_api_key: SecretStr = SecretStr("")
    livekit_api_secret: SecretStr = SecretStr("")
    livekit_agent_name: str = "vocalead-sales-agent"
    deepgram_api_key: SecretStr = SecretStr("")
    deepgram_stt_model: str = ""
    deepgram_stt_language: str = "multi"
    google_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    gemini_embedding_model: str = ""
    embedding_provider: Literal["gemini", "local"] = "gemini"
    local_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    rag_collection_name: str = "vocalead_knowledge"
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_chunk_size: int = Field(default=800, ge=200, le=4000)
    rag_chunk_overlap: int = Field(default=120, ge=0, le=1000)
    rag_max_context_chars: int = Field(default=6000, ge=500, le=20000)
    rag_max_cosine_distance: float = Field(default=0.6, ge=0, le=2)
    tts_provider: str = ""
    tts_api_key: SecretStr = SecretStr("")
    tts_model: str = ""
    tts_voice_id: str = ""
    voice_default_language: Literal["en", "hi", "hinglish"] = "en"
    voice_max_session_seconds: int = Field(default=600, ge=30, le=3600)
    voice_token_ttl_seconds: int = Field(default=300, ge=30, le=900)
    voice_transcript_retention_enabled: bool = False
    chroma_persist_directory: str = "./data/chroma"
    google_calendar_id: str = ""
    google_application_credentials: SecretStr = SecretStr("")
    hubspot_access_token: SecretStr = SecretStr("")
    calendar_provider: Literal["local", "google"] = "local"
    crm_provider: Literal["local", "hubspot"] = "local"
    appointment_timezone: Literal["Asia/Kolkata"] = "Asia/Kolkata"
    appointment_duration_minutes: int = Field(default=30, ge=15, le=120)
    appointment_booking_horizon_days: int = Field(default=14, ge=1, le=90)
    appointment_min_notice_minutes: int = Field(default=120, ge=0, le=1440)
    booking_proposal_ttl_seconds: int = Field(default=300, ge=60, le=1800)

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(("sqlite:///", "postgresql+psycopg://")):
            raise ValueError("Select SQLite or PostgreSQL with the psycopg driver")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        if any(not origin.startswith(("http://", "https://")) or origin.endswith("/") for origin in origins):
            raise ValueError("Use explicit HTTP origins without a trailing slash")
        return origins
