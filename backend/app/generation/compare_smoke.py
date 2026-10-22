"""Real hybrid/Gemini comparison check using the repository's local corpus.

Run from backend/: ../.venv/bin/python -m app.generation.compare_smoke
Uses isolated temporary storage; writes a local receipt to data/compare-smoke.json.
No provider mocks, dependency overrides, or saved-response fallbacks.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from fastapi.testclient import TestClient

from app.contracts import CompareResponse
from app.generation.api_smoke import require
from app.generation.client import GenerationError, get_model_client
from app.generation.compare import verify_comparison
from app.main import app
from app.storage.database import _storage, get_storage

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
RECORD_PATH = BACKEND / 'data' / 'compare-smoke.json'


def check_comparisons(client, report):
    manifest = json.loads((ROOT / 'corpus/manifest.json').read_text(encoding='utf-8'))
    evaluation = json.loads((ROOT / 'eval/questions.json').read_text(encoding='utf-8'))
    uploaded = {}
    # Include a third document to check selection isolation without modifying W4 inputs.
    selected = {'articles-2026', 'house-press-10322-2026-10-13', 'sc-press-briefer-2026-08-05'}
    for document in manifest['documents']:
        if document['doc_id'] not in selected:
            continue
        path = ROOT / 'corpus' / document['file']
        response = client.post('/documents', files={
            'file': (path.name, path.read_bytes(), document['media_type']),
        }, data={key: document[key] for key in ('title', 'report_date', 'source_url')})
        require(response.status_code == 201, 'Real corpus upload failed.')
        uploaded[document['doc_id']] = response.json()['doc_id']
        report['uploads'].append({'manifest_id': document['doc_id'], **response.json()})
    _storage.cache_clear()  # Verify restart/rebuild and persisted embeddings too.
    for case in evaluation['questions'][8:]:
        selection = {key: uploaded[value] for key, value in case['comparison_selection'].items()}
        response = client.post('/compare', json={**selection, 'question': case['question']})
        result = {'case_id': case['id'], 'http_status': response.status_code}
        report['comparisons'].append(result)
        if response.status_code != 200:
            result['error'] = response.json()['detail']
            raise ValueError('Live comparison failed.')
        comparison = CompareResponse.model_validate(response.json())
        result['response'] = comparison.model_dump(mode='json')
        require(comparison.status == 'compared' and bool(comparison.changes),
                'Expected supported changes were not returned.')
        require(comparison.meta.cached is False, 'Comparison must be uncached.')
        require(comparison.summary == ' '.join(c.summary for c in comparison.changes),
                'Summary added uncited assertions.')
        validated = 0
        for change in comparison.changes:
            for citations, expected in ((change.older_citations, comparison.older_doc_id),
                                        (change.newer_citations, comparison.newer_doc_id)):
                for citation in citations:
                    stored = client.get('/passages/' + citation.passage_id)
                    require(stored.status_code == 200, 'Citation does not resolve.')
                    evidence = stored.json()
                    require(citation.doc_id == expected and citation.quote in evidence['text'],
                            'Citation side or exact quote is invalid.')
                    require(all(evidence[key] == value for key, value in
                                citation.model_dump(mode='json', exclude={'quote'}).items()),
                            'Citation metadata differs from canonical storage.')
                    validated += 1
        result['validated_citations'] = validated

    # Real semantic review must reject false claims even with valid canonical citations.
    base = comparison.changes[0]
    passages = get_storage().retrieve(case['question'], list(selection.values()))
    context = [p.model_dump(mode='json') for p in passages]
    attacks = {
        'invented_fact': 'The Senate convicted the Vice President and removed her from office.',
        'invented_delta': 'The number of impeachment articles increased by 900.',
        'unsupported_prior_state': 'There were zero allegations in the earlier report; this is the first allegation.',
        'insufficient_quoted_support': base.summary,
    }
    for name, unsupported in attacks.items():
        change = deepcopy(base)
        change.summary = unsupported
        if name == 'unsupported_prior_state':
            change.kind, change.before, change.older_citations = 'added', None, []
        if name == 'insufficient_quoted_support':
            for citation in change.older_citations + change.newer_citations:
                citation.quote = citation.quote.split()[0]
        try:
            verify_comparison(('compared', unsupported, [change]), get_model_client(), context)
        except ValueError:
            report['support_rejections'].append(name)
        else:
            raise ValueError('Support review accepted an unsupported claim.')


def run():
    started = perf_counter()
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'mocked': False,
              'success': False, 'retrieval_mode': 'hybrid', 'uploads': [],
              'comparisons': [], 'support_rejections': []}
    names = ('FOLIO_DATA_DIR', 'FOLIO_DATABASE_PATH', 'FOLIO_RETRIEVAL_MODE', 'FOLIO_MAX_UPLOAD_BYTES')
    previous = {name: os.environ.get(name) for name in names}
    try:
        require(not app.dependency_overrides, 'Live check refuses dependency overrides.')
        report['model_id'] = get_model_client().model_id
        with TemporaryDirectory(prefix='folio-real-compare-') as directory:
            os.environ.update(FOLIO_DATA_DIR=directory,
                              FOLIO_DATABASE_PATH=str(Path(directory) / 'folio.sqlite3'),
                              FOLIO_RETRIEVAL_MODE='hybrid')
            os.environ.pop('FOLIO_MAX_UPLOAD_BYTES', None)
            with TestClient(app) as client:
                check_comparisons(client, report)
        report['success'] = True
    except GenerationError as exc:
        report['error'] = {'code': exc.code, 'message': str(exc), **exc.diagnostics}
    except (ValueError, OSError) as exc:
        report['error'] = {'code': 'live_check_failed', 'message': str(exc)}
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
    print(json.dumps({key: report[key] for key in
                      ('success', 'mocked', 'elapsed_ms', 'support_rejections')}))
    if 'error' in report:
        print(json.dumps(report['error']))
    print('Receipt: backend/data/compare-smoke.json')
    return 0 if report['success'] else 1


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    raise SystemExit(run())
