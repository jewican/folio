from pathlib import Path

import pytest

from app.ingestion import ExtractionError, extract_passages, extract_text_pages


def test_transcript_preserves_source_pages_and_exact_text(tmp_path):
    text = "Transcript header\r\n---------- SOURCE PDF PAGE 1 / 2 ----------\r\nFirst evidence.\r\n---------- SOURCE PDF PAGE 2 / 2 ----------\r\nSecond evidence."
    path = tmp_path / "report.txt"
    path.write_bytes(text.encode("utf-8"))
    pages = extract_text_pages("doc_1", path)
    assert [p.page for p in pages] == [None, 1, 2]
    assert all(p.doc_id == "doc_1" for p in pages)
    assert "".join(p.text for p in pages) == text
    kwargs = dict(title="Report", report_date="2026-10-20", max_chars=100)
    passages = extract_passages("doc_1", path, **kwargs)
    assert all(p.page is None and p.source_url is None for p in passages)
    assert "".join(p.text for p in passages) == text
    assert passages == extract_passages("doc_1", path, **kwargs)
    assert {p.passage_id for p in passages}.isdisjoint(
        p.passage_id for p in extract_passages("doc_2", path, **kwargs)
    )


def test_chunking_preserves_unicode_and_changes_ids_for_changed_text(tmp_path):
    path = tmp_path / "report.txt"
    text = ("Evidence: café — ₱500.\n\n" * 30) + "x" * 210
    path.write_bytes(text.encode("utf-8"))
    kwargs = dict(title="Report", report_date="2026-10-20", max_chars=100)
    passages = extract_passages("doc", path, **kwargs)
    assert "".join(p.text for p in passages) == text
    assert all(len(p.text) <= 100 for p in passages)
    assert len({p.passage_id for p in passages}) == len(passages)
    path.write_text("Changed evidence.", encoding="utf-8")
    assert extract_passages("doc", path, **kwargs)[0].passage_id not in {p.passage_id for p in passages}


@pytest.mark.parametrize("content,code", [
    (b" \r\n", "invalid_document"), (b"\xff", "invalid_document"),
    (b"%PDF-1.4", "unsupported_file_type"), (b"hello\x00world", "unsupported_file_type"),
    (b"x" * (10_485_760 + 1), "upload_too_large"),
], ids=["blank", "invalid-utf8", "disguised-pdf", "binary", "oversize"])
def test_invalid_content(tmp_path, content, code):
    path = tmp_path / "bad.txt"
    path.write_bytes(content)
    with pytest.raises(ExtractionError) as error:
        extract_text_pages("doc", path)
    assert error.value.code == code


def test_local_sample_when_available():
    path = Path(__file__).resolve().parents[2] / ".local/articles-of-impeachment-sara-duterte-2026.txt"
    if not path.exists():
        pytest.skip("Private local sample is not committed")
    pages = extract_text_pages("sample", path)
    assert [p.page for p in pages if p.page is not None] == list(range(1, 24))
    passages = extract_passages("sample", path, title="Sample", report_date="2026-10-20")
    assert all(p.page is None for p in passages)
    assert "".join(p.text for p in passages) == path.read_bytes().decode("utf-8-sig")
