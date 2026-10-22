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
    # Baseline checks stay offline; hybrid cases explicitly enable the provider mock.
    monkeypatch.setenv('FOLIO_RETRIEVAL_MODE', 'bm25')
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
    (b'hello\x00', 'a.txt', 'text/plain', 415, 'unsupported_file_type'),
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
        assert body['generationConfig']['maxOutputTokens'] == 4096
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


@pytest.mark.parametrize('pdf', [False, True])
def test_complete_ask_path(client, tmp_path, model_env, monkeypatch, pdf):
    from app.storage.database import _storage
    older = upload(client, make_pdf() if pdf else b'Ten shelters opened.',
                   'report.pdf' if pdf else 'report.txt',
                   'application/pdf' if pdf else 'text/plain').json()
    newer = upload(client, b'Twenty shelters opened.', report_date='2026-10-21').json()
    calls = []

    def respond(request):
        prompt = json.loads(request.content)['contents'][0]['parts'][0]['text']
        context = json.loads(prompt.split('INPUT_JSON:\n', 1)[1])
        calls.append(context)
        assert {p['doc_id'] for p in context['passages']} == {older['doc_id']}
        passage = next(p for p in context['passages'] if 'Ten shelters' in p['text'])
        result = {'status': 'answered', 'claims': [{
            'text': 'Ten shelters opened.', 'citations': [{
                'passage_id': passage['passage_id'], 'quote': 'Ten shelters opened.'}]}]}
        return httpx.Response(200, json={'modelVersion': 'test', 'candidates': [{
            'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(result)}]}}]})

    mock_model_transport(model_env, monkeypatch, respond)
    for restart in [False, True]:
        if restart:
            _storage.cache_clear()  # Simulate losing every process-local index.
        response = client.post('/ask', json={'question': 'How many shelters opened?',
                                            'doc_ids': [older['doc_id']]})
        assert response.status_code == 200, response.text
        answer = AskResponse.model_validate(response.json())
        assert answer.status == 'answered'
        assert answer.answer == 'Ten shelters opened.'
        citation = answer.claims[0].citations[0]
        evidence = client.get('/passages/' + citation.passage_id).json()
        assert citation.quote in evidence['text']
        assert citation.doc_id != newer['doc_id']
        assert citation.page == (1 if pdf else None)
        assert answer.meta.cached is False
    assert len(calls) == 2


@pytest.mark.parametrize('failure', ['unknown_id', 'unselected_id', 'unretrieved_id',
                                    'bad_quote', 'uncited', 'malformed', 'timeout', 'provider'])
def test_ask_rejects_invalid_generation(client, tmp_path, model_env, monkeypatch, failure):
    from app.storage.database import get_storage
    selected = upload(client, b'Ten shelters opened.').json()['doc_id']
    other = upload(client, b'Twenty shelters opened.').json()['doc_id']
    rows = stored_passages(tmp_path)
    selected_passage = next(p for p in rows if p['doc_id'] == selected)
    other_passage = next(p for p in rows if p['doc_id'] == other)
    if failure == 'unretrieved_id':
        # A selected document alone is insufficient: citation must be in context.
        monkeypatch.setattr(get_storage(), 'retrieve', lambda *args: [Passage.model_validate(other_passage)])
    citation = {'passage_id': selected_passage['passage_id'], 'quote': 'Ten shelters opened.'}
    if failure == 'unknown_id':
        citation['passage_id'] = 'invented'
    if failure == 'unselected_id':
        citation = {'passage_id': other_passage['passage_id'], 'quote': 'Twenty shelters opened.'}
    if failure == 'bad_quote':
        citation['quote'] = 'One hundred shelters opened.'

    def respond(request):
        if failure == 'timeout':
            raise httpx.ReadTimeout('private secret', request=request)
        if failure == 'provider':
            return httpx.Response(503, text='private secret')
        result = {'status': 'answered', 'claims': [{'text': 'Ten shelters opened.',
                   'citations': [] if failure == 'uncited' else [citation]}]}
        text = 'not JSON' if failure == 'malformed' else json.dumps(result)
        return httpx.Response(200, json={'modelVersion': 'test', 'candidates': [{
            'finishReason': 'STOP', 'content': {'parts': [{'text': text}]}}]})

    mock_model_transport(model_env, monkeypatch, respond)
    response = client.post('/ask', json={'question': 'shelters', 'doc_ids': (
        [selected, other] if failure == 'unretrieved_id' else [selected])})
    assert response.status_code == (504 if failure == 'timeout' else 502)
    assert 'private secret' not in response.text


def test_ask_empty_evidence_and_unknown_selection(client, monkeypatch):
    from app.generation import answer
    def fail():
        pytest.fail('No model call should be made')
    monkeypatch.setattr(answer, 'get_model_client', fail)
    doc_id = upload(client, b'Ten shelters opened.').json()['doc_id']
    response = client.post('/ask', json={'question': 'astronauts', 'doc_ids': [doc_id]})
    assert response.status_code == 200
    assert response.json()['status'] == 'insufficient_evidence'
    assert response.json()['claims'] == []
    assert 'enough evidence' in response.json()['answer']
    response = client.post('/ask', json={'question': 'shelters', 'doc_ids': [doc_id, 'missing']})
    assert response.status_code == 404
    assert response.json()['detail']['code'] == 'document_not_found'


def test_model_can_report_insufficient_evidence(client, model_env, monkeypatch):
    doc_id = upload(client, b'Ten shelters opened.').json()['doc_id']
    def respond(request):
        return httpx.Response(200, json={'modelVersion': 'test', 'candidates': [{
            'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps({
                'status': 'insufficient_evidence', 'claims': []})}]}}]})
    mock_model_transport(model_env, monkeypatch, respond)
    response = client.post('/ask', json={'question': 'Who funds shelters?', 'doc_ids': [doc_id]})
    assert response.status_code == 200
    assert response.json()['status'] == 'insufficient_evidence'
    assert response.json()['claims'] == []


