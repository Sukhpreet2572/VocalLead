from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.routes.voice import require_local
from app.database import get_session
from app.models.property import Property, PropertyUnit, KnowledgeDocument
from app.rag.service import KnowledgeService

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    max_budget_inr: int | None = Field(default=None, gt=0)
    configuration: str | None = Field(default=None, max_length=30)
    location: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=40)
    top_k: int = Field(default=5, ge=1, le=20)


@router.get("/knowledge/status", dependencies=[Depends(require_local)])
def status(request: Request, db: Session = Depends(get_session)) -> dict:
    try:
        count = KnowledgeService(request.app.state.settings).collection.count()
        ready = count > 0
    except Exception:
        count, ready = 0, False
    return {"provider": request.app.state.settings.embedding_provider,
            "model": request.app.state.settings.gemini_embedding_model or "gemini-embedding-001" if request.app.state.settings.embedding_provider == "gemini" else request.app.state.settings.local_embedding_model,
            "ready": ready, "indexed_chunks": count,
            "indexed_documents": db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0,
            "property_count": db.scalar(select(func.count()).select_from(Property)) or 0}


@router.get("/knowledge/documents", dependencies=[Depends(require_local)])
def documents(db: Session = Depends(get_session)) -> list[dict]:
    return [{"id": item.id, "source": item.source, "category": item.category,
             "property_id": item.property_id, "chunk_count": item.chunk_count, "status": item.status}
            for item in db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.id)).all()]


def property_result(item: Property) -> dict:
    return {"id": item.id, "name": item.name, "location": item.location, "type": item.type,
            "status": item.status, "amenities": item.amenities,
            "units": [{"configuration": unit.configuration, "price_inr": unit.price_inr,
                       "available": unit.available, "carpet_sqft": unit.carpet_sqft} for unit in item.units]}


@router.get("/properties", dependencies=[Depends(require_local)])
def properties(db: Session = Depends(get_session), location: str | None = None,
               configuration: str | None = None, max_budget_inr: int | None = None) -> list[dict]:
    result = []
    for item in db.scalars(select(Property).order_by(Property.name)).all():
        if location and location.casefold() not in item.location.casefold(): continue
        data = property_result(item)
        data["units"] = [unit for unit in data["units"] if (not configuration or unit["configuration"].casefold() == configuration.casefold())
                         and (max_budget_inr is None or unit["price_inr"] <= max_budget_inr)]
        if data["units"]: result.append(data)
    return result


@router.get("/properties/{property_id}", dependencies=[Depends(require_local)])
def property_details(property_id: str, db: Session = Depends(get_session)) -> dict:
    item = db.get(Property, property_id)
    if not item: raise HTTPException(404, "Property not found")
    return property_result(item)


@router.post("/knowledge/search", dependencies=[Depends(require_local)])
def search(body: SearchRequest, request: Request, db: Session = Depends(get_session)) -> dict:
    try:
        return KnowledgeService(request.app.state.settings).search(db, **body.model_dump())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(503, str(exc))
    except Exception:
        raise HTTPException(503, "Semantic retrieval unavailable; check embedding configuration and ingestion")
