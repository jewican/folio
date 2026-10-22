// Display helpers for reports, passages and citations.

import type { FolioDocument } from "@/lib/types";

// One colour per report, assigned by position in the date-sorted list, so the
// same report reads the same in the sidebar, citation chips and evidence panel.
const REPORT_TONES = ["#6f9be0", "#d39b4a", "#7fae84", "#b08ad6", "#de7b72"];

export function reportTone(docId: string, documents: FolioDocument[]) {
  const index = Math.max(
    0,
    documents.findIndex((d) => d.doc_id === docId),
  );
  return REPORT_TONES[index % REPORT_TONES.length];
}

/** A small round badge in the report's tone, used as a citation "favicon". */
export function reportBadge(tone: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="8" fill="${tone}"/><path d="M5.5 4.5h3.3l1.7 1.7v5.3h-5z" fill="#fff" fill-opacity=".92"/></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

// report_date is a calendar date, so format it in UTC to keep the day fixed in
// every time zone (and identical between server and client renders).
const toUtcDate = (isoDate: string) => {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
};

const shortDate = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});
const mediumDate = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});
const longDate = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

/** "Oct 20" */
export const formatShortDate = (isoDate: string) =>
  shortDate.format(toUtcDate(isoDate));
/** "Oct 20, 2026" */
export const formatReportDate = (isoDate: string) =>
  mediumDate.format(toUtcDate(isoDate));
/** "Tuesday, October 20, 2026" */
export const formatLongDate = (isoDate: string) =>
  longDate.format(toUtcDate(isoDate));

export const fileKind = (doc: Pick<FolioDocument, "media_type">) =>
  doc.media_type === "application/pdf" ? "PDF" : "TXT";

/** "Oct 20 · p. 2", or just the date for text files, which have no pages. */
export const citationLabel = (c: { report_date: string; page: number | null }) =>
  c.page === null
    ? formatShortDate(c.report_date)
    : `${formatShortDate(c.report_date)} · p. ${c.page}`;
