import json
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.config import ROOT, Settings
from app.database import Base, build_engine, session_factory
from app.main import create_app
from app.models.customer import Lead, LeadScoreHistory
from app.models.property import Property, PropertyUnit
from app.intelligence.service import parse_budget, parse_message, sentiment
from app.intelligence.provider import extract_with_gemini, sentiment_with_gemini
from unittest.mock import MagicMock, patch

def seeded_app(tmp_path):
    settings = Settings(_env_file=None, app_env="development", database_url=f"sqlite:///{tmp_path / 'test.db'}")
    engine = build_engine(settings)
    Base.metadata.create_all(engine)
    with session_factory(engine)() as db:
        for item in json.loads((ROOT / "knowledge_base/properties/inventory.json").read_text(encoding="utf-8")):
            db.add(Property(**{key: item[key] for key in ('id','name','location','type','status','possession','amenities','connectivity','payment')},
                            units=[PropertyUnit(**unit) for unit in item['units']]))
        db.commit()
    engine.dispose()
    return create_app(settings)

def test_parser_and_signal_boundaries():
    assert parse_budget("1 crore 20 lakh") == 12_000_000
    assert parse_budget("85 lakh") == 8_500_000
    assert parse_message("I want a 3 BHK in Gurgaon, max budget 1.2 crore").max_budget_inr == 12_000_000
    assert parse_message("Just browsing").purchase_intent is None
    assert sentiment("This is too expensive")[1] == "PRICE_CONCERN"

def test_gemini_structured_contract_with_mock():
    settings = Settings(_env_file=None, google_api_key="test-key")
    client = MagicMock()
    client.__enter__.return_value.models.generate_content.side_effect = [
        MagicMock(text='{"configuration":"3 BHK","max_budget_inr":12000000}'),
        MagicMock(text='{"sentiment":"MIXED","business_signal":"PRICE_CONCERN","evidence":"too expensive"}')]
    with patch('app.intelligence.provider.genai.Client', return_value=client):
        assert extract_with_gemini("3 BHK max 1.2 crore", settings).max_budget_inr == 12_000_000
        assert sentiment_with_gemini("too expensive", settings).business_signal == "PRICE_CONCERN"

def test_persistent_score_correction_and_isolation(tmp_path):
    app = seeded_app(tmp_path)
    headers = {"X-Voice-Owner": "a" * 64}
    with TestClient(app) as client:
        created = client.post("/api/v1/leads/demo", headers=headers)
        assert created.status_code == 201
        lead_id = created.json()["id"]
        update = client.patch(f"/api/v1/leads/{lead_id}", headers=headers, json={
            "location": "Gurugram", "configuration": "3 BHK", "max_budget_inr": 12_000_000,
            "purchase_intent": "STRONG", "timeline_months": 2, "site_visit_interest": True})
        assert update.status_code == 200
        assert update.json()["score"] == 90
        assert update.json()["classification"] == "HOT"
        assert update.json()["score_components"]["inventory_match"]["points"] == 30
        correction = client.post(f"/api/v1/leads/{lead_id}/messages", headers=headers,
                                 json={"message": "Actually I can stretch my maximum budget to 1.3 crore"})
        assert correction.status_code == 200
        assert correction.json()["lead"]["max_budget_inr"] == 13_000_000
        assert correction.json()["lead"]["location"] == "Gurugram"
        assert client.get("/api/v1/leads/summary", headers=headers).json()["hot"] == 1
        assert client.get(f"/api/v1/leads/{lead_id}", headers={"X-Voice-Owner": "b" * 64}).status_code == 404
        assert client.get("/api/v1/leads", headers={"X-Voice-Owner": "b" * 64}).json()["total"] == 0
        assert len(client.get(f"/api/v1/leads/{lead_id}", headers=headers).json()["score_history"]) == 1
        assert "phone" not in client.get(f"/api/v1/leads/{lead_id}", headers=headers).json()

def test_invalid_budget_and_production_access(tmp_path):
    app = seeded_app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/v1/leads/demo", headers={"X-Voice-Owner": "a" * 64})
        lead_id = response.json()["id"]
        assert client.patch(f"/api/v1/leads/{lead_id}", headers={"X-Voice-Owner": "a" * 64},
                            json={"max_budget_inr": -1}).status_code == 422
    settings = Settings(_env_file=None, app_env="production", database_url=f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/leads", headers={"X-Voice-Owner": "a" * 64}).status_code == 403
