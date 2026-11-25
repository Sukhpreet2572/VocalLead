"""Ingest approved knowledge-base files using configured real embeddings."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings
from app.database import build_engine, session_factory
from app.rag.service import KnowledgeService

if __name__ == "__main__":
    settings = Settings()
    engine = build_engine(settings)
    try:
        with session_factory(engine)() as db:
            print(KnowledgeService(settings).ingest(db))
    finally:
        engine.dispose()
