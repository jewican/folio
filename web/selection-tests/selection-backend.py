"""Real storage/retrieval/validation; deterministic model responses for UI regression tests."""
import json
import os
from dataclasses import dataclass
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.generation import answer  # noqa: E402
from app.generation.client import ModelResult  # noqa: E402


@dataclass(frozen=True)
class SelectionTestModel:
    timeout_seconds: float = 10

    def generate(self, prompt, **kwargs):
        context = json.loads(prompt.split('INPUT_JSON:\n', 1)[1])
        passages = context['passages']

        def evidence(passage):
            return {'passage_id': passage['passage_id'], 'quote': passage['text']}

        if 'older_doc_id' in context:
            older = next(p for p in passages if p['doc_id'] == context['older_doc_id'])
            newer = next(p for p in passages if p['doc_id'] == context['newer_doc_id'])
            result = {'status': 'compared', 'changes': [{
                'kind': 'updated', 'summary': older['text'] + ' ' + newer['text'],
                'before': older['text'], 'after': newer['text'],
                'older_citations': [evidence(older)], 'newer_citations': [evidence(newer)],
            }]}
        else:
            result = {'status': 'answered', 'claims': [
                {'text': p['text'], 'citations': [evidence(p)]} for p in passages
            ]}
        return ModelResult(json.dumps(result), 'selection-test', '1', 0)


if __name__ == '__main__':
    # Replace only the external model boundary. Production prompt construction,
    # citation validation, BM25 filtering and passage lookup remain in use.
    answer.get_model_client = lambda: SelectionTestModel()
    with TemporaryDirectory(prefix='folio-selection-') as directory:
        os.environ['FOLIO_DATA_DIR'] = directory
        os.environ['FOLIO_DATABASE_PATH'] = str(Path(directory) / 'folio.sqlite3')
        os.environ['FOLIO_CORS_ORIGINS'] = 'http://localhost:3100'
        uvicorn.run('app.main:app', host='127.0.0.1', port=8011, log_level='warning')
