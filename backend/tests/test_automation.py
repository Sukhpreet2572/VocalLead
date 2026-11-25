import json
import httpx
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.config import ROOT, Settings
from app.database import Base, build_engine, session_factory
from app.main import create_app
from app.models.appointment import Appointment, BookingProposal, CRMRecord, SyncOperation
from app.models.property import Property, PropertyUnit
from app.automation.scheduling import TZ, available_slots
from app.automation.providers import GoogleCalendar, HubSpotCRM

def app_with_inventory(tmp_path, **overrides):
    settings = Settings(_env_file=None, app_env="development", database_url=f"sqlite:///{tmp_path / 'automation.db'}", **overrides)
    engine = build_engine(settings)
    Base.metadata.create_all(engine)
    with session_factory(engine)() as db:
        for item in json.loads((ROOT / "knowledge_base/properties/inventory.json").read_text(encoding="utf-8")):
            db.add(Property(**{k: item[k] for k in ('id','name','location','type','status','possession','amenities','connectivity','payment')},
                            units=[PropertyUnit(**unit) for unit in item['units']]))
        db.commit()
    engine.dispose()
    return create_app(settings), settings

def next_open_day():
    day = datetime.now(TZ).date() + timedelta(days=2)
    while day.weekday() == 0: day += timedelta(days=1)
    return day

def setup_lead(client, headers):
    lead = client.post('/api/v1/leads/demo', headers=headers).json()
    updated = client.patch(f"/api/v1/leads/{lead['id']}", headers=headers, json={
        'location':'Gurugram','configuration':'3 BHK','max_budget_inr':12_000_000,
        'purchase_intent':'STRONG','timeline_months':2,'site_visit_interest':True})
    assert updated.json()['score'] == 90
    return lead

def test_local_booking_idempotency_conflict_cancel_and_isolation(tmp_path):
    app, _ = app_with_inventory(tmp_path)
    owner = {'X-Voice-Owner':'a' * 64}
    other = {'X-Voice-Owner':'b' * 64}
    with TestClient(app) as client:
        lead = setup_lead(client, owner)
        day = next_open_day()
        url = f'/api/v1/appointments/availability?property_id=emerald-heights&day={day}'
        available = client.get(url, headers=owner)
        assert available.status_code == 200 and available.json()['slots']
        start = available.json()['slots'][0]['start_at']
        p = client.post('/api/v1/appointments/proposals', headers=owner,
            json={'lead_id':lead['id'],'property_id':'emerald-heights','start_at':start})
        assert p.status_code == 201
        proposal_id = p.json()['id']
        assert proposal_id in [x['id'] for x in client.get('/api/v1/appointments/proposals', headers=owner).json()['items']]
        assert client.get('/api/v1/appointments/proposals', headers=other).json()['items'] == []
        assert client.post('/api/v1/appointments/confirm', headers=owner,
            json={'proposal_id':proposal_id,'idempotency_key':'test-confirmation-key-123','explicit_confirmation':False}).status_code == 409
        confirmed = client.post('/api/v1/appointments/confirm', headers=owner,
            json={'proposal_id':proposal_id,'idempotency_key':'test-confirmation-key-123','explicit_confirmation':True})
        assert confirmed.status_code == 200
        body = confirmed.json()
        assert body['status'] == 'CONFIRMED' and body['calendar_sync_status'] == 'NOT_REQUIRED'
        assert proposal_id not in [x['id'] for x in client.get('/api/v1/appointments/proposals', headers=owner).json()['items']]
        assert any(x['event_type'] == 'APPOINTMENT_CONFIRMED' for x in client.get('/api/v1/appointments/activity', headers=owner).json()['items'])
        assert start not in [x['start_at'] for x in client.get(url, headers=owner).json()['slots']]
        again = client.post('/api/v1/appointments/confirm', headers=owner,
            json={'proposal_id':proposal_id,'idempotency_key':'test-confirmation-key-123','explicit_confirmation':True})
        assert again.json()['id'] == body['id']
        assert client.post('/api/v1/appointments/confirm', headers=owner,
            json={'proposal_id':str(uuid4()),'idempotency_key':'test-confirmation-key-123','explicit_confirmation':True}).status_code == 409
        second = client.post('/api/v1/appointments/proposals', headers=owner,
            json={'lead_id':lead['id'],'property_id':'emerald-heights','start_at':start})
        assert second.status_code == 422
        assert client.get(f"/api/v1/appointments/{body['id']}", headers=other).status_code == 404
        assert client.post(f"/api/v1/appointments/{body['id']}/cancel", headers=other).status_code == 404
        assert client.get('/api/v1/crm/records', headers=owner).json()['items'][0]['lifecycle_status'] == 'VISIT_BOOKED'
        cancelled = client.post(f"/api/v1/appointments/{body['id']}/cancel", headers=owner)
        assert cancelled.json()['status'] == 'CANCELLED'
        assert client.post(f"/api/v1/appointments/{body['id']}/cancel", headers=owner).json()['status'] == 'CANCELLED'
        assert start in [x['start_at'] for x in client.get(url, headers=owner).json()['slots']]
        assert client.get('/api/v1/appointments', headers=owner).json()['total'] == 1
        assert client.get('/api/v1/appointments', headers=other).json()['total'] == 0

