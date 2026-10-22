"""Foundation checks: wire shapes, explicit stubs, and two-sided evidence rules."""
import json
import asyncio
import re
from pathlib import Path

import pytest
import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contracts import (
    AskRequest, AskResponse, CompareRequest, CompareResponse,
    ComparisonChange, DocumentList, Health, Passage,
)

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_health_and_openapi_contract(client):
    assert Health.model_validate(client.get('/health').json()).status == 'ok'
    schema = client.get('/openapi.json').json()
    expected = {
        '/health': {'get'}, '/documents': {'get', 'post'},
        '/ask': {'post'}, '/compare': {'post'}, '/passages/{id}': {'get'},
    }
    assert {path: set(ops) for path, ops in schema['paths'].items()} == expected
    assert 'multipart/form-data' in schema['paths']['/documents']['post']['requestBody']['content']
    for path, methods in expected.items():
        for method in methods:
            operation = schema['paths'][path][method]
            success = '201' if (path, method) == ('/documents', 'post') else '200'
            assert 'schema' in operation['responses'][success]['content']['application/json']


@pytest.mark.parametrize('method,path,kwargs', [
    ('get', '/documents', {}),
    ('get', '/passages/pas_example', {}),
    ('post', '/documents', {
        'files': {'file': ('sample.txt', b'Example report.', 'text/plain')},
        'data': {'title': 'Example', 'report_date': '2026-10-20'},
    }),
    ('post', '/ask', {'json': {'question': 'What happened?', 'doc_ids': ['doc_older']}}),
    ('post', '/compare', {'json': {'older_doc_id': 'doc_older', 'newer_doc_id': 'doc_newer'}}),
])
def test_features_are_explicit_stubs(client, method, path, kwargs):
    response = client.request(method, path, **kwargs)
    assert response.status_code == 501
    assert response.json()['detail']['code'] == 'not_implemented'


def test_selection_validation():
    with pytest.raises(ValidationError):
        AskRequest(question='What happened?', doc_ids=[])
    with pytest.raises(ValidationError):
        AskRequest(question='What happened?', doc_ids=['same', 'same'])
    with pytest.raises(ValidationError):
        AskRequest(question='   ', doc_ids=['doc_older'])
    with pytest.raises(ValidationError):
        CompareRequest(older_doc_id='same', newer_doc_id='same')


def test_documented_success_examples_match_models():
    contract = (Path(__file__).resolve().parents[2] / 'docs/api-contract.md').read_text()
    examples = [json.loads(block) for block in re.findall(r'```json\n(.*?)\n```', contract, re.S)]
    for model, key in [(Health, 'status'), (DocumentList, 'documents'), (Passage, 'text'),
                       (AskResponse, 'answer'), (CompareResponse, 'changes')]:
        example = next(item for item in examples if key in item and (model is not Health or item[key] == 'ok'))
        model.model_validate(example)
    comparison = next(item for item in examples if 'changes' in item)
    change = comparison['changes'][0]
    ComparisonChange.model_validate(change)
    for side in ['older_citations', 'newer_citations']:
        with pytest.raises(ValidationError):
            ComparisonChange.model_validate({**change, side: []})
    ComparisonChange.model_validate({**change, 'kind': 'added', 'before': None, 'older_citations': []})
    with pytest.raises(ValidationError):
        ComparisonChange.model_validate({**change, 'kind': 'added'})


@pytest.fixture
def model_env(monkeypatch):
    from app.generation import client
    monkeypatch.setattr(client, 'load_dotenv', lambda *args, **kwargs: None)
    for key in ['GEMINI_API_KEY', 'GOOGLE_API_KEY', 'GEMINI_MODEL',
                'GEMINI_TIMEOUT_SECONDS', 'GEMINI_MAX_OUTPUT_TOKENS']:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('GOOGLE_API_KEY', 'test-secret-fallback')
    return client


def test_model_backend_configuration(model_env, monkeypatch):
    client = model_env.get_model_client()
    assert client.api_key.get_secret_value() == 'test-secret-fallback'
    assert 'test-secret-fallback' not in repr(client)
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret-primary')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')
    monkeypatch.setenv('GEMINI_TIMEOUT_SECONDS', '5')
    monkeypatch.setenv('GEMINI_MAX_OUTPUT_TOKENS', '256')
    client = model_env.get_model_client()
    assert client.api_key.get_secret_value() == 'test-secret-primary'
    assert client.model_id == 'gemini-3.5-flash-lite'
    assert (client.timeout_seconds, client.max_output_tokens) == (5, 256)


