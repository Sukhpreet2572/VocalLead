from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from livekit import api
from sqlalchemy import select

from app.core.config import Settings
from app.database import Base
from app.main import create_app
from app.models.voice_session import VoiceSession
from app.voice.token_service import create_participant_token


def configured(tmp_path):
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'voice.db'}",
                    livekit_url="wss://demo.livekit.cloud", livekit_api_key="demo-key",
                    livekit_api_secret="a-local-test-secret-long-enough-123",
                    deepgram_api_key="dg-test", google_api_key="google-test", tts_provider="elevenlabs",
                    tts_api_key="tts-test", tts_model="eleven_multilingual_v2", tts_voice_id="test-voice")


def test_consent_and_missing_credentials(tmp_path):
    with TestClient(create_app(Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'empty.db'}"))) as client:
        response = client.post('/api/v1/voice/sessions', json={'consent_acknowledged': False}, headers={'X-Voice-Owner': 'x' * 40})
        assert response.status_code == 422
        response = client.post('/api/v1/voice/sessions', json={'consent_acknowledged': True}, headers={'X-Voice-Owner': 'x' * 40})
        assert response.status_code == 503
        assert 'secret' not in response.text.lower()
        assert 'LIVEKIT_URL' in client.get('/api/v1/voice/availability').json()['missing']


def test_token_scope_and_expiry(tmp_path):
    settings = configured(tmp_path)
    token, expiry = create_participant_token(settings, 'assigned-room', 'visitor-id', 'Guest')
    import jwt
    claims = jwt.decode(token, settings.livekit_api_secret.get_secret_value(), algorithms=['HS256'], options={'verify_aud': False})
    assert claims['iss'] == 'demo-key'
    grant = claims['video']
    assert grant['room'] == 'assigned-room' and grant['roomJoin']
    assert not grant.get('roomAdmin', False) and not grant.get('canPublishData', True)
    assert claims['sub'] == 'visitor-id'
    assert 0 < (expiry - datetime.now(timezone.utc)).total_seconds() <= 300


def test_session_persistence_ownership_and_idempotent_end(tmp_path):
    settings = configured(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        Base.metadata.create_all(app.state.session_factory.kw['bind'])
        dispatch = type('Dispatch', (), {'id': 'dispatch-1'})()
        fake = type('LiveKit', (), {'agent_dispatch': type('AgentDispatch', (), {'create_dispatch': AsyncMock(return_value=dispatch)})(),
                                    'room': type('RoomService', (), {'delete_room': AsyncMock()})(),
                                    '__aenter__': AsyncMock(), '__aexit__': AsyncMock(return_value=None)})()
        fake.__aenter__.return_value = fake
        owner = 'a' * 40
        with patch('app.api.routes.voice.api.LiveKitAPI', return_value=fake):
            response = client.post('/api/v1/voice/sessions', json={'preferred_language': 'hi', 'consent_acknowledged': True}, headers={'X-Voice-Owner': owner})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data['status'] == 'CONNECTING'
            assert data['room_name'].startswith('vocalead-')
            assert data['participant_token']
            session_id = data['session_id']
            assert client.get(f'/api/v1/voice/sessions/{session_id}', headers={'X-Voice-Owner': 'b' * 40}).status_code == 404
            assert client.get(f'/api/v1/voice/sessions/{session_id}', headers={'X-Voice-Owner': owner}).status_code == 200
            assert client.post('/api/v1/voice/sessions', json={'consent_acknowledged': True}, headers={'X-Voice-Owner': owner}).status_code == 429
            assert client.post(f'/api/v1/voice/sessions/{session_id}/end', headers={'X-Voice-Owner': owner}).json()['status'] == 'COMPLETED'
            assert client.post(f'/api/v1/voice/sessions/{session_id}/end', headers={'X-Voice-Owner': owner}).json()['status'] == 'COMPLETED'
            with app.state.session_factory() as db:
                record = db.scalar(select(VoiceSession).where(VoiceSession.id == session_id))
                assert record and record.consent_acknowledged and record.ended_at
                assert record.owner_hash != owner
            assert fake.room.delete_room.await_count == 1