def test_expired_cross_owner_and_naive_proposal(tmp_path):
    app, settings = app_with_inventory(tmp_path)
    owner = {'X-Voice-Owner':'a' * 64}
    other = {'X-Voice-Owner':'b' * 64}
    with TestClient(app) as client:
        lead = setup_lead(client, owner)
        day = next_open_day()
        slots = client.get(f'/api/v1/appointments/availability?property_id=palm-grove&day={day}', headers=owner).json()['slots']
        assert client.post('/api/v1/appointments/proposals', headers=owner, json={
            'lead_id':lead['id'],'property_id':'palm-grove','start_at':slots[0]['start_at'].replace('Z', '').split('+')[0]}).status_code == 422
        proposal = client.post('/api/v1/appointments/proposals', headers=owner, json={
            'lead_id':lead['id'],'property_id':'palm-grove','start_at':slots[0]['start_at']}).json()
        assert client.post('/api/v1/appointments/confirm', headers=other, json={
            'proposal_id':proposal['id'],'idempotency_key':'another-key-123456','explicit_confirmation':True}).status_code == 404
        engine = build_engine(settings)
        with session_factory(engine)() as db:
            record = db.get(BookingProposal, proposal['id'])
            record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        engine.dispose()
        assert client.post('/api/v1/appointments/confirm', headers=owner, json={
            'proposal_id':proposal['id'],'idempotency_key':'expired-key-123456','explicit_confirmation':True}).status_code == 409

def test_business_hours_notice_horizon_and_missing_calendar(tmp_path):
    app, settings = app_with_inventory(tmp_path)
    engine = build_engine(settings)
    with session_factory(engine)() as db:
        now = datetime(2026, 11, 25, 16, 0, tzinfo=TZ)
        assert available_slots(db, 'emerald-heights', now.date(), settings, now=now) == []
        tomorrow = now.date() + timedelta(days=1)
        slots = available_slots(db, 'emerald-heights', tomorrow, settings, now=now)
        assert slots[0]['start_at'].astimezone(TZ).hour == 10
        assert slots[-1]['end_at'].astimezone(TZ).hour == 17
        try: available_slots(db, 'emerald-heights', now.date() - timedelta(days=1), settings, now=now); assert False
        except ValueError: pass
        try: available_slots(db, 'emerald-heights', now.date() + timedelta(days=15), settings, now=now); assert False
        except ValueError: pass
        monday = now.date() + timedelta(days=5)
        assert monday.weekday() == 0 and available_slots(db, 'emerald-heights', monday, settings, now=now) == []
    engine.dispose()
    external, _ = app_with_inventory(tmp_path / 'external', calendar_provider='google')
    with TestClient(external) as client:
        response = client.get(f'/api/v1/appointments/availability?property_id=emerald-heights&day={next_open_day()}', headers={'X-Voice-Owner':'a' * 64})
        assert response.status_code == 503

