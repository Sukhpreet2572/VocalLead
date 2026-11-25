from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import database_connected, get_session
from app.schemas.system import ErrorResponse, HealthResponse, IntegrationStatus, ReadyResponse, SystemStatus

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(version=request.app.state.settings.app_version)


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ErrorResponse}})
def ready(session: Session = Depends(get_session)) -> ReadyResponse:
    if not database_connected(session):
        raise HTTPException(503, "Database unavailable")
    return ReadyResponse()


def development_only(request: Request) -> None:
    if request.app.state.settings.app_env != "development":
        raise HTTPException(404, "Not found")


@router.get("/system/status", response_model=SystemStatus, dependencies=[Depends(development_only)])
def system_status(request: Request, session: Session = Depends(get_session)) -> SystemStatus:
    settings = request.app.state.settings
    def present(value: object) -> bool:
        raw = value.get_secret_value() if hasattr(value, "get_secret_value") else value
        return bool(str(raw).strip())
    configured = {
        "gemini": present(settings.google_api_key),
        "livekit": all(present(value) for value in (settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)),
        "deepgram": present(settings.deepgram_api_key),
        "tts": all(present(value) for value in (settings.tts_provider, settings.tts_api_key, settings.tts_model, settings.tts_voice_id)),
        "google_calendar": present(settings.google_calendar_id) and present(settings.google_application_credentials),
        "hubspot": present(settings.hubspot_access_token),
    }
    return SystemStatus(
        database="connected" if database_connected(session) else "unavailable",
        integrations={name: IntegrationStatus(configured=value) for name, value in configured.items()},
    )