@pytest.mark.parametrize('key,value', [
    ('GOOGLE_API_KEY', ''), ('GEMINI_MODEL', '../other-provider'),
    ('GEMINI_TIMEOUT_SECONDS', 'nan'), ('GEMINI_TIMEOUT_SECONDS', '121'),
    ('GEMINI_MAX_OUTPUT_TOKENS', '0'), ('GEMINI_MAX_OUTPUT_TOKENS', 'oops'),
])
def test_invalid_model_config_is_safe(model_env, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(model_env.GenerationError):
        model_env.get_model_client()


def mock_model_transport(model_env, monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(model_env.httpx, 'Client', lambda **kwargs: real_client(
        transport=httpx.MockTransport(handler), **kwargs,
    ))


def test_model_request_and_result(model_env, monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        assert request.headers['x-goog-api-key'] == 'test-secret-fallback'
        assert str(request.url) == (
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent'
        )
        assert 'test-secret-fallback' not in str(request.url)
        body = json.loads(request.content)
        assert body['contents'][0]['parts'] == [{'text': 'Hello'}]
        assert body['generationConfig']['maxOutputTokens'] == 1024
        return httpx.Response(200, json={
            'modelVersion': 'gemini-3.8-flash',
            'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
                {'text': 'private reasoning', 'thought': True}, {'text': 'Hello Folio'},
            ]}}],
        })

    mock_model_transport(model_env, monkeypatch, respond)
    result = model_env.get_model_client().generate('Hello')
    assert len(calls) == 1
    assert result.text == 'Hello Folio'
    assert result.model_version == 'gemini-3.8-flash'
    assert result.elapsed_ms >= 0


@pytest.mark.parametrize('failure', ['http', 'network', 'timeout', 'empty', 'blocked', 'truncated', 'invalid_json'])
def test_model_failures_map_to_safe_api_errors(model_env, monkeypatch, failure):
    from fastapi import FastAPI

    calls = []
    real_client = httpx.AsyncClient

    def respond(request):
        calls.append(request)
        if failure == 'network':
            raise httpx.ConnectError('test-secret-fallback', request=request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('test-secret-fallback', request=request)
        if failure == 'http':
            return httpx.Response(401, text='test-secret-fallback')
        if failure == 'invalid_json':
            return httpx.Response(200, text='test-secret-fallback')
        if failure == 'empty':
            return httpx.Response(200, json={'candidates': []})
        reason = 'MAX_TOKENS' if failure == 'truncated' else 'SAFETY'
        return httpx.Response(200, json={'candidates': [{'finishReason': reason}]})

    mock_model_transport(model_env, monkeypatch, respond)
    app = FastAPI()
    app.add_exception_handler(model_env.GenerationError, model_env.generation_error_handler)

    @app.get('/test-model')
    async def generate():
        return model_env.get_model_client().generate('Hello')

    async def call_api():
        async with real_client(transport=httpx.ASGITransport(app), base_url='http://test') as api:
            return await api.get('/test-model')

    response = asyncio.run(call_api())
    assert len(calls) == 1
    assert response.status_code == (504 if failure == 'timeout' else 502)
    assert response.json()['detail']['code'] == (
        'generation_timeout' if failure == 'timeout' else 'generation_failed'
    )
    assert 'test-secret-fallback' not in response.text
    assert 'provider_http_status' not in response.text
    assert 'reason' not in response.json()['detail']


@pytest.mark.parametrize('failure,expected_reason', [
    ('http', 'provider_http_error'), ('network', 'network_error'),
    ('timeout', 'timeout'), ('truncated', 'output_token_limit'),
])
def test_model_smoke_records_safe_diagnostics(model_env, monkeypatch, tmp_path, capsys,
                                            failure, expected_reason):
    from app.generation import smoke

    def respond(request):
        if failure == 'network':
            raise httpx.ConnectError('test-secret-fallback', request=request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('test-secret-fallback', request=request)
        if failure == 'http':
            return httpx.Response(429, text='test-secret-fallback')
        return httpx.Response(200, json={'candidates': [{'finishReason': 'MAX_TOKENS'}]})

    mock_model_transport(model_env, monkeypatch, respond)
    path = tmp_path / 'smoke.json'
    monkeypatch.setattr(smoke, 'RECORD_PATH', path)
    assert smoke.run() == 1
    record = json.loads(path.read_text())
    assert record['success'] is False
    assert record['error']['reason'] == expected_reason
    if failure == 'http':
        assert record['error']['provider_http_status'] == 429
    assert 'test-secret-fallback' not in path.read_text()
    assert 'test-secret-fallback' not in capsys.readouterr().out
