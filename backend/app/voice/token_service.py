from datetime import datetime, timedelta, timezone
from livekit import api
from app.core.config import Settings


def create_participant_token(settings: Settings, room: str, identity: str, name: str | None) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.voice_token_ttl_seconds)
    token = (api.AccessToken(settings.livekit_api_key.get_secret_value(),
                             settings.livekit_api_secret.get_secret_value())
             .with_identity(identity).with_name(name or "Guest")
             .with_ttl(timedelta(seconds=settings.voice_token_ttl_seconds))
             .with_grants(api.VideoGrants(room_join=True, room=room,
                                          can_publish=True, can_subscribe=True,
                                          can_publish_data=False)))
    return token.to_jwt(), expires
