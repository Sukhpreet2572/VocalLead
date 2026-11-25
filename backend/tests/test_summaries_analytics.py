import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.config import ROOT, Settings
from app.database import Base, build_engine, session_factory
from app.main import create_app
from app.models.property import Property, PropertyUnit
from app.models.interaction import InteractionSummary
from app.models.voice_session import VoiceSession
from app.summaries.service import finalise_voice
from app.summaries.provider import gemini_narrative
from app.summaries.schemas import StructuredSummary
from app.automation.scheduling import TZ

def seeded(tmp_path):
    settings = Settings(_env_file=None, app_env='development', database_url=f"sqlite:///{tmp_path / 'summaries.db'}")
    engine = build_engine(settings); Base.metadata.create_all(engine)
    with session_factory(engine)() as db:
        for record in json.loads((ROOT/'knowledge_base/properties/inventory.json').read_text(encoding='utf8')):
            db.add(Property(**{key:record[key] for key in ('id','name','location','type','status','possession','amenities','connectivity','payment')},
                            units=[PropertyUnit(**unit) for unit in record['units']]))
        db.commit()
    engine.dispose()
    return create_app(settings), settings

def open_day():
    day = datetime.now(TZ).date() + timedelta(days=2)
    while day.weekday() == 0: day += timedelta(days=1)
    return day

def test_full_local_interaction_and_analytics(tmp_path):
    app, _ = seeded(tmp_path)
    owner, other = {'X-Voice-Owner':'a'*64}, {'X-Voice-Owner':'b'*64}
    with TestClient(app) as client:
        lead = client.post('/api/v1/leads/demo', headers=owner).json()
        profile = client.patch(f"/api/v1/leads/{lead['id']}", headers=owner, json={
            'location':'Gurugram','configuration':'3 BHK','max_budget_inr':12_000_000,
            'timeline_months':2,'purchase_intent':'STRONG','site_visit_interest':True}).json()
        assert profile['score'] == 90
        day = open_day()
        slot = client.get(f'/api/v1/appointments/availability?property_id=emerald-heights&day={day}', headers=owner).json()['slots'][0]
        proposal = client.post('/api/v1/appointments/proposals', headers=owner, json={
            'lead_id':lead['id'],'property_id':'emerald-heights','start_at':slot['start_at']}).json()
        booked = client.post('/api/v1/appointments/confirm', headers=owner, json={
            'proposal_id':proposal['id'],'idempotency_key':'summary-booking-key-123','explicit_confirmation':True}).json()
        assert booked['status'] == 'CONFIRMED'
        payload = {'lead_id':lead['id'],'idempotency_key':'summary-demo-key-12345'}
        created = client.post('/api/v1/interactions/demo/finalise', headers=owner, json=payload)
        assert created.status_code == 201
        item = created.json()
        assert item['status'] == 'COMPLETED' and item['interaction_type'] == 'LOCAL_DEMO'
        assert item['duration_seconds'] is None and item['voice_session_id'] is None
        assert item['structured']['lead']['score'] == 90
        assert item['structured']['business']['appointment_id'] == booked['id']
        assert item['structured']['business']['calendar_sync_status'] == 'NOT_REQUIRED'
        assert item['structured']['metadata']['generation_method'] == 'DETERMINISTIC'
        assert 'Emerald Heights' in item['summary_text']
        assert 'INR 12,000,000' in item['summary_text']
        repeated = client.post('/api/v1/interactions/demo/finalise', headers=owner, json=payload)
        assert repeated.json()['id'] == item['id']
        assert client.get('/api/v1/interactions', headers=owner).json()['total'] == 1
        assert client.get('/api/v1/interactions', headers=other).json()['total'] == 0
        assert client.get(f"/api/v1/interactions/{item['id']}", headers=other).status_code == 404
        assert client.get('/api/v1/interactions?interaction_type=LOCAL_DEMO&lead_classification=HOT&appointment_status=CONFIRMED', headers=owner).json()['total'] == 1
        assert client.post(f"/api/v1/interactions/{item['id']}/retry-summary", headers=owner).status_code == 409
        report = client.get('/api/v1/analytics/overview', headers=owner).json()
        assert report['interactions']['total'] == 1 and report['interactions']['local_demo_interactions'] == 1
        assert report['interactions']['completed_voice_calls'] == 0
        assert report['interactions']['average_voice_duration_seconds'] is None
        assert report['leads']['hot'] == 1
        assert report['appointments']['confirmed'] == 1
        assert report['appointments']['conversion_rate'] == 100.0
        assert report['customer_intelligence']['unknown_sentiment'] == 1
        assert client.get('/api/v1/analytics/overview', headers=other).json()['leads']['total'] == 0
        future = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()
        empty = client.get(f'/api/v1/analytics/overview?start={future}&end={future}', headers=owner).json()
        assert empty['interactions']['total'] == 0 and empty['appointments']['conversion_rate'] is None
        assert client.get('/api/v1/analytics/overview?start=2026-12-31&end=2026-01-01', headers=owner).status_code == 422
        assert client.post('/api/v1/interactions/demo/finalise', headers=owner,
            json={'lead_id':str(uuid4()), 'idempotency_key':payload['idempotency_key']}).status_code == 409

