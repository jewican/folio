"""Offline W4 handoff checks against W2 ingestion and the upload contract.

Run: python -m pytest -c backend/pytest.ini evaluation/test_corpus.py
These validate local text, not authenticity or publisher-source fidelity.
"""
from collections import Counter
from datetime import date
from hashlib import sha256
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import HttpUrl, TypeAdapter

from app.ingestion import IngestionMetadata, ingest_document
from app.retrieval import BM25Index

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'corpus'
MANIFEST = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))
DOCUMENTS = {item['doc_id']: item for item in MANIFEST['documents']}
EVALUATION = json.loads((ROOT / 'eval/questions.json').read_text(encoding='utf-8'))


def document_path(document):
    relative = Path(document['file'])
    assert not relative.is_absolute() and '..' not in relative.parts
    path = (CORPUS / relative).resolve()
    assert path.is_relative_to(CORPUS) and path.is_file()
    return path


def test_manifest_and_files_are_complete():
    assert len(DOCUMENTS) == len(MANIFEST['documents']) == 5
    paths = set()
    for doc_id, document in DOCUMENTS.items():
        IngestionMetadata.model_validate(document)
        assert date.fromisoformat(document['report_date']).isoformat() == document['report_date']
        assert document['status'] == 'ready'
        assert type(document['heldout']) is bool
        assert document['text_type']
        assert document['original_source_verified'] is False
        assert document['provenance_notes'].strip()
        assert document['media_type'] == 'text/plain'
        assert document['encoding'] == 'utf-8'
        for key in ('source_url', 'transcription_reference'):
            if document.get(key):
                TypeAdapter(HttpUrl).validate_python(document[key])
        path = document_path(document)
        assert path not in paths
        paths.add(path)
        assert path.parent.name == ('heldout' if document['heldout'] else 'initial')
        content = path.read_bytes()
        assert 0 < len(content) <= 10_485_760
        assert content.decode('utf-8').strip()
        markers = re.findall(
            r'(?:SOURCE PDF PAGE (\d+) / (\d+)|PDF PAGE (\d+) / (\d+)|PAGE (\d+) OF (\d+))',
            content.decode('utf-8'),
        )
        pages = [tuple(int(value) for value in marker if value) for marker in markers]
        if pages:
            assert all(total == pages[0][1] for _, total in pages)
            assert [number for number, _ in pages] == list(range(1, pages[0][1] + 1))
        assert document['size_bytes'] == len(content)
        assert document['sha256'] == sha256(content).hexdigest()
    assert paths == {path.resolve() for folder in ('initial', 'heldout')
                     for path in (CORPUS / folder).iterdir() if path.is_file()}
    initial = {key for key, doc in DOCUMENTS.items() if not doc['heldout']}
    heldout = set(DOCUMENTS) - initial
    assert len(initial) == 4 and len(heldout) == 1
    assert max(DOCUMENTS[key]['report_date'] for key in initial) < min(
        DOCUMENTS[key]['report_date'] for key in heldout)
    assert set(EVALUATION['stages']['before_upload']['available_document_ids']) == initial
    assert set(EVALUATION['stages']['before_upload']['excluded_document_ids']) == heldout
    assert set(EVALUATION['stages']['after_upload']['available_document_ids']) == set(DOCUMENTS)


