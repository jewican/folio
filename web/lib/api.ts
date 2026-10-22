// The frontend's only backend adapter. Components call these functions and never
// fetch directly, so integration changes stay in this file.

import {
  answerSampleQuestion,
  compareSampleReports,
  findSamplePassage,
  sampleDocuments,
  sampleQuestions,
} from "@/lib/sample-data";
import type {
  AskRequest,
  AskResponse,
  CompareRequest,
  CompareResponse,
  DocumentList,
  ErrorDetail,
  FolioDocument,
  Passage,
  ValidationIssue,
} from "@/lib/types";
import { MAX_UPLOAD_BYTES, uploadKind } from "@/lib/upload";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// The UI talks to the FastAPI backend by default. Set
// NEXT_PUBLIC_USE_SAMPLE_DATA=true in web/.env.local to develop against
// sample responses without a running backend.
export const USING_SAMPLE_DATA =
  process.env.NEXT_PUBLIC_USE_SAMPLE_DATA === "true";

/** POST /ask accepts 1–5 explicitly selected documents. */
export const MAX_ASK_DOCUMENTS = 5;

/** Questions offered as one-click prompts. */
export const suggestedQuestions: string[] = USING_SAMPLE_DATA
  ? sampleQuestions
  : [];

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Something went wrong.";

export async function listDocuments(): Promise<FolioDocument[]> {
  if (USING_SAMPLE_DATA) {
    await wait(250);
    return sampleDocuments;
  }
  const body = await request<DocumentList>("/documents");
  return body.documents;
}

export async function ask(body: AskRequest): Promise<AskResponse> {
  if (USING_SAMPLE_DATA) {
    const started = performance.now();
    const missing = body.doc_ids.find((id) => !findSampleDocument(id));
    if (missing) {
      throw new ApiError(
        "A selected document was not found.",
        "document_not_found",
        404,
      );
    }
    await wait(1100);
    return {
      ...answerSampleQuestion(body),
      meta: {
        retrieval_mode: "bm25",
        elapsed_ms: Math.round(performance.now() - started),
        cached: false,
      },
    };
  }
  return request<AskResponse>("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function compare(body: CompareRequest): Promise<CompareResponse> {
  if (USING_SAMPLE_DATA) {
    const started = performance.now();
    const older = findSampleDocument(body.older_doc_id);
    const newer = findSampleDocument(body.newer_doc_id);
    if (!older || !newer) {
      throw new ApiError(
        "A selected document was not found.",
        "document_not_found",
        404,
      );
    }
    if (older.report_date >= newer.report_date) {
      throw new ApiError(
        "The older report must have an earlier report date than the newer one.",
        "invalid_selection",
        422,
      );
    }
    await wait(1400);
    return {
      ...compareSampleReports(body),
      meta: {
        retrieval_mode: "bm25",
        elapsed_ms: Math.round(performance.now() - started),
        cached: false,
      },
    };
  }
  return request<CompareResponse>("/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export type UploadRequest = {
  file: File;
  title: string;
  report_date: string;
  source_url: string | null;
};

export async function uploadDocument(input: UploadRequest): Promise<FolioDocument> {
  if (USING_SAMPLE_DATA) return sampleUpload(input);

  const form = new FormData();
  form.append("file", input.file);
  form.append("title", input.title);
  form.append("report_date", input.report_date);
  // The contract asks clients to omit source_url when it is unknown.
  if (input.source_url) form.append("source_url", input.source_url);
  return request<FolioDocument>("/documents", { method: "POST", body: form });
}

// Mirrors the backend's upload checks so the form's error states can be exercised.
// Sample uploads have no extracted passages, so questions about them come back
// as insufficient evidence.
async function sampleUpload(input: UploadRequest): Promise<FolioDocument> {
  await wait(900);
  const { file } = input;
  const kind = uploadKind(file);
  if (!kind) {
    throw new ApiError("Only PDF and TXT files are supported.", "unsupported_file_type", 415);
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new ApiError("The file is larger than 10 MB.", "upload_too_large", 413);
  }

  let passageCount: number;
  if (kind === "pdf") {
    const header = new TextDecoder().decode(await file.slice(0, 5).arrayBuffer());
    if (header !== "%PDF-") {
      throw new ApiError("This file isn't a valid PDF.", "unsupported_file_type", 415);
    }
    passageCount = Math.max(1, Math.round(file.size / 4000));
  } else {
    let text: string;
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
    } catch {
      throw new ApiError("This text file isn't valid UTF-8.", "invalid_document", 422);
    }
    const paragraphs = text.split(/\n\s*\n/).filter((p) => p.trim());
    if (paragraphs.length === 0) {
      throw new ApiError("This file has no readable text.", "invalid_document", 422);
    }
    passageCount = paragraphs.length;
  }

  const doc: FolioDocument = {
    doc_id: `doc_upload_${Date.now().toString(36)}`,
    title: input.title,
    filename: file.name,
    media_type: kind === "pdf" ? "application/pdf" : "text/plain",
    report_date: input.report_date,
    source_url: input.source_url,
    uploaded_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    passage_count: passageCount,
    status: "ready",
  };
  sampleUploads.push(doc);
  return doc;
}

// Reports uploaded in sample mode, so ask and compare can find them this session.
const sampleUploads: FolioDocument[] = [];

const findSampleDocument = (docId: string) =>
  [...sampleDocuments, ...sampleUploads].find((d) => d.doc_id === docId);

export async function getPassage(passageId: string): Promise<Passage> {
  if (USING_SAMPLE_DATA) {
    await wait(200);
    const passage = findSamplePassage(passageId);
    if (!passage) {
      throw new ApiError("That passage was not found.", "passage_not_found", 404);
    }
    return passage;
  }
  return request<Passage>(`/passages/${encodeURIComponent(passageId)}`);
}

const wait = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms));

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(
      `Can't reach the Folio backend at ${API_BASE_URL}. Is it running?`,
      "network_error",
      0,
    );
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

// Backend errors use {detail: {code, message}}; FastAPI request validation
// uses {detail: [{loc, msg, type}]}. The contract asks clients to handle both.
async function toApiError(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => null)) as {
    detail?: ErrorDetail | ValidationIssue[];
  } | null;
  const detail = body?.detail;

  if (Array.isArray(detail)) {
    const message = detail.map((issue) => issue.msg).join("; ");
    return new ApiError(
      message || "The request was not valid.",
      "validation_error",
      response.status,
    );
  }
  // Contract stubs answer 501 until the owning workstream implements them.
  if (detail && !Array.isArray(detail) && detail.code === "not_implemented") {
    return new ApiError(
      "This feature isn't available on the backend yet.",
      detail.code,
      response.status,
    );
  }
  if (detail && typeof detail.message === "string") {
    return new ApiError(detail.message, detail.code, response.status);
  }
  return new ApiError(
    `The backend responded with ${response.status}.`,
    "http_error",
    response.status,
  );
}
