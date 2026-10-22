"""API/storage checks, deferred generation, and two-sided evidence rules."""
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
def client(tmp_path, monkeypatch):
    from app.main import app
    monkeypatch.setenv('FOLIO_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FOLIO_DATABASE_PATH', str(tmp_path / 'folio.sqlite3'))
    monkeypatch.delenv('FOLIO_MAX_UPLOAD_BYTES', raising=False)
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
    ('post', '/ask', {'json': {'question': 'What happened?', 'doc_ids': ['doc_older']}}),
    ('post', '/compare', {'json': {'older_doc_id': 'doc_older', 'newer_doc_id': 'doc_newer'}}),
])
def test_features_are_explicit_stubs(client, method, path, kwargs):
    response = client.request(method, path, **kwargs)
    assert response.status_code == 501
    assert response.json()['detail']['code'] == 'not_implemented'


def upload(client, content=b'Example report.', filename='sample.txt',
           media_type='text/plain', **metadata):
    return client.post('/documents', files={'file': (filename, content, media_type)},
                       data={'title': 'Example', 'report_date': '2026-10-20', **metadata})


def stored_passages(tmp_path):
    import sqlite3
    with sqlite3.connect(tmp_path / 'folio.sqlite3') as db:
        return [json.loads(row[0]) for row in db.execute('SELECT payload FROM passages')]


def test_upload_persistence_and_exact_evidence(client, tmp_path):
    from app.main import app
    assert client.get('/documents').json() == {'documents': []}
    content = 'Ten shelters opened.\nRésumé — report.\n'.encode()
    response = upload(client, content, filename='../../report.txt',
                      source_url='https://example.org/report')
    assert response.status_code == 201
    doc = response.json()
    assert doc['filename'] == 'report.txt'
    assert doc['source_url'] == 'https://example.org/report'
    assert doc['report_date'] == '2026-10-20'
    assert doc['passage_count'] == 1
    assert doc['status'] == 'ready'
    assert 'original_path' not in doc
    assert list((tmp_path / 'uploads').iterdir())[0].read_bytes() == content
    passage = stored_passages(tmp_path)[0]
    assert passage['text'] == content.decode()
    assert passage['page'] is None
    assert passage['doc_id'] == doc['doc_id']
    with TestClient(app) as restarted:
        assert restarted.get('/documents').json() == {'documents': [doc]}
        assert restarted.get('/passages/' + passage['passage_id']).json() == passage
    duplicate = upload(client, content).json()
    assert duplicate['doc_id'] != doc['doc_id']
    assert client.get('/passages/' + passage['passage_id']).json() == passage


def test_list_ordering_and_unknown_passage(client):
    for day in ['2026-10-22', '2026-10-20', '2026-10-20']:
        assert upload(client, report_date=day).status_code == 201
    documents = client.get('/documents').json()['documents']
    assert documents == sorted(documents, key=lambda d: (d['report_date'], d['doc_id']))
    assert documents[0]['source_url'] is None
    response = client.get('/passages/unknown')
    assert response.status_code == 404
    assert response.json()['detail']['code'] == 'passage_not_found'


@pytest.mark.parametrize('content,filename,mime,status,code', [
    (b'', 'a.txt', 'text/plain', 422, 'invalid_document'),
    (b' \n\t', 'a.txt', 'text/plain', 422, 'invalid_document'),
    (b'\xff\xfe', 'a.txt', 'text/plain', 422, 'invalid_document'),
    (b'hello\x00', 'a.txt', 'text/plain', 422, 'invalid_document'),
    (b'hello', 'a.exe', 'text/plain', 415, 'unsupported_file_type'),
    (b'hello', 'a.pdf', 'text/plain', 415, 'unsupported_file_type'),
    (b'hello', 'a.pdf', 'application/pdf', 415, 'unsupported_file_type'),
    (b'%PDF-1.7 broken', 'a.pdf', 'application/pdf', 422, 'invalid_document'),
    (b'%PDF-1.7', 'a.txt', 'text/plain', 415, 'unsupported_file_type'),
    (b'PK\x03\x04zip', 'a.txt', 'text/plain', 415, 'unsupported_file_type'),
    (b'x' * (10485760 + 1), 'a.txt', 'text/plain', 413, 'upload_too_large'),
])
def test_invalid_uploads_publish_nothing(client, tmp_path, content, filename, mime, status, code):
    response = upload(client, content, filename, mime)
    assert response.status_code == status
    assert response.json()['detail']['code'] == code
    assert client.get('/documents').json() == {'documents': []}
    assert stored_passages(tmp_path) == []
    assert list((tmp_path / 'uploads').iterdir()) == []