def test_hubspot_skip_without_consent_and_calendar_failure(tmp_path):
    app, settings = app_with_inventory(tmp_path, crm_provider='hubspot', calendar_provider='google')
    owner = {'X-Voice-Owner':'a' * 64}
    with TestClient(app) as client:
        lead = setup_lead(client, owner)
        day = next_open_day()
        with patch('app.automation.providers.GoogleCalendar') as calendar, patch('app.automation.sync.GoogleCalendar') as sync_calendar:
            calendar.return_value.busy.return_value = []
            sync_calendar.return_value.create_event.side_effect = OSError('private provider detail')
            slots = client.get(f'/api/v1/appointments/availability?property_id=emerald-heights&day={day}', headers=owner).json()['slots']
            proposal = client.post('/api/v1/appointments/proposals', headers=owner, json={
                'lead_id':lead['id'],'property_id':'emerald-heights','start_at':slots[0]['start_at']}).json()
            result = client.post('/api/v1/appointments/confirm', headers=owner, json={
                'proposal_id':proposal['id'],'idempotency_key':'external-key-123456','explicit_confirmation':True})
        assert result.status_code == 200
        body = result.json()
        assert body['status'] == 'PENDING' and body['calendar_sync_status'] == 'FAILED'
        assert body['crm_sync_status'] == 'NOT_REQUIRED'
        assert 'private provider detail' not in json.dumps(body)
        assert client.post(f"/api/v1/appointments/{body['id']}/sync", headers=owner).status_code == 409
        assert client.post(f"/api/v1/appointments/{body['id']}/sync", headers={'X-Voice-Owner':'b' * 64}).status_code == 404
        assert client.get('/api/v1/crm/records', headers=owner).json()['items'][0]['failure_code'] == 'CONSENT_OR_EMAIL_REQUIRED'

def test_concurrent_slot_claims_only_one_succeeds(tmp_path):
    app, _ = app_with_inventory(tmp_path)
    owner = {'X-Voice-Owner':'a' * 64}
    with TestClient(app) as client:
        lead = setup_lead(client, owner)
        day = next_open_day()
        start = client.get(f'/api/v1/appointments/availability?property_id=emerald-heights&day={day}', headers=owner).json()['slots'][0]['start_at']
        proposals = [client.post('/api/v1/appointments/proposals', headers=owner, json={
            'lead_id':lead['id'],'property_id':'emerald-heights','start_at':start}).json()['id'] for _ in range(2)]
        def book(index):
            return client.post('/api/v1/appointments/confirm', headers=owner, json={
                'proposal_id':proposals[index], 'idempotency_key':f'parallel-key-{index}-123456',
                'explicit_confirmation':True}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(book, range(2)))
        assert sorted(codes) == [200, 409]
        assert client.get('/api/v1/appointments', headers=owner).json()['total'] == 1

