"""Evaluator guard tests; no fake backend answers or live evaluation scores."""
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_eval import corpus_bytes, load_inputs, parse_judgment, schedule


def test_phase_schedule_keeps_all_controls_before_heldout():
    suite, documents, _ = load_inputs()
    phases = schedule(suite['questions'])
    assert [stage for stage, _ in phases] == ['before_upload', 'after_upload']
    before, after = phases[0][1], phases[1][1]
    assert len(before) == 9 and len(after) == 3
    assert {key for key, role, _ in before if role == 'control'} == {'FOLIO-09', 'FOLIO-10'}
    assert len({key for _, cases in phases for key, role, _ in cases if role == 'primary'}) == 10
    for _, _, case in before:
        assert case.get('operation', 'ask') == 'ask'
        assert all(not documents[key]['heldout'] for key in case['selected_document_ids'])
    assert [(key, case.get('operation', 'ask')) for key, _, case in after] == [
        ('FOLIO-08', 'ask'), ('FOLIO-09', 'compare'), ('FOLIO-10', 'compare')]


def test_crlf_is_accepted_only_with_exact_gold_hash(tmp_path):
    path = tmp_path / 'source.txt'
    doc = {'doc_id': 'test', 'sha256': sha256(b'One\nTwo\n').hexdigest()}
    path.write_bytes(b'One\r\nTwo\r\n')
    assert corpus_bytes(path, doc) == b'One\nTwo\n'
    assert path.read_bytes() == b'One\r\nTwo\r\n'
    path.write_bytes(b'Changed\r\nTwo\r\n')
    with pytest.raises(ValueError, match='Corpus hash mismatch'):
        corpus_bytes(path, doc)


@pytest.mark.parametrize('criteria,support', [
    ([], []),
    ([{'index': 0, 'passed': True, 'reason': 'ok'}] * 2, []),
    ([{'index': 0, 'passed': 'true', 'reason': 'ok'}], []),
    ([{'index': 0, 'passed': True, 'reason': ' '}], []),
    ([{'index': 0, 'passed': True, 'reason': 'ok'}], []),
])
def test_semantic_verdicts_fail_closed(criteria, support):
    with pytest.raises(ValueError):
        parse_judgment(json.dumps({'criteria': criteria, 'support': support}), 1, 1)


def test_semantic_failure_is_preserved():
    verdict = {'index': 0, 'passed': False, 'reason': 'The quote does not support the asserted amount.'}
    result = parse_judgment(json.dumps({'criteria': [verdict], 'support': [verdict]}), 1, 1)
    assert result['criteria'][0]['passed'] is False
    assert result['support'][0]['passed'] is False
