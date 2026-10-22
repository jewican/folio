from datetime import date

import pytest

from app.contracts import Passage
from app.retrieval import BM25Index, StoredPassageRetriever, rebuild_index, retrieve


def passage(id, doc, text):
    return Passage(passage_id=id, doc_id=doc, text=text, title="Report",
                   report_date="2026-10-20", source_url=None, page=None)


def test_overview_covers_headings_without_altering_ocr_or_leaking_newer_text():
    headings = [passage(f'h{i}', 'old', f'ARTICLE {label}\n\nAllegation number {i}.')
                for i, label in enumerate(['|', 'Il', 'Ill', 'IV'])]
    noise = [passage(f'n{i}', 'old', 'Original articles prosecution pursuing update. ' * 10)
             for i in range(8)]
    newer = passage('heldout', 'new', 'ARTICLE V\n\nLater change.')
    index = BM25Index([*headings, *noise, newer])
    results = index.retrieve('Which articles did the original filing present?', ['old'])
    assert {p.passage_id for p in results[:4]} == {p.passage_id for p in headings}
    assert all(p.doc_id == 'old' for p in results)
    assert next(p for p in results if p.passage_id == 'h1').text == headings[1].text


def test_uploaded_documents_refresh_but_excluded_documents_never_appear(tmp_path):
    stored = [passage("old-1", "old", "Shelters opened today.")]
    search = StoredPassageRetriever(lambda: iter(stored))
    assert search("shelters", doc_ids=["old"]) == stored
    # Simulate W1 committing an upload after the retriever was constructed.
    uploaded = passage("new-1", "new", "Shelters shelters shelters expanded.")
    uploaded.title = "Updated report"
    uploaded.report_date = date(2026, 10, 21)
    uploaded.page = 2
    stored.append(uploaded)
    assert search("shelters", ["new"], top_k=1) == [uploaded]
    snapshot = tmp_path / "bm25.json"
    search.save(snapshot)
    restarted = BM25Index.load(snapshot)
    for index in (search, restarted):
        assert index.retrieve("shelters", ["old"]) == stored[:1]
        assert index.retrieve("expanded", ["old"]) == []
        assert index.retrieve("shelters", ["new"]) == [uploaded]
    assert search("shelters", ["missing"]) == []
    stored.clear()
    assert search("shelters", ["old"]) == []


def test_storage_loading_failure_is_not_hidden():
    def broken_loader():
        raise OSError("Storage unavailable")
    with pytest.raises(OSError, match="Storage unavailable"):
        StoredPassageRetriever(broken_loader)("shelters", ["old"])


def test_failed_refresh_keeps_valid_snapshot():
    stored = [passage("one", "old", "Shelters")]
    search = StoredPassageRetriever(lambda: stored)
    previous = search.rebuild()
    stored.append(passage("one", "new", "Shelters expanded"))
    with pytest.raises(ValueError, match="Duplicate"):
        search.rebuild()
    assert previous.retrieve("shelters", ["old"]) == stored[:1]


def test_ranking_selection_and_rebuild():
    rows = [passage("a", "old", "Confidential funds misuse."),
            passage("b", "old", "Shelters opened today."),
            passage("c", "new", "Confidential funds misuse increased.")]
    index = BM25Index(rows)
    assert index.retrieve("CONFIDENTIAL funds", ["old"], 1) == [rows[0]]
    assert index.retrieve("misuse", ["new"]) == [rows[2]]
    assert index.retrieve("unrelated", ["old"]) == []
    assert index.retrieve("misuse", ["unknown"]) == []
    assert index.retrieve("funds", ["old"]) == BM25Index(rows[:2]).retrieve("funds", ["old"])
    assert index.retrieve("funds", ["old", "new"]) == BM25Index(reversed(rows)).retrieve("funds", ["old", "new"])


def test_index_snapshot_and_return_values_cannot_be_mutated():
    row = passage("a", "old", "Evidence")
    index = BM25Index([row])
    row.text = "Changed"
    result = index.retrieve("Evidence", ["old"])
    result[0].text = "Changed again"
    assert index.retrieve("Evidence", ["old"])[0].text == "Evidence"


