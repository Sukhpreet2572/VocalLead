"""Small persistent semantic index; relational inventory decides eligible units."""
import hashlib
import json
import time
import re
from pathlib import Path

import chromadb
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ROOT, Settings
from app.models.property import KnowledgeDocument, Property, PropertyUnit
from app.rag.chunker import chunks
from app.rag.embeddings import selected


def source_files() -> list[Path]:
    base = ROOT / "knowledge_base"
    return sorted(path for path in base.rglob("*") if path.suffix.lower() in (".md", ".txt", ".json", ".pdf") and path.is_file())


def load_text(path: Path) -> str:
    if not path.resolve().is_relative_to((ROOT / "knowledge_base").resolve()):
        raise ValueError("Document outside knowledge base")
    if path.stat().st_size > 2_000_000:
        raise ValueError("Document exceeds 2 MB")
    if path.suffix.lower() == ".pdf":
        import pymupdf
        with pymupdf.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        records = json.loads(raw)
        return "\n\n".join(json.dumps(item, ensure_ascii=False) for item in records)
    return raw


class KnowledgeService:
    def __init__(self, settings: Settings):
        self.settings = settings
        path = Path(settings.chroma_persist_directory)
        path = path if path.is_absolute() else ROOT / path
        self.client = chromadb.PersistentClient(path=str(path))
        self.model_name = settings.gemini_embedding_model or "gemini-embedding-001" if settings.embedding_provider == "gemini" else settings.local_embedding_model
        self.collection = self.client.get_or_create_collection(settings.rag_collection_name,
            metadata={"hnsw:space": "cosine", "provider": settings.embedding_provider, "model": self.model_name})
        if self.collection.metadata.get("provider") != settings.embedding_provider or self.collection.metadata.get("model") != self.model_name:
            raise ValueError("Collection embedding model differs; use a new RAG_COLLECTION_NAME")

    def ingest(self, db: Session) -> dict:
        embedder = selected(self.settings)
        added = skipped = 0
        for path in source_files():
            document_id = str(path.relative_to(ROOT / "knowledge_base")).replace("\\", "/")
            text = load_text(path)
            digest = hashlib.sha256(text.encode()).hexdigest()
            previous = db.get(KnowledgeDocument, document_id)
            if previous and previous.content_hash == digest and previous.status == "indexed":
                skipped += 1
                continue
            pieces = chunks(document_id, text, self.settings.rag_chunk_size, self.settings.rag_chunk_overlap)
            vectors = embedder.embed([part for _, part in pieces], "RETRIEVAL_DOCUMENT")
            if not vectors or any(len(vector) != len(vectors[0]) for vector in vectors):
                raise RuntimeError("Embedding dimensions invalid")
            old = self.collection.get(where={"document_id": document_id})
            self.collection.upsert(ids=[key for key, _ in pieces], documents=[part for _, part in pieces], embeddings=vectors,
                metadatas=[{"document_id": document_id, "source": document_id, "category": path.parent.name,
                            "property_id": path.stem if path.parent.name == "brochures" else "", "content_hash": digest,
                            "model": self.model_name, "dimensions": len(vectors[0])} for _ in pieces])
            obsolete = set(old["ids"]) - {key for key, _ in pieces}
            if obsolete:
                self.collection.delete(ids=list(obsolete))
            if previous is None:
                previous = KnowledgeDocument(id=document_id, source=document_id, category=path.parent.name,
                    property_id=path.stem if path.parent.name == "brochures" else None,
                    content_hash=digest, chunk_count=len(pieces), status="indexed")
                db.add(previous)
            else:
                previous.content_hash = digest
                previous.chunk_count = len(pieces)
                previous.status = "indexed"
            db.commit()
            added += 1
        return {"indexed": added, "skipped": skipped, "chunks": self.collection.count()}

    def search(self, db: Session, query: str, max_budget_inr: int | None = None,
               configuration: str | None = None, location: str | None = None,
               available_only: bool = True, category: str | None = None, top_k: int = 5,
               property_id: str | None = None) -> dict:
        started = time.monotonic()
        query = re.sub(r"\bgurgaon\b", "Gurugram", query, flags=re.I)
        if location:
            location = re.sub(r"\bgurgaon\b", "Gurugram", location, flags=re.I)
        candidates = []
        for unit in ([] if category in ("company_policies", "faqs") else db.scalars(select(PropertyUnit)).all()):
            prop = unit.property
            if max_budget_inr is not None and unit.price_inr > max_budget_inr: continue
            if configuration and unit.configuration.casefold() != configuration.casefold(): continue
            if location and location.casefold() not in prop.location.casefold(): continue
            if property_id and prop.id != property_id: continue
            if available_only and unit.available <= 0: continue
            candidates.append({"property_id": prop.id, "name": prop.name, "location": prop.location,
                               "configuration": unit.configuration, "price_inr": unit.price_inr,
                               "available": unit.available, "amenities": prop.amenities})
        if self.collection.count() == 0:
            raise RuntimeError("Knowledge index is empty; run ingestion")
        vector = selected(self.settings).embed([query], "RETRIEVAL_QUERY")[0]
        result = self.collection.query(query_embeddings=[vector], n_results=min(top_k * 4, self.collection.count()),
                                       include=["documents", "metadatas", "distances"])
        eligible_ids = {item["property_id"] for item in candidates}
        hits = []
        names = {item["property_id"]: item["name"].casefold() for item in candidates}
        for text, meta, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
            if distance > self.settings.rag_max_cosine_distance: continue
            if category and meta["category"] != category: continue
            if meta["property_id"] and meta["property_id"] not in eligible_ids: continue
            if property_id and meta["property_id"] != property_id: continue
            if not meta["property_id"] and (configuration or location or max_budget_inr) and category != "company_policies": continue
            exact_name = bool(meta["property_id"] and names.get(meta["property_id"], "") in query.casefold())
            hits.append({"text": text[:self.settings.rag_max_context_chars], "source": meta["source"],
                         "property_id": meta["property_id"] or None, "distance": distance,
                         "rank_score": 1 / (60 + len(hits) + 1) + (0.02 if exact_name else 0)})
        hits.sort(key=lambda item: item["rank_score"], reverse=True)
        hits = hits[:top_k]
        return {"candidates": candidates, "hits": hits, "evidence_available": bool(hits),
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
                "filters": {"max_budget_inr": max_budget_inr, "configuration": configuration, "location": location, "category": category}}
