"""Exercise Phase 5 local business automation against the configured database."""
import json
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

def run() -> dict:
    settings = Settings()
    if settings.app_env != "development" or settings.calendar_provider != "local" or settings.crm_provider != "local":
        raise RuntimeError("Verification requires local development calendar and CRM modes")
    header = {"X-Voice-Owner": secrets.token_hex(32)}
    other = {"X-Voice-Owner": secrets.token_hex(32)}
    with TestClient(create_app(settings)) as client:
        lead_response = client.post("/api/v1/leads/demo", headers=header)
        lead_response.raise_for_status()
        lead = lead_response.json()
        updated = client.patch(f"/api/v1/leads/{lead['id']}", headers=header, json={
            "location": "Gurugram", "configuration": "3 BHK", "max_budget_inr": 12_000_000,
            "purchase_intent": "STRONG", "timeline_months": 2, "site_visit_interest": True})
        updated.raise_for_status()
        assert updated.json()["score"] == 90
        properties = client.get("/api/v1/properties").json()
        assert any(p["id"] == "emerald-heights" and any(u["configuration"] == "3 BHK" and u["price_inr"] <= 12_000_000 for u in p["units"]) for p in properties)
        local_day = datetime.now(ZoneInfo("Asia/Kolkata")).date() + timedelta(days=2)
        while local_day.weekday() == 0: local_day += timedelta(days=1)
        query = f"/api/v1/appointments/availability?property_id=emerald-heights&day={local_day}"
        available = client.get(query, headers=header); available.raise_for_status()
        slot = available.json()["slots"][0]
        proposed = client.post("/api/v1/appointments/proposals", headers=header, json={
            "lead_id": lead["id"], "property_id": "emerald-heights", "start_at": slot["start_at"]})
        proposed.raise_for_status()
        payload = {"proposal_id": proposed.json()["id"], "idempotency_key": secrets.token_hex(20), "explicit_confirmation": True}
        booked = client.post("/api/v1/appointments/confirm", headers=header, json=payload); booked.raise_for_status()
        appointment = booked.json()
        assert appointment["status"] == "CONFIRMED"
        assert slot["start_at"] not in [x["start_at"] for x in client.get(query, headers=header).json()["slots"]]
        again = client.post("/api/v1/appointments/confirm", headers=header, json=payload); again.raise_for_status()
        assert again.json()["id"] == appointment["id"]
        assert client.get("/api/v1/crm/records", headers=header).json()["items"][0]["lifecycle_status"] == "VISIT_BOOKED"
        assert client.get(f"/api/v1/appointments/{appointment['id']}", headers=other).status_code == 404
        assert client.get("/api/v1/appointments", headers=header).json()["total"] >= 1
        cancelled = client.post(f"/api/v1/appointments/{appointment['id']}/cancel", headers=header); cancelled.raise_for_status()
        assert cancelled.json()["status"] == "CANCELLED"
        assert slot["start_at"] in [x["start_at"] for x in client.get(query, headers=header).json()["slots"]]
        return {"lead_score": 90, "appointment_status": "CANCELLED", "duplicate_prevented": True,
                "owner_isolation": True, "slot_released": True, "crm_lifecycle_at_booking": "VISIT_BOOKED"}

if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