def test_index_failure_rolls_back_upload(client, tmp_path, monkeypatch):
    from app.storage.database import Storage, get_storage
    doc_id = upload(client, b'Ten shelters opened.').json()['doc_id']
    original_ids = [p.passage_id for p in get_storage().retrieve('shelters', [doc_id])]
    def fail(connection):
        raise OSError('private path')
    monkeypatch.setattr(Storage, '_build_index', staticmethod(fail))
    response = upload(client, b'Twenty shelters opened.')
    assert response.status_code == 500
    assert len(client.get('/documents').json()['documents']) == 1
    assert len(stored_passages(tmp_path)) == 1
    assert len(list((tmp_path / 'uploads').iterdir())) == 1
    assert [p.passage_id for p in get_storage().retrieve('shelters', [doc_id])] == original_ids


@pytest.fixture
def w4_corpus(client):
    """Upload the real W4 TXT inputs with normal production ingestion wiring."""
    from app.storage.database import get_storage
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'corpus/manifest.json').read_text(encoding='utf-8'))
    cases = json.loads((root / 'eval/questions.json').read_text(encoding='utf-8'))
    uploaded = {}
    for document in sorted(manifest['documents'], key=lambda row: row['heldout']):
        path = root / 'corpus' / document['file']
        response = client.post('/documents', files={
            'file': (path.name, path.read_bytes(), document['media_type']),
        }, data={key: document[key] for key in ('title', 'report_date', 'source_url')})
        assert response.status_code == 201, response.text
        uploaded[document['doc_id']] = response.json()
    return uploaded, cases, get_storage()


