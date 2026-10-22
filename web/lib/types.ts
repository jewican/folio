// TypeScript mirror of docs/api-contract.md (v1). W1 owns the contract;
// change it there first, then update these shapes to match.

/** Contract `Document`: one uploaded report version. */
export type FolioDocument = {
  doc_id: string;
  title: string;
  filename: string;
  media_type: "application/pdf" | "text/plain";
  /** Publication date (YYYY-MM-DD) supplied on upload, never the upload time. */
  report_date: string;
  source_url: string | null;
  /** RFC 3339 UTC upload completion time. */
  uploaded_at: string;
  passage_count: number;
  status: "ready";
};

export type DocumentList = {
  documents: FolioDocument[];
};

export type Passage = {
  passage_id: string;
  doc_id: string;
  title: string;
  report_date: string;
  source_url: string | null;
  /** 1-based physical PDF page; null for TXT. */
  page: number | null;
  text: string;
};

export type Citation = {
  passage_id: string;
  doc_id: string;
  title: string;
  report_date: string;
  source_url: string | null;
  page: number | null;
  /** Exact contiguous substring of the passage's stored text. */
  quote: string;
};

export type ResponseMeta = {
  retrieval_mode: "bm25";
  elapsed_ms: number;
  cached: boolean;
};

export type AskRequest = {
  question: string;
  /** 1–5 explicitly selected ready documents; there is no implicit "all". */
  doc_ids: string[];
};

export type Claim = {
  text: string;
  citations: Citation[];
};

export type AskResponse = {
  question: string;
  doc_ids: string[];
  status: "answered" | "insufficient_evidence";
  answer: string;
  claims: Claim[];
  meta: ResponseMeta;
};

export type CompareRequest = {
  older_doc_id: string;
  newer_doc_id: string;
  question?: string;
};

export type Change = {
  kind: "updated" | "unresolved" | "added";
  summary: string;
  /** Null only for `added`. */
  before: string | null;
  after: string;
  older_citations: Citation[];
  newer_citations: Citation[];
};

export type CompareResponse = {
  older_doc_id: string;
  newer_doc_id: string;
  question: string;
  status: "compared" | "insufficient_evidence";
  summary: string;
  changes: Change[];
  meta: ResponseMeta;
};

/** Backend error envelope: `{"detail": {"code": ..., "message": ...}}`. */
export type ErrorDetail = {
  code: string;
  message: string;
};

/** One entry of FastAPI's 422 validation `detail` array. */
export type ValidationIssue = {
  loc: (string | number)[];
  msg: string;
  type: string;
};
