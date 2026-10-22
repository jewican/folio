"use client";

import { ArrowUpRight, Check, RotateCcw, Upload, X } from "lucide-react";
import { HookSidebar } from "@/components/ui/hook-sidebar";
import { API_BASE_URL, MAX_ASK_DOCUMENTS } from "@/lib/api";
import {
  fileKind,
  formatReportDate,
  formatShortDate,
  reportTone,
} from "@/lib/reports";
import type { FolioDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

export const VIEWS = [
  { id: "ask", label: "Ask the reports" },
  { id: "compare", label: "Compare versions" },
] as const;

export type View = (typeof VIEWS)[number]["id"];

type DocumentSidebarProps = {
  documents: FolioDocument[] | null;
  documentsError: string | null;
  onRetryDocuments: () => void;
  selectedIds: string[];
  onToggleDocument: (docId: string) => void;
  view: View;
  onViewChange: (view: View) => void;
  /** Drawer state below the md breakpoint; the sidebar is always shown above it. */
  open: boolean;
  onClose: () => void;
  onUploadClick: () => void;
  /** Reports uploaded during this visit, marked so the newest evidence stands out. */
  newIds: string[];
};

export function DocumentSidebar({
  documents,
  documentsError,
  onRetryDocuments,
  selectedIds,
  onToggleDocument,
  view,
  onViewChange,
  open,
  onClose,
  onUploadClick,
  newIds,
}: DocumentSidebarProps) {
  const atLimit = selectedIds.length >= MAX_ASK_DOCUMENTS;

  return (
    <aside
      id="document-sidebar"
      aria-label="Reports"
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex w-[272px] flex-col border-r border-[#303238] bg-[#1c1f23] text-[#dce0e6] [--foreground:#e5e8ed] duration-300 ease-out md:static md:z-auto md:w-[248px] md:translate-x-0 lg:w-[272px]",
        open
          ? "visible translate-x-0 transition-[translate]"
          : "transition-[translate,visibility] max-md:invisible max-md:-translate-x-full",
      )}
    >
      <div className="flex items-center justify-between px-5 pt-6">
        <span className="flex items-center gap-2.5 text-[28px] font-[530] tracking-[-0.06em] text-[#f0f1f3]">
          <BrandMark />
          <span>
            folio<span className="text-[#9bbbf0]">.</span>
          </span>
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close reports"
          className="grid size-8 place-items-center rounded-md text-[#939ba7] hover:bg-white/5 hover:text-[#e0eafa] md:hidden"
        >
          <X size={18} />
        </button>
      </div>

      <StoryCard documents={documents} />

      <SectionLabel className="mb-2">Workspace</SectionLabel>
      <HookSidebar
        aria-label="Workspace"
        className="folio-nav mx-3 mb-7"
        color="#98bfff"
        dashed={false}
        items={VIEWS.map((v) => v.label)}
        value={VIEWS.findIndex((v) => v.id === view)}
        onChange={(index) => onViewChange(VIEWS[index].id)}
      />

      <div className="mb-2 flex items-baseline justify-between pr-5">
        <SectionLabel>Reports</SectionLabel>
        {documents && documents.length > 0 && (
          <span className="text-[10.5px] tabular-nums text-[#7d8693]">
            {selectedIds.length} of {documents.length} selected
          </span>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3">
        {documents === null ? (
          documentsError ? (
            <div className="rounded-lg border border-[#5a3a36] bg-[#2a2120] p-3 text-[12px] leading-relaxed text-[#e3b8b0]">
              <p>{documentsError}</p>
              <button
                type="button"
                onClick={onRetryDocuments}
                className="mt-2 inline-flex items-center gap-1.5 font-medium text-[#f1d2cc] hover:text-white"
              >
                <RotateCcw size={12} /> Try again
              </button>
            </div>
          ) : (
            <ul aria-label="Loading reports" className="flex flex-col gap-1">
              {[0, 1, 2].map((i) => (
                <li key={i} className="flex gap-3 px-2.5 py-3">
                  <span className="size-4 animate-pulse rounded-[5px] bg-white/[0.07]" />
                  <span className="flex flex-1 flex-col gap-2">
                    <span className="h-2.5 w-4/5 animate-pulse rounded-full bg-white/[0.07]" />
                    <span className="h-2 w-1/2 animate-pulse rounded-full bg-white/[0.05]" />
                  </span>
                </li>
              ))}
            </ul>
          )
        ) : documents.length === 0 ? (
          <p className="px-2.5 py-3 text-[12px] leading-relaxed text-[#8c949f]">
            No reports yet. Upload a dated report to start asking questions.
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {documents.map((doc) => {
              const checked = selectedIds.includes(doc.doc_id);
              return (
                <ReportItem
                  key={doc.doc_id}
                  doc={doc}
                  tone={reportTone(doc.doc_id, documents)}
                  checked={checked}
                  isNew={newIds.includes(doc.doc_id)}
                  disabled={!checked && atLimit}
                  onToggle={() => onToggleDocument(doc.doc_id)}
                />
              );
            })}
          </ul>
        )}
      </div>

      <div className="px-3 pt-3">
        <button
          type="button"
          onClick={onUploadClick}
          disabled={documents === null}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-[#3d434b] px-3 py-2.5 text-[12px] font-medium text-[#a9b1bc] transition-colors hover:enabled:border-[#5b6573] hover:enabled:bg-white/[0.04] hover:enabled:text-[#e8ecf1] disabled:opacity-60"
        >
          <Upload size={14} /> Upload report
        </button>
      </div>

      <div className="mt-4 border-t border-white/[0.07] px-5 pb-4 pt-3.5 text-[11px]">
        <p className="flex items-center gap-2 text-[#8b959f]">
          <span
            className={cn(
              "size-1.5 shrink-0 rounded-full",
              documentsError ? "bg-[#d3a75c]" : documents === null ? "bg-[#a9b1bc]" : "bg-[#87a68b]",
            )}
          />
          <span title={API_BASE_URL}>
            {documentsError ? "Backend unavailable" : documents === null ? "Connecting to backend…" : "Connected to backend"}
          </span>
        </p>
        <a
          href="https://rareui.com"
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-[10px] text-[#85909d] hover:text-[#c9d9ed]"
        >
          Interface components by Rare UI <ArrowUpRight size={10} />
        </a>
      </div>
    </aside>
  );
}

function ReportItem({
  doc,
  tone,
  checked,
  isNew,
  disabled,
  onToggle,
}: {
  doc: FolioDocument;
  tone: string;
  checked: boolean;
  isNew: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <li>
      <label
        title={
          disabled
            ? `Ask uses at most ${MAX_ASK_DOCUMENTS} reports at a time`
            : undefined
        }
        className={cn(
          "flex items-start gap-3 rounded-lg px-2.5 py-2.5 transition-colors",
          disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:bg-white/[0.04]",
          checked && "bg-white/[0.06] hover:bg-white/[0.08]",
        )}
      >
        <input
          type="checkbox"
          className="peer sr-only"
          checked={checked}
          disabled={disabled}
          onChange={onToggle}
        />
        <span
          aria-hidden
          className={cn(
            "mt-0.5 grid size-4 shrink-0 place-items-center rounded-[5px] border transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[#5599ee]",
            checked
              ? "border-[#98bfff] bg-[#98bfff] text-[#1c1f23]"
              : "border-[#4a515b]",
          )}
        >
          {checked && <Check size={11} strokeWidth={3} />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span
              aria-hidden
              className="size-2 shrink-0 rounded-full"
              style={{ background: tone }}
            />
            <span className="truncate text-[12.5px] font-medium text-[#e8ecf1]">
              {doc.title}
            </span>
            {isNew && (
              <span className="shrink-0 rounded-full bg-[#98bfff]/15 px-1.5 py-px text-[9.5px] font-semibold uppercase tracking-[0.08em] text-[#a9c9ff]">
                New
              </span>
            )}
          </span>
          <span className="mt-1 block text-[11px] text-[#8c949f]">
            <time dateTime={doc.report_date}>
              {formatReportDate(doc.report_date)}
            </time>
            {" · "}
            {fileKind(doc)} · {doc.passage_count}{" "}
            {doc.passage_count === 1 ? "passage" : "passages"}
          </span>
        </span>
      </label>
    </li>
  );
}

function StoryCard({ documents }: { documents: FolioDocument[] | null }) {
  let summary = "Loading reports…";
  if (documents) {
    const first = documents[0]?.report_date;
    const last = documents.at(-1)?.report_date;
    const range =
      first && last && first !== last
        ? `${formatShortDate(first)} – ${formatReportDate(last)}`
        : first
          ? formatReportDate(first)
          : "no reports yet";
    summary = `${documents.length} ${documents.length === 1 ? "report" : "reports"} · ${range}`;
  }

  return (
    <div className="mx-4 my-7 flex items-center gap-2.5 rounded-[9px] border border-[#33383e] bg-[#25292e] p-2.5 shadow-[inset_0_1px_0_#ffffff06]">
      <span
        aria-hidden
        className="grid size-[30px] shrink-0 place-items-center rounded-[7px] border border-[#718ba344] bg-linear-to-br from-[#597b9c] to-[#324355] font-serif text-[17px] text-[#e6edf4]"
      >
        F
      </span>
      <span className="min-w-0 text-[12px] font-medium leading-tight">
        Story workspace
        <small className="mt-1 block truncate text-[10.5px] font-normal text-[#949aa3]">
          {summary}
        </small>
      </span>
    </div>
  );
}

function SectionLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h2
      className={cn(
        "px-5 text-[10px] font-semibold uppercase tracking-[0.13em] text-[#868f9b]",
        className,
      )}
    >
      {children}
    </h2>
  );
}

function BrandMark() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 36 36"
      fill="none"
      className="size-8 text-[#c2d2e7]"
    >
      <path
        d="M8 7.5A3.5 3.5 0 0 1 11.5 4H27v23H12a4 4 0 0 0-4 4V7.5Z"
        fill="currentColor"
        opacity=".26"
      />
      <path
        d="M5 11a4 4 0 0 1 4-4h13v24H9a4 4 0 0 1-4-4V11Z"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <path
        d="M12 13h8M12 18h8M12 23h5M27 10h4v22H12"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}
