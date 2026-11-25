"""External adapters. Live writes require explicit provider configuration and credentials."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from app.core.config import Settings
from app.models.appointment import Appointment
from app.models.customer import Customer, Lead

class ProviderUnavailable(Exception):
    pass

class TimedRequest(Request):
    def __call__(self, url, method="GET", body=None, headers=None, timeout=8, **kwargs):
        return super().__call__(url, method=method, body=body, headers=headers, timeout=min(timeout, 8), **kwargs)

def utc_iso(value: datetime) -> str:
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()

def event_id_for(appointment_id: str) -> str:
    return "vocalead" + appointment_id.replace("-", "")

class GoogleCalendar:
    BASE = "https://www.googleapis.com/calendar/v3"
    SCOPES = ["https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/calendar.freebusy"]

    def __init__(self, settings: Settings):
        self.calendar_id = settings.google_calendar_id
        path = settings.google_application_credentials.get_secret_value()
        if not self.calendar_id or not path or not Path(path).is_file():
            raise ProviderUnavailable("Google Calendar configuration incomplete")
        self.path = path

    def _headers(self) -> dict[str, str]:
        credentials = service_account.Credentials.from_service_account_file(self.path, scopes=self.SCOPES)
        credentials.refresh(TimedRequest())
        return {"Authorization": f"Bearer {credentials.token}"}

    def busy(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        with httpx.Client(timeout=8) as client:
            response = client.post(f"{self.BASE}/freeBusy", headers=self._headers(),
                json={"timeMin": start.isoformat(), "timeMax": end.isoformat(),
                      "items": [{"id": self.calendar_id}]})
            response.raise_for_status()
        calendar = response.json().get("calendars", {}).get(self.calendar_id, {})
        if calendar.get("errors"): raise ProviderUnavailable("Calendar free/busy denied")
        return [(datetime.fromisoformat(x["start"].replace("Z", "+00:00")),
                 datetime.fromisoformat(x["end"].replace("Z", "+00:00"))) for x in calendar.get("busy", [])]

    def get_event(self, event_id: str) -> dict | None:
        with httpx.Client(timeout=8) as client:
            response = client.get(f"{self.BASE}/calendars/{quote(self.calendar_id, safe='')}/events/{quote(event_id, safe='')}", headers=self._headers())
        if response.status_code == 404: return None
        response.raise_for_status()
        return response.json()

    def create_event(self, appointment: Appointment, property_name: str) -> str:
        event_id = event_id_for(appointment.id)
        existing = self.get_event(event_id)
        if existing: return event_id
        body = {"id": event_id, "summary": f"Site visit: {property_name}",
                "description": "VocaLead synthetic demonstration booking",
                "start": {"dateTime": utc_iso(appointment.start_at), "timeZone": appointment.timezone},
                "end": {"dateTime": utc_iso(appointment.end_at), "timeZone": appointment.timezone}}
        with httpx.Client(timeout=8) as client:
            response = client.post(f"{self.BASE}/calendars/{quote(self.calendar_id, safe='')}/events",
                                   headers=self._headers(), json=body)
        if response.status_code == 409 and self.get_event(event_id): return event_id
        response.raise_for_status()
        return response.json()["id"]

    def cancel_event(self, event_id: str) -> None:
        with httpx.Client(timeout=8) as client:
            response = client.delete(f"{self.BASE}/calendars/{quote(self.calendar_id, safe='')}/events/{quote(event_id, safe='')}", headers=self._headers())
        if response.status_code not in (204, 404, 410): response.raise_for_status()

class HubSpotCRM:
    URL = "https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert"

    def __init__(self, settings: Settings):
        self.token = settings.hubspot_access_token.get_secret_value()
        if not self.token: raise ProviderUnavailable("HubSpot configuration incomplete")

    def upsert_contact(self, customer: Customer, lead: Lead) -> str | None:
        if not customer.contact_consent or not customer.email:
            return None  # Email is the supported unique identifier; phone-only cannot safely upsert.
        properties = {"email": customer.email}
        if customer.display_name: properties["firstname"] = customer.display_name
        if customer.phone: properties["phone"] = customer.phone
        with httpx.Client(timeout=8) as client:
            response = client.post(self.URL, headers={"Authorization": f"Bearer {self.token}"},
                json={"inputs": [{"id": customer.email, "idProperty": "email", "properties": properties}]})
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results: raise ProviderUnavailable("HubSpot upsert returned no contact")
        return str(results[0]["id"])
