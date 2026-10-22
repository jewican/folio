// The frontend's only backend adapter. Components call these functions and never
// fetch directly, so integration changes stay in this file.

import {
  answerSampleQuestion,
  findSamplePassage,
  sampleDocuments,
  sampleQuestions,
} from "@/lib/sample-data";
import type {
  AskRequest,
  AskResponse,
  DocumentList,
  ErrorDetail,
  FolioDocument,
  Passage,
  ValidationIssue,
} from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// The feature routes return 501 until W1 implements them, so the UI runs on
// sample responses by default. Set NEXT_PUBLIC_USE_SAMPLE_DATA=false in
// web/.env.local to call the backend instead.
export const USING_SAMPLE_DATA =
  process.env.NEXT_PUBLIC_USE_SAMPLE_DATA !== "false";

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
    const missing = body.doc_ids.find(
      (id) => !sampleDocuments.some((d) => d.doc_id === id),
    );
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
  if (detail && typeof detail.message === "string") {
    return new ApiError(detail.message, detail.code, response.status);
  }
  return new ApiError(
    `The backend responded with ${response.status}.`,
    "http_error",
    response.status,
  );
}
