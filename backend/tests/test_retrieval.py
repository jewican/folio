import pytest

from app.contracts import Passage
from app.retrieval import BM25Index


def passage(id, doc, text):
    return Passage(passage_id=id, doc_id=doc, text=text, title="Report",
                   report_date="2026-10-20", source_url=None, page=None)


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