@pytest.mark.parametrize('case_number', range(7), ids=lambda n: f'W4-{n + 1:02}')
def test_w4_questions_retrieve_gold_evidence_and_resolve_citations(
        client, w4_corpus, model_env, monkeypatch, case_number):
    from app.storage.database import _storage
    uploaded, evaluation, storage = w4_corpus
    case = evaluation['questions'][case_number]
    selected = [uploaded[key]['doc_id'] for key in case['selected_document_ids']]
    model_calls = []

    def respond(request):
        prompt = json.loads(request.content)['contents'][0]['parts'][0]['text']
        context = json.loads(prompt.split('INPUT_JSON:\n', 1)[1])
        model_calls.append(context)
        assert len(context['passages']) <= 6
        assert {p['doc_id'] for p in context['passages']} <= set(selected)
        citations = []
        for expected in case['supporting_passages']:
            document = uploaded[expected['doc_id']]
            passage = next((p for p in context['passages']
                            if p['doc_id'] == document['doc_id'] and expected['quote'] in p['text']), None)
            assert passage is not None, f"Missing W4 gold evidence for {case['id']}"
            for field in ('title', 'report_date', 'source_url'):
                assert passage[field] == document[field]
            assert passage['page'] is None
            citations.append({'passage_id': passage['passage_id'], 'quote': expected['quote']})
        result = {'status': 'answered', 'claims': [
            {'text': case['expected_answer'], 'citations': citations},
        ]}
        return httpx.Response(200, json={'modelVersion': 'test', 'candidates': [{
            'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(result)}]}}]})

    mock_model_transport(model_env, monkeypatch, respond)
    expected = storage.retrieve(case['question'], selected)
    assert expected
    # Same result regardless of selection order or losing process-local indexes.
    assert storage.retrieve(case['question'], list(reversed(selected))) == expected
    _storage.cache_clear()
    response = client.post('/ask', json={'question': case['question'], 'doc_ids': selected})
    assert response.status_code == 200, response.text
    answer = AskResponse.model_validate(response.json())
    assert answer.status == 'answered'
    assert answer.answer == case['expected_answer']
    assert len(model_calls) == 1
    for claim in answer.claims:
        for citation in claim.citations:
            passage = client.get('/passages/' + citation.passage_id).json()
            assert citation.quote in passage['text']
            assert citation.doc_id in selected
            for field in ('doc_id', 'title', 'report_date', 'source_url', 'page'):
                assert citation.model_dump(mode='json')[field] == passage[field]


def test_w4_stored_retriever_refresh_and_snapshot_citations(client, w4_corpus, tmp_path):
    from app.retrieval import BM25Index, StoredPassageRetriever
    uploaded, evaluation, storage = w4_corpus
    selected = [uploaded['articles-2026']['doc_id']]
    query = evaluation['questions'][0]['question']
    search = StoredPassageRetriever(storage.list_passages)
    expected = search(query, selected)
    assert expected
    snapshot = tmp_path / 'bm25.json'
    search.save(snapshot)
    restarted = BM25Index.load(snapshot)
    assert restarted.retrieve(query, selected) == expected
    for passage in restarted.retrieve(query, selected):
        assert client.get('/passages/' + passage.passage_id).json() == passage.model_dump(mode='json')
    fresh = upload(client, b'Zephyrlight is the name of the new shelter.').json()
    assert search('Zephyrlight', [fresh['doc_id']])
    assert search(query, selected) == expected
    assert search('Zephyrlight', selected) == []


def test_w4_chunks_preserve_transcript_boundaries_and_metadata():
    from app.ingestion import extract_text_pages, ingest_document
    root = Path(__file__).resolve().parents[2]
    documents = json.loads((root / 'corpus/manifest.json').read_text(encoding='utf-8'))['documents']
    for document in documents:
        path = root / 'corpus' / document['file']
        pages = extract_text_pages(document['doc_id'], path)
        chunks = ingest_document(path, document)
        assert ''.join(chunk.text for chunk in chunks) == path.read_bytes().decode('utf-8-sig')
        assert chunks == ingest_document(path, document)
        for chunk in chunks:
            assert any(chunk.text in page.text for page in pages)
            assert len(chunk.text.split()) <= 500
            assert chunk.page is None
            assert chunk.doc_id == document['doc_id']
            assert chunk.title == document['title']
            assert chunk.report_date.isoformat() == document['report_date']
            assert str(chunk.source_url) == document['source_url']


def test_w4_insufficient_evidence_uses_normal_answer_path(client, w4_corpus, model_env, monkeypatch):
    uploaded, evaluation, storage = w4_corpus
    case = evaluation['questions'][7]
    selected = [uploaded[key]['doc_id'] for key in case['selected_document_ids']]
    calls = []
    assert case['expected_status'] == 'insufficient_evidence'
    assert storage.retrieve(case['question'], selected)  # Lexical matches alone are not an answer.

    def respond(request):
        context = json.loads(json.loads(request.content)['contents'][0]['parts'][0]['text'].split(
            'INPUT_JSON:\n', 1)[1])
        calls.append(context)
        assert {p['doc_id'] for p in context['passages']} <= set(selected)
        return httpx.Response(200, json={'modelVersion': 'test', 'candidates': [{
            'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps({
                'status': 'insufficient_evidence', 'claims': []})}]}}]})

    mock_model_transport(model_env, monkeypatch, respond)
    response = client.post('/ask', json={'question': case['question'], 'doc_ids': selected})
    assert response.status_code == 200
    assert len(calls) == 1
    assert response.json()['status'] == 'insufficient_evidence'
    assert response.json()['claims'] == []
    assert 'enough evidence' in response.json()['answer']


