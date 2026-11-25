import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from livekit import api

from app.database import get_session
from app.models.voice_session import VoiceSession
from app.schemas.voice import CreateVoiceSession, VoiceAvailability, VoiceSessionCreated, VoiceSessionInfo
from app.voice.token_service import create_participant_token

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


def availability(settings) -> VoiceAvailability:
    required = {
        "LIVEKIT_URL": settings.livekit_url,
        "LIVEKIT_API_KEY": settings.livekit_api_key.get_secret_value(),
        "LIVEKIT_API_SECRET": settings.livekit_api_secret.get_secret_value(),
        "DEEPGRAM_API_KEY": settings.deepgram_api_key.get_secret_value(),
        "GOOGLE_API_KEY": settings.google_api_key.get_secret_value(),
        "TTS_PROVIDER": settings.tts_provider,
        "TTS_API_KEY": settings.tts_api_key.get_secret_value(),
        "TTS_MODEL": settings.tts_model,
        "TTS_VOICE_ID": settings.tts_voice_id,
    }
    return VoiceAvailability(available=all(required.values()), missing=[key for key, value in required.items() if not value],
                             transcript_retention_enabled=settings.voice_transcript_retention_enabled,
                             max_session_seconds=settings.voice_max_session_seconds)


def require_local(request: Request) -> None:
    if request.app.state.settings.app_env != "development" or request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
        raise HTTPException(403, "Voice demo is restricted to local development")


def owner_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def owned_session(session_id: str, owner: str | None, db: Session) -> VoiceSession:
    record = db.get(VoiceSession, session_id)
    if not record or not owner or not secrets.compare_digest(record.owner_hash, owner_hash(owner)):
        raise HTTPException(404, "Voice session not found")
    return record


def info(record: VoiceSession) -> VoiceSessionInfo:
    return VoiceSessionInfo(session_id=record.id, status=record.status, preferred_language=record.preferred_language,
                            created_at=record.created_at, started_at=record.started_at, ended_at=record.ended_at,
                            duration_seconds=record.duration_seconds)


@router.get("/availability", response_model=VoiceAvailability, dependencies=[Depends(require_local)])
def voice_availability(request: Request) -> VoiceAvailability:
    return availability(request.app.state.settings)


@router.post("/sessions", response_model=VoiceSessionCreated, dependencies=[Depends(require_local)])
async def create_session(body: CreateVoiceSession, request: Request, db: Session = Depends(get_session),
                         x_voice_owner: str | None = Header(default=None)) -> VoiceSessionCreated:
    if not body.consent_acknowledged:
        raise HTTPException(422, "Voice consent is required")
    if not x_voice_owner or len(x_voice_owner) < 32:
        raise HTTPException(403, "Demo owner key is required")
    settings = request.app.state.settings
    state = availability(settings)
    if not state.available or settings.tts_provider != "elevenlabs":
        raise HTTPException(503, "Voice configuration incomplete; check /api/v1/voice/availability and TTS_PROVIDER=elevenlabs")
    # One active demo session per owner limits accidental concurrent paid usage.
    existing = db.scalar(select(VoiceSession).where(VoiceSession.owner_hash == owner_hash(x_voice_owner),
                                                      VoiceSession.status.in_(["CREATED", "CONNECTING", "ACTIVE", "ENDING"])))
    if existing:
        raise HTTPException(429, "End the current voice session before creating another")
    uid = str(uuid4())
    room = f"vocalead-{uid}"
    identity = f"visitor-{uuid4()}"
    token, expires = create_participant_token(settings, room, identity, body.display_name)
    record = VoiceSession(id=uid, room_name=room, participant_identity=identity,
                          owner_hash=owner_hash(x_voice_owner), preferred_language=body.preferred_language,
                          consent_acknowledged=True, consent_timestamp=datetime.now(timezone.utc), status="CREATED")
    db.add(record)
    db.commit()
    try:
        async with api.LiveKitAPI(url=settings.livekit_url, api_key=settings.livekit_api_key.get_secret_value(),
                                  api_secret=settings.livekit_api_secret.get_secret_value()) as livekit:
            dispatch = await livekit.agent_dispatch.create_dispatch(api.CreateAgentDispatchRequest(
                agent_name=settings.livekit_agent_name, room=room, metadata=f"{uid}:{body.preferred_language}"))
        record.dispatch_id = dispatch.id
        record.status = "CONNECTING"
        db.commit()
    except Exception:
        record.status = "FAILED"
        record.failure_reason = "Agent dispatch failed"
        db.commit()
        raise HTTPException(503, "Could not dispatch the voice agent; check LiveKit and worker availability")
    db.refresh(record)
    return VoiceSessionCreated(**info(record).model_dump(), livekit_url=settings.livekit_url,
                               room_name=room, participant_token=token, token_expires_at=expires)


@router.get("/sessions/{session_id}", response_model=VoiceSessionInfo, dependencies=[Depends(require_local)])
def get_voice_session(session_id: str, db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None)) -> VoiceSessionInfo:
    return info(owned_session(session_id, x_voice_owner, db))


@router.post("/sessions/{session_id}/end", response_model=VoiceSessionInfo, dependencies=[Depends(require_local)])
async def end_voice_session(session_id: str, request: Request, db: Session = Depends(get_session),
                            x_voice_owner: str | None = Header(default=None)) -> VoiceSessionInfo:
    record = owned_session(session_id, x_voice_owner, db)
    if record.status in ("COMPLETED", "FAILED"):
        return info(record)
    settings = request.app.state.settings
    record.status = "ENDING"
    db.commit()
    try:
        async with api.LiveKitAPI(url=settings.livekit_url, api_key=settings.livekit_api_key.get_secret_value(),
                                  api_secret=settings.livekit_api_secret.get_secret_value()) as livekit:
            await livekit.room.delete_room(api.DeleteRoomRequest(room=record.room_name))
    except Exception:
        raise HTTPException(503, "Could not end the LiveKit room; retry ending the call")
    record.status = "COMPLETED"
    record.ended_at = datetime.now(timezone.utc)
    if record.started_at:
        record.duration_seconds = max(0, int((record.ended_at - record.started_at.replace(tzinfo=timezone.utc)).total_seconds()))
    db.commit()
    return info(record)