@pytest.mark.parametrize("ids,k", [([], 5), (["old", "old"], 5), ("old", 5), (["old"], 0)])
def test_explicit_selection_required(ids, k):
    with pytest.raises(ValueError):
        BM25Index([]).retrieve("evidence", ids, k)


def test_duplicate_passage_ids_rejected():
    with pytest.raises(ValueError):
        BM25Index([passage("a", "old", "One"), passage("a", "new", "Two")])


def test_public_api_defaults_modes_and_rebuild():
    rows = [passage(str(n), "old", "evidence " * (n + 1)) for n in range(8)]
    try:
        rebuild_index(rows)
        assert len(retrieve("evidence", ["old"])) == 6
        assert len(retrieve("evidence", ["old"], k=2)) == 2
        with pytest.raises(ValueError, match="bm25"):
            retrieve("evidence", ["old"], mode="vector")
        rebuild_index([])
        assert retrieve("evidence", ["old"]) == []
    finally:
        rebuild_index([])


def test_ranking_uses_rank_bm25():
    from rank_bm25 import BM25Plus
    rows = [passage("a", "old", "funds funds report"),
            passage("b", "old", "funds report report report report"),
            passage("c", "old", "unrelated")]
    scores = BM25Plus([p.text.split() for p in rows], delta=0).get_scores(["funds"])
    expected = sorted(rows[:2], key=lambda p: -scores[rows.index(p)])
    assert BM25Index(rows).retrieve("funds", ["old"]) == expected
    assert BM25Index([passage("empty", "old", "...")]).retrieve("funds", ["old"]) == []


def test_real_document_retrieval():
    from pathlib import Path
    from app.ingestion import ingest_document

    path = Path(__file__).resolve().parents[2] / ".local/articles-of-impeachment-sara-duterte-2026.txt"
    if not path.exists():
        pytest.skip("Private local sample is not committed")
    rows = ingest_document(path, dict(doc_id="real", title="Articles of impeachment",
                                     report_date="2026-10-20"))
    index = BM25Index(rows + [passage("held-out", "later", "confidential funds liquidation")])
    result = index.retrieve("confidential funds liquidation", ["real"])
    assert len(result) == 6
    assert all(p.doc_id == "real" and p in rows for p in result)
    assert "confidential funds" in result[0].text.lower()
    assert all(p.page is None for p in result)
    assert index.retrieve("confidential funds", ["later"])[0].passage_id == "held-out"


def test_question_scaffolding_does_not_displace_substantive_evidence():
    boilerplate = passage('boilerplate', 'doc', 'According to the supplied document, what did she do? ' * 20)
    evidence = passage('evidence', 'doc', 'The confidential-fund amounts were five million.')
    index = BM25Index([boilerplate, evidence])
    assert index.retrieve('According to the supplied document, what confidential-fund amounts?',
                          ['doc'], k=1) == [evidence]
    assert index.retrieve('what did she do', ['doc']) == []


def test_snapshot_round_trip_preserves_citation_fields(tmp_path):
    row = passage('evidence', 'doc', 'Résumé — ₱500.\nExact quote.')
    from pydantic import HttpUrl
    row.source_url = HttpUrl('https://example.org/source')
    row.page = 7
    index = BM25Index([row])
    path = tmp_path / 'index.json'
    index.save(path)
    assert BM25Index.load(path).retrieve('Exact quote', ['doc']) == [row]


