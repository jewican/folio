// Upload rules from docs/api-contract.md (POST /documents). The form checks them
// before sending; the backend remains the authority and re-checks everything.

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MiB
export const MAX_TITLE_LENGTH = 200;
export const ACCEPTED_FILE_TYPES = ".pdf,.txt,application/pdf,text/plain";

export type UploadInput = {
  file: File | null;
  title: string;
  report_date: string;
  source_url: string;
};

export type UploadErrors = Partial<Record<keyof UploadInput, string>>;

export const uploadKind = (file: File): "pdf" | "txt" | null => {
  const name = file.name.toLowerCase();
  if (name.endsWith(".pdf")) return "pdf";
  if (name.endsWith(".txt")) return "txt";
  return null;
};

const isCalendarDate = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
};

const isHttpUrl = (value: string) => {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
};

export function validateUpload(input: UploadInput): UploadErrors {
  const errors: UploadErrors = {};
  const { file } = input;

  if (!file) errors.file = "Choose a PDF or TXT file.";
  else if (!uploadKind(file)) errors.file = "Only .pdf and .txt files are supported.";
  else if (file.size === 0) errors.file = "This file is empty.";
  else if (file.size > MAX_UPLOAD_BYTES) errors.file = "Files can be at most 10 MB.";

  const title = input.title.trim();
  if (!title) errors.title = "Give the report a title.";
  else if (title.length > MAX_TITLE_LENGTH)
    errors.title = `Keep the title under ${MAX_TITLE_LENGTH} characters.`;

  if (!input.report_date) errors.report_date = "Enter the date the report was published.";
  else if (!isCalendarDate(input.report_date)) errors.report_date = "Enter a valid date.";

  const sourceUrl = input.source_url.trim();
  if (sourceUrl && !isHttpUrl(sourceUrl))
    errors.source_url = "Use a full http:// or https:// link, or leave it blank.";

  return errors;
}

/** Suggested title from a filename: "river-2026-10-21.pdf" -> "river 2026 10 21". */
export const titleFromFilename = (name: string) =>
  name.replace(/\.(pdf|txt)$/i, "").replace(/[-_]+/g, " ").trim();