def test_provider_adapter_contracts_are_mocked(tmp_path):
    path = tmp_path / 'service.json'
    path.write_text('{}')
    settings = Settings(_env_file=None, google_calendar_id='dedicated-test-calendar',
                        google_application_credentials=str(path), hubspot_access_token='mock-token')
    calendar = GoogleCalendar(settings)
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {'calendars': {'dedicated-test-calendar': {'busy': []}}}
    with patch.object(calendar, '_headers', return_value={'Authorization':'Bearer mock'}), patch('app.automation.providers.httpx.Client') as client:
        client.return_value.__enter__.return_value.post.return_value = Response()
        assert calendar.busy(datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1)) == []
        assert client.return_value.__enter__.return_value.post.call_args.args[0].endswith('/freeBusy')
    from unittest.mock import MagicMock
    appointment = MagicMock(id='12345678-1234-1234-1234-123456789abc',
        start_at=datetime.now(timezone.utc), end_at=datetime.now(timezone.utc) + timedelta(minutes=30), timezone='Asia/Kolkata')
    class EventResponse(Response):
        def json(self): return {'id':'vocalead12345678123412341234123456789abc'}
    with patch.object(calendar, '_headers', return_value={'Authorization':'Bearer mock'}), patch.object(calendar, 'get_event', return_value=None), patch('app.automation.providers.httpx.Client') as client:
        client.return_value.__enter__.return_value.post.return_value = EventResponse()
        event_id = calendar.create_event(appointment, 'Emerald Heights')
        assert event_id == 'vocalead12345678123412341234123456789abc'
        payload = client.return_value.__enter__.return_value.post.call_args.kwargs['json']
        assert payload['start']['dateTime'].endswith('+00:00')
    class DeletedResponse(Response):
        status_code = 204
    with patch.object(calendar, '_headers', return_value={'Authorization':'Bearer mock'}), patch('app.automation.providers.httpx.Client') as client:
        client.return_value.__enter__.return_value.delete.return_value = DeletedResponse()
        calendar.cancel_event(event_id)
        assert client.return_value.__enter__.return_value.delete.called
    hubspot = HubSpotCRM(settings)
    from app.models.customer import Customer, Lead
    customer = Customer(id=str(uuid4()), owner_hash='a' * 64, email='demo@example.test', contact_consent=True)
    lead = Lead(id=str(uuid4()), customer_id=customer.id)
    class ContactResponse(Response):
        def json(self): return {'results':[{'id':'12345'}]}
    with patch('app.automation.providers.httpx.Client') as client:
        client.return_value.__enter__.return_value.post.return_value = ContactResponse()
        assert hubspot.upsert_contact(customer, lead) == '12345'
        payload = client.return_value.__enter__.return_value.post.call_args.kwargs['json']
        assert payload['inputs'][0]['idProperty'] == 'email'

def test_calendar_timeout_reconciles_without_duplicate_write(tmp_path):
    app, _ = app_with_inventory(tmp_path, calendar_provider='google')
    owner = {'X-Voice-Owner':'a' * 64}
    with TestClient(app) as client:
        lead = setup_lead(client, owner)
        day = next_open_day()
        with patch('app.automation.providers.GoogleCalendar') as adapter, patch('app.automation.sync.GoogleCalendar') as sync_adapter:
            adapter.return_value.busy.return_value = []
            sync_adapter.return_value.create_event.side_effect = httpx.TimeoutException('remote outcome unknown')
            start = client.get(f'/api/v1/appointments/availability?property_id=emerald-heights&day={day}', headers=owner).json()['slots'][0]['start_at']
            proposal = client.post('/api/v1/appointments/proposals', headers=owner, json={
                'lead_id':lead['id'],'property_id':'emerald-heights','start_at':start}).json()
            booked = client.post('/api/v1/appointments/confirm', headers=owner, json={
                'proposal_id':proposal['id'],'idempotency_key':'reconcile-key-123456','explicit_confirmation':True}).json()
            assert booked['status'] == 'PENDING'
            assert booked['operations'][0]['status'] == 'RECONCILE_REQUIRED'
            assert client.post(f"/api/v1/appointments/{booked['id']}/sync", headers=owner).status_code == 409
            sync_adapter.return_value.get_event.return_value = {'status':'confirmed'}
            reconciled = client.post(f"/api/v1/appointments/{booked['id']}/reconcile", headers=owner)
            assert reconciled.status_code == 200 and reconciled.json()['status'] == 'CONFIRMED'
            assert reconciled.json()['calendar_sync_status'] == 'SYNCED'
            assert client.get('/api/v1/crm/records', headers=owner).json()['items'][0]['lifecycle_status'] == 'VISIT_BOOKED'
            assert sync_adapter.return_value.create_event.call_count == 1
