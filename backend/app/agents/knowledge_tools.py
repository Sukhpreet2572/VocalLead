"""Agent tools share the exact retrieval service used by the API."""
import asyncio
from livekit.agents import function_tool
from app.core.config import Settings
from app.database import build_engine, session_factory
from app.rag.service import KnowledgeService


def _search(query: str, max_budget_inr: int | None = None, configuration: str | None = None,
            location: str | None = None, category: str | None = None, property_id: str | None = None) -> str:
    settings = Settings()
    engine = build_engine(settings)
    try:
        with session_factory(engine)() as db:
            result = KnowledgeService(settings).search(db, query, max_budget_inr=max_budget_inr,
                configuration=configuration, location=location, category=category, property_id=property_id)
            if not result["evidence_available"]:
                return "No verified source evidence found. Say you cannot confirm the answer."
            sources = "; ".join(f"{hit['source']}: {hit['text'][:500]}" for hit in result["hits"])
            candidates = "; ".join(f"{item['name']} {item['configuration']} INR {item['price_inr']} available {item['available']}" for item in result["candidates"])
            return f"Verified source excerpts: {sources}. Canonical eligible units: {candidates}"
    finally:
        engine.dispose()


@function_tool
async def search_properties(query: str, max_budget_inr: int | None = None,
                            configuration: str | None = None, location: str | None = None) -> str:
    """Search fictional property facts and apply strict unit price, layout and location filters."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(_search, query, max_budget_inr, configuration, location), 60)
    except Exception:
        return "Property knowledge is unavailable; do not guess."


@function_tool
async def get_property_details(property_id: str, question: str) -> str:
    """Retrieve sourced details for a known fictional property identifier."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(_search, question, None, None, None, "brochures", property_id), 60)
    except Exception:
        return "Property details are unavailable; do not guess."


@function_tool
async def search_company_knowledge(question: str) -> str:
    """Search site visit, payment and buyer policy documents."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(_search, question, None, None, None, "company_policies"), 60)
    except Exception:
        return "Company knowledge is unavailable; do not guess."
