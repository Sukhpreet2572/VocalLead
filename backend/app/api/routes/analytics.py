from datetime import date
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.api.routes.leads import owner_key
from app.api.routes.voice import require_local
from app.analytics.service import metrics
from app.database import get_session

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"], dependencies=[Depends(require_local)])

def scoped(db: Session, owner: str | None, start: date | None, end: date | None) -> dict:
    if start and end and (start > end or (end - start).days > 366):
        raise HTTPException(422, "Invalid date range")
    return metrics(db, owner_key(owner), start, end)

@router.get("/overview")
def overview(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
             start: date | None = None, end: date | None = None) -> dict:
    return scoped(db, x_voice_owner, start, end)

@router.get("/leads")
def leads(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
          start: date | None = None, end: date | None = None) -> dict:
    return scoped(db, x_voice_owner, start, end)["leads"]

@router.get("/appointments")
def appointments(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
                 start: date | None = None, end: date | None = None) -> dict:
    return scoped(db, x_voice_owner, start, end)["appointments"]

@router.get("/interactions")
def interactions(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
                 start: date | None = None, end: date | None = None) -> dict:
    return scoped(db, x_voice_owner, start, end)["interactions"]

@router.get("/property-demand")
def property_demand(db: Session = Depends(get_session), x_voice_owner: str | None = Header(default=None),
                    start: date | None = None, end: date | None = None) -> dict:
    return scoped(db, x_voice_owner, start, end)["property_demand"]