def test_missing_facts_retry_and_voice_idempotency(tmp_path):
    app, settings = seeded(tmp_path)
    owner = {'X-Voice-Owner':'a'*64}
    with TestClient(app) as client:
        lead = client.post('/api/v1/leads/demo', headers=owner).json()
        item = client.post('/api/v1/interactions/demo/finalise', headers=owner,
            json={'lead_id':lead['id'],'idempotency_key':'missing-info-key-12345'}).json()
        assert item['structured']['requirements']['location'] is None
        assert item['structured']['conversation']['sentiment'] == 'UNKNOWN'
        assert 'unavailable' in item['summary_text']
        engine = build_engine(settings)
        with session_factory(engine)() as db:
            record = db.get(InteractionSummary, item['id'])
            record.status = 'FAILED'; record.error_code = 'SUMMARY_PROCESSING_FAILED'; db.commit()
        engine.dispose()
        retried = client.post(f"/api/v1/interactions/{item['id']}/retry-summary", headers=owner)
        assert retried.status_code == 200 and retried.json()['status'] == 'COMPLETED'
        engine = build_engine(settings)
        with session_factory(engine)() as db:
            now = datetime.now(timezone.utc)
            voice = VoiceSession(id=str(uuid4()), room_name='test-summary-room', participant_identity='test-summary-participant',
                owner_hash='not-used', customer_id=lead['customer_id'], preferred_language='en', status='COMPLETED',
                consent_acknowledged=True, consent_timestamp=now, created_at=now, started_at=now-timedelta(seconds=65),
                ended_at=now, duration_seconds=65)
            # Use the owned customer's actual hash; this is a synthetic unit fixture, not an actual voice metric claim.
            from app.models.customer import Customer
            voice.owner_hash = db.get(Customer, lead['customer_id']).owner_hash
            db.add(voice); db.commit()
            first = finalise_voice(db, voice.id, settings)
            second = finalise_voice(db, voice.id, settings)
            assert first.id == second.id and first.duration_seconds == 65
            assert first.interaction_type == 'VOICE'
        engine.dispose()

def test_gemini_narrative_adapter_contract_is_mocked():
    settings = Settings(_env_file=None, google_api_key='test-key')
    from app.summaries.schemas import (RequirementsSnapshot, ConversationSnapshot, LeadSnapshot, BusinessSnapshot, SummaryMetadata)
    summary = StructuredSummary(requirements=RequirementsSnapshot(), conversation=ConversationSnapshot(),
        lead=LeadSnapshot(score=0, classification='COLD', components={}, recommended_follow_up='Ask requirements.'),
        business=BusinessSnapshot(), metadata=SummaryMetadata(interaction_type='VOICE', generation_method='DETERMINISTIC',
        generated_at=datetime.now(timezone.utc), data_completeness='LIMITED'), summary_text='No details.')
    client = MagicMock()
    client.__enter__.return_value.models.generate_content.return_value = MagicMock(text='{"summary_text":"Record-based call summary."}')
    with patch('app.summaries.provider.genai.Client', return_value=client):
        assert gemini_narrative(summary, settings).summary_text == 'Record-based call summary.'
