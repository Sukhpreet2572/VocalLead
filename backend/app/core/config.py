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
    deepgram_api_key: SecretStr = SecretStr("")
    deepgram_stt_model: str = ""
    google_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    gemini_embedding_model: str = ""
    tts_provider: str = ""
    tts_api_key: SecretStr = SecretStr("")
    tts_model: str = ""
    tts_voice_id: str = ""
    chroma_persist_directory: str = "./data/chroma"
    google_calendar_id: str = ""
    google_application_credentials: SecretStr = SecretStr("")
    hubspot_access_token: SecretStr = SecretStr("")

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
