"""Wire schemas for docs/api-contract.md v1; no feature implementation."""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=128)]
Question = Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Health(Contract):
    status: Literal["ok"] = "ok"


class Document(Contract):
    doc_id: Identifier
    title: str
    filename: str
    media_type: Literal["application/pdf", "text/plain"]
    report_date: date
    source_url: HttpUrl | None
    uploaded_at: datetime
    passage_count: int = Field(ge=1)
    status: Literal["ready"] = "ready"


class DocumentList(Contract):
    documents: list[Document]


class Citation(Contract):
    passage_id: Identifier
    doc_id: Identifier
    title: str
    report_date: date
    source_url: HttpUrl | None
    page: int | None = Field(ge=1)
    quote: str = Field(min_length=1)


class Passage(Contract):
    passage_id: Identifier
    doc_id: Identifier
    title: str
    report_date: date
    source_url: HttpUrl | None
    page: int | None = Field(ge=1)
    text: str = Field(min_length=1)


class ResponseMeta(Contract):
    retrieval_mode: Literal["bm25"] = "bm25"
    elapsed_ms: int = Field(ge=0)
    cached: bool


class AskRequest(Contract):
    question: Question
    doc_ids: list[Identifier] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def distinct_documents(self):
        if len(set(self.doc_ids)) != len(self.doc_ids):
            raise ValueError("doc_ids must be distinct")
        return self


class AnswerClaim(Contract):
    text: str = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)


class AskResponse(Contract):
    question: str
    doc_ids: list[Identifier]
    status: Literal["answered", "insufficient_evidence"]
    answer: str
    claims: list[AnswerClaim]
    meta: ResponseMeta


class CompareRequest(Contract):
    older_doc_id: Identifier
    newer_doc_id: Identifier
    question: Question = "What changed between these reports?"

    @model_validator(mode="after")
    def distinct_versions(self):
        if self.older_doc_id == self.newer_doc_id:
            raise ValueError("Select two distinct documents")
        return self


class ComparisonChange(Contract):
    kind: Literal["updated", "added", "unresolved"]
    summary: str = Field(min_length=1)
    before: str | None
    after: str | None
    older_citations: list[Citation]
    newer_citations: list[Citation]

    @model_validator(mode="after")
    def evidence_on_both_sides(self):
        if self.kind == "added":
            if self.before is not None or self.older_citations or not self.after or not self.newer_citations:
                raise ValueError("Added means newly reported; no earlier claim may be asserted")
        elif not (self.before and self.after and self.older_citations and self.newer_citations):
            raise ValueError("Before/after assertions require passages from both versions")
        return self


class CompareResponse(Contract):
    older_doc_id: Identifier
    newer_doc_id: Identifier
    question: str
    status: Literal["compared", "insufficient_evidence"]
    summary: str
    changes: list[ComparisonChange]
    meta: ResponseMeta
