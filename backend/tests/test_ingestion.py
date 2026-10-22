from pathlib import Path

import pytest

from app.ingestion import ExtractionError, extract_passages, extract_text_pages, ingest_document


def test_transcript_preserves_source_pages_and_exact_text(tmp_path):
    text = "Transcript header\r\n---------- SOURCE PDF PAGE 1 / 2 ----------\r\nFirst evidence.\r\n---------- SOURCE PDF PAGE 2 / 2 ----------\r\nSecond evidence."
    path = tmp_path / "report.txt"
    path.write_bytes(text.encode("utf-8"))
    pages = extract_text_pages("doc_1", path)
    assert [p.page for p in pages] == [None, 1, 2]
    assert all(p.doc_id == "doc_1" for p in pages)
    assert "".join(p.text for p in pages) == text
    kwargs = dict(title="Report", report_date="2026-10-20")
    passages = extract_passages("doc_1", path, **kwargs)
    assert all(p.page is None and p.source_url is None for p in passages)
    assert "".join(p.text for p in passages) == text
    assert passages == extract_passages("doc_1", path, **kwargs)
    assert {p.passage_id for p in passages}.isdisjoint(
        p.passage_id for p in extract_passages("doc_2", path, **kwargs)
    )


def test_chunking_preserves_unicode_and_changes_ids_for_changed_text(tmp_path):
    path = tmp_path / "report.txt"
    text = ("Evidence: café — ₱500.\n\n" * 300) + "x" * 210
    path.write_bytes(text.encode("utf-8"))
    kwargs = dict(title="Report", report_date="2026-10-20")
    passages = extract_passages("doc", path, **kwargs)
    assert "".join(p.text for p in passages) == text
    assert all(300 <= len(p.text.split()) <= 500 for p in passages)
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


def test_paragraph_boundaries_and_long_paragraph(tmp_path):
    paragraphs = [("paragraph%d " % n) * 100 + "\r\n\r\n" for n in range(12)]
    path = tmp_path / "paragraphs.txt"
    path.write_bytes("".join(paragraphs).encode())
    metadata = dict(doc_id="doc", title="Report", report_date="2026-10-20",
                    source_url="https://example.org/report")
    passages = ingest_document(path, metadata)
    assert [len(p.text.split()) for p in passages] == [400, 400, 400]
    assert all(p.text.endswith("\r\n\r\n") for p in passages)
    assert "".join(p.text for p in passages) == "".join(paragraphs)
    assert all(str(p.source_url) == metadata["source_url"] for p in passages)
    path.write_text("word " * 1100, encoding="utf-8")
    passages = ingest_document(path, metadata)
    assert all(300 <= len(p.text.split()) <= 500 for p in passages)
    assert "".join(p.text for p in passages) == "word " * 1100


def make_pdf(path, page_texts, encrypted=False):
    """Small real PDF byte fixture, exercising the parser without mocks."""
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                     NameObject("/Subtype"): NameObject("/Type1"),
                                     NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
            stream = DecodedStreamObject()
            stream.set_data(("BT /F1 12 Tf 50 700 Td (" + text + ") Tj ET").encode("ascii"))
            page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("secret")
    writer.write(path)


def test_pdf_physical_pages_and_stable_ids(tmp_path):
    path = tmp_path / "report.pdf"
    make_pdf(path, [None, "Confidential funds " * 550, "Second page evidence"])
    meta = dict(doc_id="pdf", title="Report", report_date="2026-10-20")
    passages = ingest_document(path, meta)
    assert {p.page for p in passages} == {2, 3}
    assert all(len(p.text.split()) <= 500 for p in passages)
    assert sum(len(p.text.split()) for p in passages if p.page == 2) == 1100
    assert passages == ingest_document(path, meta)
    assert passages[-1].text == "Second page evidence"


@pytest.mark.parametrize("kind", ["encrypted", "textless", "broken", "fake"])
def test_invalid_pdf(tmp_path, kind):
    path = tmp_path / "bad.pdf"
    if kind == "broken":
        path.write_bytes(b"%PDF-1.7\nnot a PDF")
    elif kind == "fake":
        path.write_text("plain text", encoding="utf-8")
    else:
        make_pdf(path, [None] if kind == "textless" else ["Secret"], kind == "encrypted")
    with pytest.raises(ExtractionError) as error:
        ingest_document(path, dict(doc_id="doc", title="Report", report_date="2026-10-20"))
    assert error.value.code == ("unsupported_file_type" if kind == "fake" else "invalid_document")
