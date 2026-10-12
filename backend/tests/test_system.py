"""Real corpus integration tests + model-contract tests. No paid API dependency."""
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient
from app.config import Settings, ROOT
from app.main import create_app
from app.services.resume import parse_resume
from app.services.generation import Generator, ModelUnavailable, plan
from app.services.knowledge import KnowledgeBase
from app.db import Database

RESUME = (ROOT / 'examples/resume.txt').read_bytes()


@pytest.fixture(scope='module')
def settings(tmp_path_factory):
    return replace(Settings(), database=tmp_path_factory.mktemp('db') / 'test.db', mode='practice')


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def start(client, role='ai-ml'):
    response = client.post('/api/sessions', data={'role': role}, files={'resume': ('resume.txt', RESUME)})
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_roles(client):
    assert client.get('/api/health').json()['chunks'] > 100
    assert len(client.get('/api/roles').json()) == 3


def test_complete_and_persist(client, settings):
    s = start(client)
    assert s['profile']['skills'] and s['mode'] == 'practice'
    for q in s['questions']:
        assert set(q['citation_ids']) <= {c['id'] for c in q['sources']}
        assert q['corpus_sha256'] and q['plan']['anchor'] in s['profile']['skills']
        result = client.post(f'/api/sessions/{s["id"]}/answers', json={'question_id': q['id'], 'answer': 'I would use separate training and held-out test sets, fit preprocessing only on training records, then validate feature distributions and evaluate generalization before deployment.'})
        assert result.status_code == 200
    s = result.json()
    assert s['status'] == 'complete' and s['summary']['answered'] == 3
    # Simulate a fresh process/database object; neither sessions nor vectors are volatile.
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get('/api/sessions/' + s['id']).json()['summary'] == s['summary']
    with Database(settings.database).connect() as db:
        assert db.execute('SELECT count(*) FROM questions WHERE session_id=? AND answer IS NOT NULL', (s['id'],)).fetchone()[0] == 3


def test_order_duplicate_and_blank(client):
    s = start(client)
    path = f'/api/sessions/{s["id"]}/answers'
    assert client.post(path, json={'question_id': s['questions'][1]['id'], 'answer': 'Wrong order'}).status_code == 409
    qid = s['questions'][0]['id']
    assert client.post(path, json={'question_id': qid, 'answer': '   '}).status_code == 422
    assert client.post(path, json={'question_id': qid, 'answer': 'First valid answer'}).status_code == 200
    assert client.post(path, json={'question_id': qid, 'answer': 'Overwrite attempt'}).status_code == 409
    assert client.get('/api/sessions/' + s['id']).json()['questions'][0]['answer'] == 'First valid answer'


def test_delete_cascades(client, settings):
    s = start(client)
    assert client.delete('/api/sessions/' + s['id']).status_code == 204
    assert client.get('/api/sessions/' + s['id']).status_code == 404
    with Database(settings.database).connect() as db:
        assert db.execute('SELECT count(*) FROM questions WHERE session_id=?', (s['id'],)).fetchone()[0] == 0


@pytest.mark.parametrize('filename,content', [('bad.exe', b'not a resume'), ('bad.pdf', b'fake pdf'), ('empty.txt', b''), ('short.txt', b'Hi'), ('utf8.txt', b'\xff' * 80), ('huge.txt', b'x' * (2 * 1024 * 1024 + 1))])
def test_bad_uploads(client, filename, content):
    assert client.post('/api/sessions', data={'role': 'ai-ml'}, files={'resume': (filename, content)}).status_code == 422


def test_unknown_role(client):
    assert client.post('/api/sessions', data={'role': 'astronaut'}, files={'resume': ('resume.txt', RESUME)}).status_code == 422


def test_resume_and_role_change_plans():
    profile = parse_resume('resume.txt', RESUME)
    a = plan(profile, 'ai-ml', 3)
    b = plan(profile, 'backend', 3)
    other = parse_resume('other.txt', (ROOT / 'examples/backend-resume.txt').read_bytes())
    c = plan(other, 'ai-ml', 3)
    assert a != b and a != c and a[0]['anchor'] == 'RAG' and b[0]['anchor'] == 'FastAPI'


def test_retrieval_relevant_and_reloads(settings):
    db = Database(settings.database)
    kb = KnowledgeBase(db, settings.corpus); kb.load()
    hits = kb.search('precision recall classification false positive false negative')
    assert any('precision' in h['text'].lower() or 'recall' in h['text'].lower() for h in hits)
    kb2 = KnowledgeBase(db, settings.corpus); kb2.load()
    assert hits == kb2.search('precision recall classification false positive false negative')
    assert len({h['page'] for h in hits}) == len(hits)


def test_model_json_contract(settings):
    p = {'anchor': 'RAG', 'topic': 'similarity', 'difficulty': 'foundational'}
    evidence = [{'id': 'p20-c0', 'text': 'Similarity can compare the directions of feature vectors.'}]
    valid = {'text': 'How would you compare two vectors in your RAG retrieval project?', 'focus': 'similarity', 'rationale': 'Connects RAG to similarity', 'citation_ids': ['p20-c0'], 'evidence_quote': 'Similarity can compare the directions of feature vectors.'}
    generator = Generator(replace(settings, mode='llm'))
    def response(obj):
        return httpx.Response(200, request=httpx.Request('POST', 'http://test'), json={'choices': [{'message': {'content': json.dumps(obj)}}]})
    with patch('httpx.Client.post', return_value=response(valid)):
        assert generator.model_question({'skills': ['RAG']}, 'ai-ml', p, evidence, []) == valid
    for broken in [{**valid, 'citation_ids': ['made-up']}, {**valid, 'text': 'Too short'}, {**valid, 'citation_ids': []}, ['not an object']]:
        with patch('httpx.Client.post', return_value=response(broken)):
            with pytest.raises(ModelUnavailable):
                generator.model_question({'skills': ['RAG']}, 'ai-ml', p, evidence, [])
    with patch('httpx.Client.post', side_effect=httpx.ReadTimeout('timeout')):
        with pytest.raises(ModelUnavailable):
            generator.model_question({'skills': ['RAG']}, 'ai-ml', p, evidence, [])


def test_model_failure_saves_no_partial_session(settings):
    llm_settings = replace(settings, mode='llm')
    with TestClient(create_app(llm_settings)) as client:
        with Database(settings.database).connect() as conn:
            before = conn.execute('SELECT count(*) FROM sessions').fetchone()[0]
        with patch('app.services.generation.Generator.generate', side_effect=ModelUnavailable('Model unavailable')):
            response = client.post('/api/sessions', data={'role': 'ai-ml'}, files={'resume': ('resume.txt', RESUME)})
        assert response.status_code == 502
        with Database(settings.database).connect() as conn:
            assert conn.execute('SELECT count(*) FROM sessions').fetchone()[0] == before


def test_missing_corpus_is_actionable(settings, tmp_path):
    with TestClient(create_app(replace(settings, database=tmp_path / 'empty.db', corpus=tmp_path / 'absent.pdf'))) as client:
        assert client.get('/api/health').json()['status'] == 'not_ready'
        assert client.post('/api/sessions', data={'role': 'ai-ml'}, files={'resume': ('resume.txt', RESUME)}).status_code == 503
