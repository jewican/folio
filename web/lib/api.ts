// The frontend's only backend adapter. Every operation uses the real FastAPI API.
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

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://localhost:8000"
).replace(/\/+$/, "");

/** POST /ask accepts 1–5 explicitly selected documents. */
export const MAX_ASK_DOCUMENTS = 5;

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
  const body = await request<DocumentList>("/documents");
  return body.documents;
}

export async function ask(body: AskRequest): Promise<AskResponse> {
  return request<AskResponse>("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function compare(body: CompareRequest): Promise<CompareResponse> {
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
  const form = new FormData();
  form.append("file", input.file);
  form.append("title", input.title);
  form.append("report_date", input.report_date);
  if (input.source_url) form.append("source_url", input.source_url);
  return request<FolioDocument>("/documents", { method: "POST", body: form });
}

export async function getPassage(passageId: string): Promise<Passage> {
  return request<Passage>(`/passages/${encodeURIComponent(passageId)}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  // Leave time for the backend's configurable provider timeout (up to 120 s).
  const timeout = setTimeout(() => controller.abort(), 135_000);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) throw await toApiError(response);
    try {
      return (await response.json()) as T;
    } catch {
      throw new ApiError("The backend returned an unreadable response. Try again.", "invalid_response", 502);
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      throw new ApiError("The request timed out. Try again.", "request_timeout", 504);
    }
    throw new ApiError(
      `Can't reach the Folio backend at ${API_BASE_URL}. Is it running?`,
      "network_error",
      0,
    );
  } finally {
    clearTimeout(timeout);
  }
}

// Both FastAPI error envelopes from docs/api-contract.md are supported.
async function toApiError(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => null)) as {
    detail?: ErrorDetail | ValidationIssue[];
  } | null;
  const detail = body?.detail;
  if (Array.isArray(detail)) {
    return new ApiError(
      detail.map((issue) => issue.msg).join("; ") || "The request was not valid.",
      "validation_error",
      response.status,
    );
  }
  if (detail?.code === "not_implemented") {
    return new ApiError("This feature isn't available on the backend yet.", detail.code, response.status);
  }
  if (detail && typeof detail.message === "string") {
    return new ApiError(detail.message, detail.code, response.status);
  }
  return new ApiError(`The backend responded with ${response.status}.`, "http_error", response.status);
}
