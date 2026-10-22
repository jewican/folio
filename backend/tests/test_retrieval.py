from datetime import date

import pytest

from app.contracts import Passage
from app.retrieval import BM25Index, StoredPassageRetriever, rebuild_index, retrieve


def passage(id, doc, text):
    return Passage(passage_id=id, doc_id=doc, text=text, title="Report",
                   report_date="2026-10-20", source_url=None, page=None)


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
