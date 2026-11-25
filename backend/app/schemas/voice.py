from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

Language = Literal["en", "hi", "hinglish"]


class CreateVoiceSession(BaseModel):
    preferred_language: Language = "en"
    consent_acknowledged: bool
    display_name: str | None = Field(default=None, max_length=60)


class VoiceSessionInfo(BaseModel):
    session_id: str
    status: str
    preferred_language: Language
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None


class VoiceSessionCreated(VoiceSessionInfo):
    livekit_url: str
    room_name: str
    participant_token: str
    token_expires_at: datetime


class VoiceAvailability(BaseModel):
    available: bool
    missing: list[str]
    transcript_retention_enabled: bool
    max_session_seconds: int
