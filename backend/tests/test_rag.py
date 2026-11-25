import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import ROOT, Settings
from app.database import Base, build_engine, session_factory
from app.main import create_app
from app.models.property import Property
from app.rag.chunker import chunks
from app.rag.service import KnowledgeService, load_text


def test_inventory_and_stable_chunks():
    records = json.loads((ROOT / 'knowledge_base/properties/inventory.json').read_text(encoding='utf-8'))
    assert len(records) == 6
    assert len({item['id'] for item in records}) == 6
    assert any(unit['configuration'] == '3 BHK' and unit['price_inr'] <= 12_000_000 and unit['available'] > 0
               for item in records if 'Gurugram' in item['location'] for unit in item['units'])
    assert chunks('doc', 'some useful text', 200, 20) == chunks('doc', 'some useful text', 200, 20)


def test_loader_rejects_outside_path(tmp_path):
    path = tmp_path / 'outside.md'
    path.write_text('private')
    try:
        load_text(path)
        assert False
    except ValueError:
        pass


def test_strict_unit_filter_and_sources(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
                        chroma_persist_directory=str(tmp_path / 'chroma'), embedding_provider='gemini')
    engine = build_engine(settings)
    Base.metadata.create_all(engine)
    with session_factory(engine)() as db:
        records = json.loads((ROOT / 'knowledge_base/properties/inventory.json').read_text(encoding='utf-8'))
        from app.models.property import PropertyUnit
        for item in records:
            db.add(Property(**{key:item[key] for key in ('id','name','location','type','status','possession','amenities','connectivity','payment')},
                            units=[PropertyUnit(**unit) for unit in item['units']]))
        db.commit()
        service = KnowledgeService(settings)
        service.collection.add(ids=['test-1'], embeddings=[[1.0, 0.0]], documents=['A family play area at Palm Grove Estate'],
                               metadatas=[{'source':'brochures/palm-grove.md','property_id':'palm-grove','category':'brochures','document_id':'test'}])
        fake = type('Embedder', (), {'embed': lambda self, texts, task_type: [[1.0, 0.0]]})()
        with patch('app.rag.service.selected', return_value=fake):
            result = service.search(db, 'family apartment', max_budget_inr=12_000_000, configuration='3 BHK', location='Gurugram')
        assert result['evidence_available']
        assert result['hits'][0]['source'] == 'brochures/palm-grove.md'
        assert all(item['price_inr'] <= 12_000_000 and item['configuration'] == '3 BHK' for item in result['candidates'])
        assert 'urban-crest' not in {item['property_id'] for item in result['candidates']}
    engine.dispose()


def test_search_api_validation(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
                        chroma_persist_directory=str(tmp_path / 'chroma'))
    app = create_app(settings)
    with TestClient(app) as client:
        Base.metadata.create_all(app.state.session_factory.kw['bind'])
        assert client.post('/api/v1/knowledge/search', json={'query':'x'}).status_code == 422
        assert client.post('/api/v1/knowledge/search', json={'query':'valid question','top_k':50}).status_code == 422
        assert client.get('/api/v1/knowledge/status').status_code == 200
