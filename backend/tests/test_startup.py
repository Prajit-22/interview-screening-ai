"""Safe read-only model-list diagnostics and full real HTTP LLM simulation."""
import importlib.util
from dataclasses import replace
from pathlib import Path
import httpx
import pytest
from app.config import Settings, ROOT

spec = importlib.util.spec_from_file_location('check_model', ROOT / 'scripts/check_model.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

@pytest.mark.parametrize('status,body,expected', [
    (200, {'data': [{'id': 'llama-3.1-8b-instant'}]}, 0),
    (200, {'data': [{'id': 'llama-3.3-70b-versatile'}]}, 1),
    (401, {'error': 'PRIVATE_KEY'}, 1),
    (403, {'error': 'PRIVATE_KEY'}, 1),
    (404, {'error': 'PRIVATE_KEY'}, 1),
    (200, [], 1),
])
def test_safe_model_list(status, body, expected, capsys):
    s = replace(Settings(), mode='llm', base_url='https://api.groq.com/openai/v1',
                model='llama-3.1-8b-instant', api_key='PRIVATE_KEY')
    def handler(request):
        assert str(request.url) == 'https://api.groq.com/openai/v1/models'
        assert request.headers['Authorization'] == 'Bearer PRIVATE_KEY'
        return httpx.Response(status, json=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert probe.check(s, client) == expected
    assert 'PRIVATE_KEY' not in capsys.readouterr().out


def test_no_key_does_not_call_network(capsys):
    s = replace(Settings(), api_key='ollama')
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('Network called'))) as client:
        assert probe.check(s, client) == 1
    assert 'No hosted-model key loaded' in capsys.readouterr().out
"""Exercise the full model-backed API against a local OpenAI-compatible HTTP server."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import replace
from fastapi.testclient import TestClient
from app.config import Settings, ROOT
from app.main import create_app


def test_real_http_model_full_lifecycle(tmp_path, monkeypatch):
    # A stale system proxy must not divert model calls to an unrelated 404 endpoint.
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
    monkeypatch.setenv('HTTPS_PROXY', 'http://127.0.0.1:1')
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, payload['model']))
            assert self.path == '/openai/v1/chat/completions'
            assert self.headers['Authorization'] == 'Bearer fake-local-key'
            data = json.loads(payload['messages'][1]['content'])
            q = {'text': f'For a hypothetical {data["skill"]} project, how would you apply the passage idea to test {data["topic"]}?',
                 'focus': data['topic'], 'rationale': 'Connects the selected skill to textbook evidence.',
                 'evidence_quote': data['passage'][:120], 'citation_ids': [data['passage_id']]}
            body = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(q)}}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        s = replace(Settings(), mode='llm', model='llama-3.1-8b-instant', api_key='fake-local-key',
                    base_url=f'http://127.0.0.1:{server.server_port}/openai/v1', database=tmp_path / 'http.db')
        with TestClient(create_app(s)) as client:
            r = client.post('/api/sessions', data={'role': 'ai-ml'},
                            files={'resume': ('resume.txt', (ROOT/'examples/resume.txt').read_bytes())})
            assert r.status_code == 201, r.text
            session = r.json()
            assert session['mode'] == 'llm'
            assert len(requests) == 3
            for q in session['questions']:
                assert q['model'] == 'llama-3.1-8b-instant'
                r = client.post('/api/sessions/'+session['id']+'/answers',
                                json={'question_id': q['id'], 'answer': 'I would test assumptions on held-out examples.'})
                assert r.status_code == 200
            assert r.json()['status'] == 'complete'
            assert client.get('/api/sessions/'+session['id']).json()['summary']['answered'] == 3
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_groq_gpt_oss_json_budget_and_reasoning(settings=None):
    from unittest.mock import patch
    from app.services.generation import Generator
    s = replace(Settings(), mode='llm', base_url='https://api.groq.com/openai/v1',
                model='openai/gpt-oss-20b', api_key='not-a-real-key', json_schema=False)
    p = {'anchor': 'RAG', 'topic': 'similarity', 'difficulty': 'foundational'}
    evidence = [{'id': 'p20-c0', 'text': 'Similarity can compare the directions of feature vectors.'}]
    valid = {'text': 'How would you compare two vectors in a hypothetical RAG retrieval project?',
             'focus': 'similarity', 'rationale': 'Connects RAG to similarity', 'citation_ids': ['p20-c0'],
             'evidence_quote': evidence[0]['text']}
    response = httpx.Response(200, request=httpx.Request('POST', s.base_url+'/chat/completions'),
                              json={'choices': [{'finish_reason': 'stop', 'message': {
                                  'content': json.dumps(valid), 'reasoning': 'Do not parse this field'}}]})
    with patch('httpx.Client.post', return_value=response) as post:
        assert Generator(s).model_question({'skills': ['RAG']}, 'ai-ml', p, evidence, []) == valid
        request = post.call_args.kwargs['json']
        assert request['response_format'] == {'type': 'json_object'}
        assert request['max_completion_tokens'] == 4096 and 'max_tokens' not in request
        assert request['include_reasoning'] is False and request['reasoning_effort'] == 'low'
        assert 'reasoning_format' not in request