@pytest.mark.parametrize('status,phrase', [
    (402, 'billing and quota'), (429, 'rate limited'), (403, 'credentials or access'),
])
def test_provider_rejections_are_actionable_and_safe(client, model_env, monkeypatch, status, phrase):
    doc_id = upload(client, b'Ten shelters opened.').json()['doc_id']

    def respond(request):
        payload = json.loads(request.content)
        assert payload['generationConfig']['responseMimeType'] == 'application/json'
        return httpx.Response(status, text='private provider message and secret')

    mock_model_transport(model_env, monkeypatch, respond)
    response = client.post('/ask', json={'question': 'shelters', 'doc_ids': [doc_id]})
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'generation_failed'
    assert phrase in response.json()['detail']['message']
    assert 'private provider' not in response.text
    assert 'secret' not in response.text


@pytest.mark.parametrize('tamper', ['foreign', 'altered', 'missing'])
def test_retrieval_boundary_rejects_noncanonical_evidence(client, monkeypatch, tamper):
    from app.storage.database import get_storage
    from app.generation import answer
    selected = upload(client, b'Ten shelters opened.').json()['doc_id']
    other = upload(client, b'Twenty shelters opened.').json()['doc_id']
    storage = get_storage()
    original = next(p for p in storage.list_passages() if p.doc_id == selected)
    if tamper == 'foreign':
        invalid = next(p for p in storage.list_passages() if p.doc_id == other)
    elif tamper == 'missing':
        invalid = original.model_copy(update={'passage_id': 'nonexistent'})
    else:
        invalid = original.model_copy(update={'text': 'One hundred shelters opened.'})
    monkeypatch.setattr(storage, 'retrieve', lambda *args: [invalid])

    def fail():
        pytest.fail('Noncanonical evidence must not be sent to the provider')

    monkeypatch.setattr(answer, 'get_model_client', fail)
    response = client.post('/ask', json={'question': 'shelters', 'doc_ids': [selected]})
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'generation_failed'


@pytest.mark.parametrize('embedding_fails', [False, True])
def test_hybrid_ask_preserves_wire_contract_citations_and_comparison(
        client, model_env, monkeypatch, embedding_fails):
    from app.retrieval import hybrid
    monkeypatch.setattr(hybrid, 'load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setenv('FOLIO_RETRIEVAL_MODE', 'hybrid')
    calls = []

    def respond(request):
        calls.append(request.url.path)
        data = json.loads(request.content)
        if request.url.path.endswith(':batchEmbedContents'):
            if embedding_fails:
                return httpx.Response(429, text='private quota details')
            return httpx.Response(200, json={'embeddings': [
                {'values': [1.0] + [0.0] * 767} for _ in data['requests']]})
        context = json.loads(data['contents'][0]['parts'][0]['text'].split('INPUT_JSON:\n', 1)[1])
        assert {p['doc_id'] for p in context['passages']} == {older['doc_id']}
        evidence = context['passages'][0]
        result = {'status': 'answered', 'claims': [{
            'text': 'Three people killed.', 'citations': [{
                'passage_id': evidence['passage_id'], 'quote': 'Three people killed.'}]}]}
        return httpx.Response(200, json={'modelVersion': 'test', 'candidates': [{
            'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(result)}]}}]})

    mock_model_transport(model_env, monkeypatch, respond)
    older = upload(client, b'Three people killed.').json()
    newer = upload(client, b'Six people killed.', report_date='2026-10-21').json()
    question = 'people killed' if embedding_fails else 'fatalities'
    response = client.post('/ask', json={'question': question, 'doc_ids': [older['doc_id']]})
    assert response.status_code == 200, response.text
    answer = AskResponse.model_validate(response.json())
    assert answer.status == 'answered'
    assert answer.meta.retrieval_mode == 'bm25'  # Existing v1 compatibility field.
    assert set(response.json()) == {'question', 'doc_ids', 'status', 'answer', 'claims', 'meta'}
    citation = answer.claims[0].citations[0]
    evidence = client.get('/passages/' + citation.passage_id).json()
    assert citation.quote in evidence['text']
    assert citation.doc_id == older['doc_id']
    assert sum(path.endswith(':generateContent') for path in calls) == 1
    assert client.post('/compare', json={
        'older_doc_id': older['doc_id'], 'newer_doc_id': newer['doc_id']}).status_code == 501
