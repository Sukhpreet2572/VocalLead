"""Measure retrieval, never final LLM answer quality."""
import json
import statistics
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings
from app.database import build_engine, session_factory
from app.rag.service import KnowledgeService

if __name__ == "__main__":
    cases = json.loads((ROOT / "backend/tests/fixtures/rag_evaluation.json").read_text(encoding="utf-8"))
    settings = Settings()
    engine = build_engine(settings)
    try:
        service = KnowledgeService(settings)
        results = []
        with session_factory(engine)() as db:
            for case in cases:
                result = service.search(db, case["query"], category=case.get("category"), **case.get("filters", {}))
                found = [hit["property_id"] for hit in result["hits"] if hit["property_id"]]
                expected = case.get("expected_property_ids", [])
                hit = any(item in found for item in expected) if expected else any(case.get("expected_source", "") in item["source"] for item in result["hits"])
                ranks = [index + 1 for index, item in enumerate(found) if item in expected]
                violation = any(item["price_inr"] > case["filters"]["max_budget_inr"] for item in result["candidates"]) if case.get("filters", {}).get("max_budget_inr") else False
                results.append({"query": case["query"], "sources": [item["source"] for item in result["hits"]],
                                "hit": hit, "recall": len(set(found) & set(expected))/len(expected) if expected else None,
                                "rr": 1/min(ranks) if ranks else 0, "abstain_ok": not result["evidence_available"] if case.get("abstain") else None,
                                "violation": violation, "latency": result["duration_ms"]})
        judged = [item for item in results if item["abstain_ok"] is None]
        print(json.dumps({"queries": len(results), "hit_rate": sum(item["hit"] for item in judged)/len(judged),
                          "recall_at_k": statistics.mean(item["recall"] for item in judged if item["recall"] is not None),
                          "mrr": statistics.mean(item["rr"] for item in judged),
                          "strict_filter_violations": sum(item["violation"] for item in results),
                          "no_evidence_correct": sum(item["abstain_ok"] is True for item in results),
                          "no_evidence_cases": sum(item["abstain_ok"] is not None for item in results),
                          "mean_latency_ms": round(statistics.mean(item["latency"] for item in results),1),
                          "cases": [{"query": item["query"], "hit": item["hit"], "sources": item["sources"]} for item in results]}, indent=2))
    finally:
        engine.dispose()
