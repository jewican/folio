"""Foundation checks: wire shapes, explicit stubs, and two-sided evidence rules."""
import json
import re
from pathlib import Path

import pytest
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