def test_evaluation_paths_metadata_and_exact_quotes():
    assert ROOT / EVALUATION['manifest'] == CORPUS / 'manifest.json'
    inventory = EVALUATION['source_inventory']
    assert len(inventory) == len(DOCUMENTS)
    assert {row['doc_id'] for row in inventory} == set(DOCUMENTS)
    for row in inventory:
        document = DOCUMENTS[row['doc_id']]
        assert ROOT / row['file'] == document_path(document)
        assert row['available'] is True
        for key in ('report_date', 'text_type', 'original_source_verified'):
            assert row[key] == document[key]
    questions = EVALUATION['questions']
    assert len({q['id'] for q in questions}) == len(questions) == 10
    assert Counter(q['category'] for q in questions) == EVALUATION['question_counts']
    assert not EVALUATION['missing_manifest_documents']
    for question in questions:
        cases = [question]
        if 'before_upload_control' in question:
            cases.append(question['before_upload_control'])
            comparison = question['comparison_selection']
            assert set(comparison.values()) == set(question['selected_document_ids'])
            assert DOCUMENTS[comparison['older_doc_id']]['report_date'] < DOCUMENTS[
                comparison['newer_doc_id']]['report_date']
        for case in cases:
            selected = case['selected_document_ids']
            assert 1 <= len(selected) <= 5 and len(set(selected)) == len(selected)
            assert set(case['source_document_ids']) <= set(selected) <= set(DOCUMENTS)
            if case['run_stage'] == 'before_upload':
                assert all(not DOCUMENTS[key]['heldout'] for key in selected)
            for evidence in case['supporting_passages']:
                document = DOCUMENTS[evidence['doc_id']]
                assert evidence['doc_id'] in selected
                assert ROOT / evidence['file'] == document_path(document)
                text = document_path(document).read_text(encoding='utf-8')
                lines = text.splitlines()
                start, end = evidence['line_start'], evidence['line_end']
                assert 1 <= start <= end <= len(lines)
                assert evidence['quote'] in '\n'.join(lines[start - 1:end])
                assert evidence['quote'] in text
                assert evidence['page'] is None
                assert evidence['text_type'] == document['text_type']
                marker = evidence['source_page_reference']
                if marker:
                    assert marker in '\n'.join(lines[:start])


def test_w2_ingestion_indexing_and_heldout_isolation():
    passages = []
    for document in DOCUMENTS.values():
        path = document_path(document)
        extracted = ingest_document(path, document)
        assert extracted
        assert extracted == ingest_document(path, document)
        for passage in extracted:
            assert passage.doc_id == document['doc_id']
            assert passage.title == document['title']
            assert passage.report_date.isoformat() == document['report_date']
            assert str(passage.source_url) == document['source_url']
            assert passage.page is None
            assert passage.text in path.read_text(encoding='utf-8')
        passages.extend(extracted)
    assert len({p.passage_id for p in passages}) == len(passages)
    initial = [key for key, doc in DOCUMENTS.items() if not doc['heldout']]
    heldout = [key for key, doc in DOCUMENTS.items() if doc['heldout']]
    before = BM25Index(p for p in passages if p.doc_id in initial)
    after = BM25Index(passages)
    query = 'impeachment prosecution Article II unexplained wealth'
    assert not before.retrieve(query, heldout)
    assert before.retrieve(query, initial) == after.retrieve(query, initial)
    assert after.retrieve(query, heldout)
    for doc_id in DOCUMENTS:
        assert after.retrieve('impeachment', [doc_id])


def test_all_documents_upload_through_w2_and_preserve_metadata(tmp_path, monkeypatch):
    from app.main import app
    from app.storage.ingestion import get_ingestor

    monkeypatch.setenv('FOLIO_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FOLIO_DATABASE_PATH', str(tmp_path / 'folio.sqlite3'))
    monkeypatch.delenv('FOLIO_MAX_UPLOAD_BYTES', raising=False)

    def w2_adapter(**kwargs):
        return ingest_document(kwargs['path'], kwargs)

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_ingestor] = lambda: w2_adapter
    try:
        with TestClient(app) as client:
            uploaded = {}
            for document in sorted(DOCUMENTS.values(), key=lambda doc: doc['heldout']):
                path = document_path(document)
                response = client.post('/documents', files={
                    'file': (path.name, path.read_bytes(), document['media_type']),
                }, data={key: document[key] for key in ('title', 'report_date', 'source_url')})
                assert response.status_code == 201, response.text
                saved = response.json()
                assert saved['doc_id'] != document['doc_id']
                uploaded[document['doc_id']] = saved['doc_id']
                assert saved['filename'] == path.name
                expected = ingest_document(path, {**document, 'doc_id': saved['doc_id']})
                assert saved['passage_count'] == len(expected)
                for passage in expected:
                    assert client.get('/passages/' + passage.passage_id).json() == passage.model_dump(mode='json')
            assert len(client.get('/documents').json()['documents']) == 5
            assert len(set(uploaded.values())) == 5
            assert sorted(p.read_bytes() for p in (tmp_path / 'uploads').iterdir()) == sorted(
                document_path(doc).read_bytes() for doc in DOCUMENTS.values())
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