# Hybrid tests use deterministic provider vectors; no external API or keys required.
@pytest.fixture
def embedding_transport(monkeypatch):
    import json
    import httpx
    from app.retrieval import hybrid

    monkeypatch.setattr(hybrid, 'load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setenv('GEMINI_API_KEY', 'test-embedding-key')
    monkeypatch.setenv('FOLIO_RETRIEVAL_MODE', 'hybrid')
    monkeypatch.setenv('GEMINI_EMBEDDING_TIMEOUT_SECONDS', '2')
    calls = []
    state = {'failure': None}
    real_client = httpx.Client

    def respond(request):
        calls.append(request)
        assert str(request.url).endswith('/gemini-embedding-2:batchEmbedContents')
        if state['failure'] == 'timeout':
            raise httpx.ReadTimeout('private provider details', request=request)
        if state['failure'] == 'http':
            return httpx.Response(429, text='private quota details')
        inputs = json.loads(request.content)['requests']
        embeddings = []
        for item in inputs:
            assert item['model'] == 'models/gemini-embedding-2'
            assert item['outputDimensionality'] == 768
            assert 'taskType' not in item
            assert len(item['content']['parts']) == 1
            text = item['content']['parts'][0]['text']
            # Deliberately no lexical overlap: fatalities <-> people killed.
            vector = ([1.0, 0.0] if ('killed' in text or 'fatalities' in text)
                      else [0.0, 1.0]) + [0.0] * 766
            if state['failure'] == 'zero':
                vector = [0.0] * 768
            if state['failure'] == 'dimension':
                vector = [1.0]
            if state['failure'] == 'nan':
                # Return nonfinite JSON as text, since httpx rejects JSON NaN.
                return httpx.Response(200, text='{"embeddings":[{"values":[NaN]}]}')
            embeddings.append({'values': vector})
        if state['failure'] == 'count':
            embeddings = []
        return httpx.Response(200, json={'embeddings': embeddings})

    monkeypatch.setattr(hybrid.httpx, 'Client', lambda **kwargs: real_client(
        transport=httpx.MockTransport(respond), **kwargs))
    return calls, state


def hybrid_storage(tmp_path, rows):
    from datetime import datetime, timezone
    from app.contracts import Document
    from app.storage.database import Storage

    storage = Storage(tmp_path, tmp_path / 'folio.sqlite3')
    for doc_id in sorted({p.doc_id for p in rows}):
        selected = [p for p in rows if p.doc_id == doc_id]
        original = storage.upload_dir / (doc_id + '.txt')
        original.write_text(''.join(p.text for p in selected))
        storage.save(Document(
            doc_id=doc_id, title=selected[0].title, filename=original.name,
            media_type='text/plain', report_date=selected[0].report_date,
            source_url=selected[0].source_url, uploaded_at=datetime.now(timezone.utc),
            passage_count=len(selected), status='ready'), selected, original)
    return storage


def test_hybrid_paraphrase_upload_persistence_and_document_filters(tmp_path, embedding_transport):
    import json
    from app.storage.database import Storage

    calls, _ = embedding_transport
    rows = [passage('a', 'old', 'Three people killed in the incident.'),
            passage('b', 'old', 'Hospitals remained open.'),
            passage('c', 'new', 'Six people killed in the incident.')]
    storage = hybrid_storage(tmp_path, rows)
    assert len(calls) == 2  # Upload embeds each document's chunks separately.
    assert storage.retrieve('fatalities', ['old'], mode='bm25') == []
    assert len(calls) == 2  # BM25 never calls the embedding API.
    result = storage.retrieve('fatalities', ['old'], mode='hybrid')
    assert result[0] == rows[0]
    assert all(p.doc_id == 'old' for p in result)
    assert len(calls) == 3
    assert json.loads(calls[-1].content)['requests'][0]['content']['parts'][0]['text'] == (
        'task: search result | query: fatalities')
    with storage.connect() as db:
        assert db.execute('SELECT count(*) FROM passage_embeddings').fetchone()[0] == 3
    restarted = Storage(tmp_path, tmp_path / 'folio.sqlite3')
    assert restarted.retrieve('fatalities', ['old']) == result
    assert len(calls) == 4  # Restart reuses persisted document vectors; only embeds query.
    assert restarted.get_passage(result[0].passage_id) == rows[0]
    assert restarted.retrieve('fatalities', ['missing']) == []
    assert len(calls) == 4  # No candidates means no query-embedding call.
    assert restarted.retrieve('fatalities', ['old', 'new']) == restarted.retrieve(
        'fatalities', ['new', 'old'])


def test_rrf_combines_rankings_and_deduplicates():
    from app.retrieval.hybrid import rrf
    a, b, c = [passage(pid, 'doc', pid) for pid in 'abc']
    assert rrf([[a, b], [c, b]], 3) == [b, a, c]
    assert rrf([[a, a], [b]], 3) == [a, b]


@pytest.mark.parametrize('failure', ['http', 'timeout', 'dimension', 'zero', 'nan', 'count'])
@pytest.mark.parametrize('phase', ['upload', 'query'])
def test_embedding_failure_preserves_bm25_and_uploads(
        tmp_path, embedding_transport, caplog, failure, phase):
    import logging
    calls, state = embedding_transport
    if phase == 'upload':
        state['failure'] = failure
    rows = [passage('a', 'old', 'Ten shelters opened.')]
    storage = hybrid_storage(tmp_path, rows)
    assert storage.get_passage('a') == rows[0]
    assert storage.list_documents()[0].doc_id == 'old'
    state['failure'] = failure
    with caplog.at_level(logging.INFO):
        assert storage.retrieve('shelters', ['old']) == storage.retrieve(
            'shelters', ['old'], mode='bm25')
    assert calls
    assert 'actual=bm25' in caplog.text
    assert 'private' not in caplog.text
    assert 'test-embedding-key' not in caplog.text


def test_hybrid_backfills_existing_chunks_and_repairs_cache(tmp_path, monkeypatch, embedding_transport):
    calls, _ = embedding_transport
    monkeypatch.setenv('FOLIO_RETRIEVAL_MODE', 'bm25')
    rows = [passage('a', 'old', 'Three people killed.')]
    storage = hybrid_storage(tmp_path, rows)
    assert calls == []
    assert storage.retrieve('fatalities', ['old'], mode='hybrid') == rows
    assert len(calls) == 2  # Document backfill, then query.
    with storage.connect() as db:
        db.execute("UPDATE passage_embeddings SET vector = '[0]'")
        db.commit()
    assert storage.retrieve('fatalities', ['old'], mode='hybrid') == rows
    assert len(calls) == 4
    with storage.connect() as db:
        db.execute("UPDATE passage_embeddings SET content_hash = 'stale'")
        db.commit()
    assert storage.retrieve('fatalities', ['old'], mode='hybrid') == rows
    assert len(calls) == 6


def test_hybrid_keeps_six_passage_balanced_context(tmp_path, embedding_transport):
    rows = [passage(f'{doc}-{i}', doc, 'People killed and shelters opened.')
            for doc in ['old', 'new'] for i in range(8)]
    storage = hybrid_storage(tmp_path, rows)
    result = storage.retrieve('fatalities', ['old', 'new'])
    assert len(result) == len({p.passage_id for p in result}) == 6
    assert [p.doc_id for p in result] == ['new', 'old'] * 3
    assert all(storage.get_passage(p.passage_id) == p for p in result)


def test_embedding_cache_failure_falls_back(tmp_path, embedding_transport, monkeypatch):
    import sqlite3
    storage = hybrid_storage(tmp_path, [passage('a', 'old', 'Shelters opened.')])
    def fail(*args):
        raise sqlite3.OperationalError('private database path')
    monkeypatch.setattr(storage._hybrid.store, 'load', fail)
    assert storage.retrieve('shelters', ['old']) == storage.retrieve('shelters', ['old'], mode='bm25')


def test_unknown_retrieval_mode_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv('FOLIO_RETRIEVAL_MODE', 'bm25')
    storage = hybrid_storage(tmp_path, [])
    with pytest.raises(ValueError, match='bm25 and hybrid'):
        storage.retrieve('shelters', ['old'], mode='unknown')


@pytest.mark.parametrize('configuration', ['missing_key', 'bad_timeout'])
def test_embedding_configuration_failure_is_offline_bm25(
        tmp_path, monkeypatch, embedding_transport, configuration):
    calls, _ = embedding_transport
    if configuration == 'missing_key':
        monkeypatch.setenv('GEMINI_API_KEY', '')
        monkeypatch.setenv('GOOGLE_API_KEY', '')
    else:
        monkeypatch.setenv('GEMINI_EMBEDDING_TIMEOUT_SECONDS', 'nan')
    rows = [passage('a', 'old', 'Ten shelters opened.')]
    storage = hybrid_storage(tmp_path, rows)
    assert storage.retrieve('shelters', ['old']) == rows
    assert calls == []


def test_hybrid_filters_whole_corpus_before_embedding(embedding_transport):
    import json
    from app.retrieval.hybrid import HybridRetriever

    calls, _ = embedding_transport
    old = passage('old', 'z-old', 'Shelters opened.')
    future = passage('future', 'a-new', 'Future-only secret evidence.')
    search = HybridRetriever(None)
    # A whole-corpus caller must neither embed nor rank unselected reports.
    assert search.rank('shelters', [future], BM25Index([future]), ['z-old']) == [[]]
    assert calls == []

    class MemoryVectors:
        def load(self, rows):
            assert rows == [old]
            return {}
        def save(self, rows, vectors):
            assert rows == [old]

    search = HybridRetriever(MemoryVectors())
    assert search.rank('shelters', [old, future], BM25Index([old, future]), ['z-old']) == [[old]]
    inputs = [item['content']['parts'][0]['text'] for call in calls
              for item in json.loads(call.content)['requests']]
    assert not any('Future-only' in text for text in inputs)


@pytest.mark.parametrize('mode', ['bm25', 'hybrid'])
def test_real_report_pair_upload_restart_and_strict_dates(tmp_path, embedding_transport, mode):
    from pathlib import Path
    from app.ingestion import ingest_document
    from app.storage.database import Storage

    examples = Path(__file__).resolve().parents[1] / 'app/retrieval/examples'
    reports = []
    for doc_id, day, number in [('z-older', '2024-10-22', '005'),
                                ('a-newer', '2024-10-27', '024')]:
        reports.append(ingest_document(examples / f'kristy-{day}.txt', {
            'doc_id': doc_id, 'title': f'Kristy advisory {number}', 'report_date': day,
            'source_url': f'https://www.nhc.noaa.gov/archive/2024/ep12/ep122024.public.{number}.shtml',
        }))
    older, newer = reports
    storage = hybrid_storage(tmp_path, older)
    # A second worker has already built its snapshot before the later upload.
    reader = Storage(tmp_path, tmp_path / 'folio.sqlite3')
    question = 'What changed in maximum sustained winds and minimum central pressure?'
    original = reader.retrieve(question, ['z-older'], mode=mode)
    assert original == older
    from datetime import datetime, timezone
    from app.contracts import Document
    source = storage.upload_dir / 'newer.txt'
    source.write_text((examples / 'kristy-2024-10-27.txt').read_text())
    storage.save(Document(doc_id='a-newer', title=newer[0].title, filename=source.name,
                          media_type='text/plain', report_date=newer[0].report_date,
                          source_url=newer[0].source_url, uploaded_at=datetime.now(timezone.utc),
                          passage_count=len(newer), status='ready'), newer, source)
    assert reader.retrieve(question, ['a-newer'], mode=mode) == newer
    assert reader.retrieve(question, ['z-older'], mode=mode) == original
    assert all('45 MPH' not in p.text and '1003 MB' not in p.text for p in original)
    restarted = Storage(tmp_path, tmp_path / 'folio.sqlite3')
    rows = restarted.list_passages()
    index = BM25Index(rows)
    before, after = restarted._hybrid.compare(question, rows, index, 'z-older', 'a-newer', mode=mode)
    assert before == older and after == newer
    assert '75 MPH' in before[0].text and '45 MPH' in after[0].text
    assert all(restarted.get_passage(p.passage_id) == p for p in before + after)
    assert restarted.retrieve(question, ['z-older', 'a-newer'], mode=mode) == after + before
    for old_id, new_id in [('a-newer', 'z-older'), ('z-older', 'z-older'), ('missing', 'a-newer')]:
        with pytest.raises(ValueError):
            restarted._hybrid.compare(question, rows, index, old_id, new_id, mode=mode)
    equal_dates = [p.model_copy(update={'report_date': date(2024, 10, 22)}) for p in rows]
    with pytest.raises(ValueError, match='strictly before'):
        restarted._hybrid.compare(question, equal_dates, BM25Index(equal_dates),
                                  'z-older', 'a-newer', mode=mode)


@pytest.mark.parametrize('ids,k', [([], 3), (['old', 'old'], 3), ('old', 3),
                                  (['old'], 0), (['old'], True)])
def test_hybrid_rejects_invalid_selection_before_provider(embedding_transport, ids, k):
    from app.retrieval.hybrid import HybridRetriever
    calls, _ = embedding_transport
    with pytest.raises(ValueError):
        HybridRetriever(None).rank('evidence', [], BM25Index([]), ids, k)
    assert calls == []
