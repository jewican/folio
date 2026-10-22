"""Real W4 upload/retrieval/Gemini/citation check; never mocks the model.

Run from backend/: python -m app.generation.api_smoke
Uses temporary local storage and writes a receipt to data/api-smoke.json.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from fastapi.testclient import TestClient

from app.contracts import AskResponse
from app.generation.client import GenerationError, get_model_client
from app.main import app
from app.storage.database import _storage, get_storage

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
RECORD_PATH = BACKEND / 'data' / 'api-smoke.json'


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def check_api(client: TestClient, report: dict):
    manifest = json.loads((ROOT / 'corpus/manifest.json').read_text(encoding='utf-8'))
    evaluation = json.loads((ROOT / 'eval/questions.json').read_text(encoding='utf-8'))
    uploaded = {}
    for document in sorted(manifest['documents'], key=lambda row: row['heldout']):
        path = ROOT / 'corpus' / document['file']
        response = client.post('/documents', files={
            'file': (path.name, path.read_bytes(), document['media_type']),
        }, data={key: document[key] for key in ('title', 'report_date', 'source_url')})
        require(response.status_code == 201, 'W4 upload failed.')
        saved = response.json()
        require(all(saved[field] == document[field]
                    for field in ('title', 'report_date', 'source_url')), 'Upload metadata mismatch.')
        uploaded[document['doc_id']] = saved['doc_id']
        report['uploads'].append({
            'manifest_id': document['doc_id'], 'doc_id': saved['doc_id'],
            'passage_count': saved['passage_count'], 'heldout': document['heldout'],
        })
    require(len(client.get('/documents').json()['documents']) == 5, 'Document listing mismatch.')
    selection = [uploaded['articles-2026']]
    checks = {
        'unknown_document': client.post('/ask', json={'question': 'shelters', 'doc_ids': ['missing']}),
        'blank_question': client.post('/ask', json={'question': ' ', 'doc_ids': selection}),
        'unknown_passage': client.get('/passages/missing'),
        'unsupported_upload': client.post('/documents', files={
            'file': ('invalid.exe', b'Unsupported upload.', 'application/octet-stream'),
        }, data={'title': 'Invalid', 'report_date': '2026-10-22'}),
    }
    expected_codes = {'unknown_document': 404, 'blank_question': 422,
                      'unknown_passage': 404, 'unsupported_upload': 415}
    for name, response in checks.items():
        report['error_checks'][name] = response.status_code
        require(response.status_code == expected_codes[name], 'API error mapping failed.')
    empty = client.post('/ask', json={
        'question': 'FolioUnmatchedLexicalProbe926713', 'doc_ids': selection,
    })
    require(empty.status_code == 200 and empty.json()['status'] == 'insufficient_evidence'
            and empty.json()['claims'] == [], 'Empty retrieval must return insufficient evidence.')
    report['empty_retrieval_checked'] = True

    # Lose the process index: answers below must use the passages saved by uploads.
    _storage.cache_clear()
    for number in (6, 0, 7):  # SC summary, financial allegations, then insufficient evidence.
        case = evaluation['questions'][number]
        selected = [uploaded[key] for key in case['selected_document_ids']]
        passages = get_storage().retrieve(case['question'], selected)
        require(bool(passages), 'Expected evidence was not retrieved.')
        require(all(p.doc_id in selected for p in passages), 'Retrieval leaked an unselected document.')
        result = {'case_id': case['id'], 'question': case['question'],
                  'expected_status': case['expected_status'], 'selected_doc_ids': selected,
                  'retrieved_passage_ids': [p.passage_id for p in passages]}
        report['answers'].append(result)
        # This invokes the normal production route and the real configured provider.
        response = client.post('/ask', json={'question': case['question'], 'doc_ids': selected})
        result['http_status'] = response.status_code
        if response.status_code != 200:
            result['error'] = response.json()['detail']
            report['error'] = result['error']
            return  # Stop at a provider failure; no retries or saved-answer fallback.
        answer = AskResponse.model_validate(response.json())
        require(answer.status == case['expected_status'], 'Unexpected answer/evidence status.')
        require(answer.meta.cached is False, 'Live response must be uncached.')
        require(answer.doc_ids == selected and answer.question == case['question'], 'Request echo mismatch.')
        supplied = {p.passage_id: p for p in passages}
        validated = 0
        for claim in answer.claims:
            for citation in claim.citations:
                require(citation.passage_id in supplied, 'Citation was not retrieved.')
                evidence = client.get('/passages/' + citation.passage_id)
                require(evidence.status_code == 200, 'Citation did not resolve.')
                stored = evidence.json()
                require(citation.quote in stored['text'], 'Quote differs from stored text.')
                require(citation.doc_id in selected, 'Citation is outside the selection.')
                fields = citation.model_dump(mode='json', exclude={'quote'})
                require(all(value == stored[key] for key, value in fields.items()),
                        'Citation metadata differs from storage.')
                validated += 1
        if answer.status == 'answered':
            require(validated > 0 and answer.claims, 'Answered without citations.')
        else:
            require(not answer.claims, 'Insufficient evidence must not assert claims.')
        result['response'] = answer.model_dump(mode='json')
        result['validated_citations'] = validated
    report['success'] = True


def run() -> int:
    started = perf_counter()
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'provider': 'gemini',
              'success': False, 'mocked': False, 'uploads': [], 'answers': [], 'error_checks': {}}
    names = ('FOLIO_DATA_DIR', 'FOLIO_DATABASE_PATH', 'FOLIO_MAX_UPLOAD_BYTES')
    previous = {name: os.environ.get(name) for name in names}
    try:
        require(not app.dependency_overrides, 'Live check refuses dependency overrides.')
        report['model_id'] = get_model_client().model_id
        with TemporaryDirectory(prefix='folio-live-api-') as directory:
            os.environ['FOLIO_DATA_DIR'] = directory
            os.environ['FOLIO_DATABASE_PATH'] = str(Path(directory) / 'folio.sqlite3')
            os.environ.pop('FOLIO_MAX_UPLOAD_BYTES', None)
            with TestClient(app) as client:
                check_api(client, report)
    except GenerationError as exc:
        report['error'] = {'code': exc.code, 'message': str(exc), **exc.diagnostics}
    except (ValueError, OSError):
        report['error'] = {'code': 'live_check_failed',
                           'message': 'Live API validation failed. Review the recorded completed checks.'}
    finally:
        _storage.cache_clear()
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    report['elapsed_ms'] = round((perf_counter() - started) * 1000)
    RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECORD_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Concise terminal status; full real responses and citations stay in the local receipt.
    print(json.dumps({key: report[key] for key in ('tested_at', 'success', 'mocked', 'elapsed_ms')}))
    print(f"Uploaded documents: {len(report['uploads'])}; real answers validated: "
          f"{sum('response' in answer for answer in report['answers'])}")
    if 'error' in report:
        print(json.dumps(report['error']))
    print('Receipt: backend/data/api-smoke.json')
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(run())