@pytest.mark.parametrize('metadata', [
    {'title': '   '}, {'title': 'x' * 201}, {'report_date': '2026-02-30'},
    {'source_url': 'file:///tmp/source'}, {'source_url': 'not a URL'},
    {'report_date': '0'}, {'report_date': '2026-10-20T00:00:00Z'},
])
def test_upload_metadata_validation(client, metadata):
    assert upload(client, **metadata).status_code == 422
    assert client.get('/documents').json() == {'documents': []}


def make_pdf(*, blank=False, encrypted=False):
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    for text in ['Ten shelters opened.', 'Twelve shelters opened.']:
        page = writer.add_blank_page(width=300, height=300)
        if not blank:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
                DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(f'BT /F1 12 Tf 10 100 Td ({text}) Tj ET'.encode())
            page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('password')
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_upload_preserves_physical_pages(client, tmp_path):
    response = upload(client, make_pdf(), 'report.pdf', 'application/pdf')
    assert response.status_code == 201
    assert response.json()['passage_count'] == 2
    passages = stored_passages(tmp_path)
    assert [p['page'] for p in passages] == [1, 2]
    assert 'Ten shelters' in passages[0]['text']
    assert 'Twelve shelters' in passages[1]['text']
    for passage in passages:
        assert client.get('/passages/' + passage['passage_id']).json() == passage


@pytest.mark.parametrize('options', [{'blank': True}, {'encrypted': True}])
def test_unusable_pdfs(client, tmp_path, options):
    response = upload(client, make_pdf(**options), 'report.pdf', 'application/pdf')
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'invalid_document'
    assert client.get('/documents').json() == {'documents': []}
    assert not list((tmp_path / 'uploads').iterdir())


def test_replaceable_ingestion_and_database_rollback(client, tmp_path, monkeypatch):
    from app.main import app
    from app.storage.ingestion import get_ingestor
    from app.storage.database import Storage

    def ingest(**kwargs):
        assert kwargs['path'].read_bytes() == b'Example report.'
        return [Passage(passage_id='w2_passage', text='W2 extracted text', page=None,
                        **{key: kwargs[key] for key in ['doc_id', 'title', 'report_date', 'source_url']})]

    app.dependency_overrides[get_ingestor] = lambda: ingest
    try:
        first = upload(client)
        assert first.status_code == 201
        assert client.get('/passages/w2_passage').json()['text'] == 'W2 extracted text'
        # Duplicate passage IDs cause INSERT failure after the document INSERT.
        failed = upload(client)
        assert failed.status_code == 500
        assert failed.json()['detail']['code'] == 'storage_failed'
        assert len(client.get('/documents').json()['documents']) == 1
        assert len(list((tmp_path / 'uploads').iterdir())) == 1
    finally:
        app.dependency_overrides.clear()

    def fail(*args):
        raise OSError('/private/path/secret')

    monkeypatch.setattr(Storage, 'save', fail)
    response = upload(client)
    assert response.status_code == 500
    assert 'secret' not in response.text
    assert len(list((tmp_path / 'uploads').iterdir())) == 1


def test_missing_upload_fields(client):
    assert client.post('/documents', data={'title': 'Example'}).status_code == 422


def test_configured_upload_limit(client, monkeypatch):
    monkeypatch.setenv('FOLIO_MAX_UPLOAD_BYTES', '15')
    assert upload(client, b'x' * 15).status_code == 201
    assert upload(client, b'x' * 16).status_code == 413


def test_cors_local_frontend(client):
    response = client.options('/documents', headers={
        'Origin': 'http://localhost:3000', 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:3000'


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
