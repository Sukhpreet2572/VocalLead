"""Idempotently seed the fictional inventory. Run from repository root."""
import json
import sys
from pathlib import Path
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings
from app.database import build_engine, session_factory
from app.models.property import Property, PropertyUnit


def seed() -> int:
    records = json.loads((ROOT / "knowledge_base/properties/inventory.json").read_text(encoding="utf-8"))
    engine = build_engine(Settings())
    try:
        with session_factory(engine)() as db:
            for item in records:
                if db.get(Property, item["id"]):
                    continue
                db.add(Property(**{key: item[key] for key in ("id", "name", "location", "type", "status", "possession", "amenities", "connectivity", "payment")},
                                units=[PropertyUnit(**unit) for unit in item["units"]]))
            db.commit()
            return len(db.scalars(select(Property)).all())
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(f"Seeded property count: {seed()}")
