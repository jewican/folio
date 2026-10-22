"use client";

import { useEffect, useState } from "react";
import {
  ExternalLink,
  PanelRightClose,
  Quote,
  RotateCcw,
  TriangleAlert,
} from "lucide-react";
import { errorMessage, getPassage } from "@/lib/api";
import {
  fileKind,
  formatLongDate,
  formatReportDate,
  reportTone,
} from "@/lib/reports";
import type { Citation, FolioDocument, Passage } from "@/lib/types";
import { cn } from "@/lib/utils";

type EvidencePanelProps = {
  citation: Citation | null;
  documents: FolioDocument[];
  /** Overlay state below the xl breakpoint; the panel is a column above it. */
  open: boolean;
  onClose: () => void;
  ref?: React.Ref<HTMLElement>;
};

type PassageResult = { id: string; passage?: Passage; error?: string };

export function EvidencePanel({
  citation,
  documents,
  open,
  onClose,
  ref,
}: EvidencePanelProps) {
  const passageId = citation?.passage_id ?? null;
  const [result, setResult] = useState<PassageResult | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!passageId) return;
    let cancelled = false;
    getPassage(passageId).then(
      (passage) => {
        if (!cancelled) setResult({ id: passageId, passage });
      },
      (error) => {
        if (!cancelled) setResult({ id: passageId, error: errorMessage(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [passageId, attempt]);

  // A result for a different passage is stale; treat it as still loading.
  const current = result?.id === passageId ? result : null;

  return (
    <aside
      id="evidence-panel"
      ref={ref}
      tabIndex={-1}
      aria-label="Evidence"
      className={cn(
        "fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-[#d6dce2] bg-[#eef0f2] outline-none duration-300 ease-out sm:w-[440px] xl:static xl:z-auto xl:w-[400px] xl:translate-x-0 2xl:w-[460px]",
        open
          ? "visible translate-x-0 transition-[translate]"
          : "transition-[translate,visibility] max-xl:invisible max-xl:translate-x-full",
      )}
    >
      <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-[#dfe4e9] bg-[#f8f9fa] px-5 sm:h-16">
        <div className="min-w-0">
          <h2 className="text-[13px] font-semibold text-[#3d4652]">Evidence</h2>
          <p className="truncate text-[11px] text-[#8e9aa9]">
            {citation
              ? "The exact stored passage behind a claim"
              : "Select a citation to inspect it"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close evidence"
          className="grid size-8 place-items-center rounded-md text-[#8e9aa9] hover:bg-[#dde3eb60] hover:text-[#264b7d] xl:hidden"
        >
          <PanelRightClose size={18} />
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-5">
        {citation ? (
          <EvidenceDetail
            citation={citation}
            doc={documents.find((d) => d.doc_id === citation.doc_id)}
            tone={reportTone(citation.doc_id, documents)}
            result={current}
            onRetry={() => {
              setResult(null);
              setAttempt((n) => n + 1);
            }}
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <span className="grid size-12 place-items-center rounded-full bg-white text-[#8fa4bf] shadow-[0_1px_3px_#00000010]">
              <Quote size={19} />
            </span>
            <p className="mt-4 text-[14px] font-medium text-[#4c5866]">
              No passage selected
            </p>
            <p className="mt-1.5 max-w-[270px] text-[12px] leading-relaxed text-[#8994a1]">
              Every claim in an answer cites the passage it came from. Select a
              citation to read it here with its report date and page.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}

function EvidenceDetail({
  citation,
  doc,
  tone,
  result,
  onRetry,
}: {
  citation: Citation;
  doc: FolioDocument | undefined;
  tone: string;
  result: PassageResult | null;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-xl border border-[#dfe4e9] bg-white/70 p-4">
        <div className="flex items-start gap-2.5">
          <span
            aria-hidden
            className="mt-[5px] size-2 shrink-0 rounded-full"
            style={{ background: tone }}
          />
          <div className="min-w-0">
            <h3 className="text-[13.5px] font-semibold leading-snug text-[#2f3742]">
              {citation.title}
            </h3>
            <p className="mt-1 text-[12px] text-[#7d8896]">
              Reported{" "}
              <time dateTime={citation.report_date}>
                {formatLongDate(citation.report_date)}
              </time>
            </p>
          </div>
        </div>
        <dl className="mt-3.5 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[12px]">
          {doc && (
            <>
              <dt className="text-[#9aa4b1]">File</dt>
              <dd className="break-all text-[#4d5866]">{doc.filename}</dd>
            </>
          )}
          <dt className="text-[#9aa4b1]">Page</dt>
          <dd className="text-[#4d5866]">
            {citation.page ?? "None (text file)"}
          </dd>
          <dt className="text-[#9aa4b1]">Passage</dt>
          <dd className="break-all font-mono text-[11px] leading-[18px] text-[#4d5866]">
            {citation.passage_id}
          </dd>
          <dt className="text-[#9aa4b1]">Source</dt>
          <dd className="min-w-0">
            {citation.source_url ? (
              <a
                href={citation.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex max-w-full items-center gap-1 text-[#3f6ea8] hover:underline"
              >
                <span className="truncate">
                  {citation.source_url.replace(/^https?:\/\//, "")}
                </span>
                <ExternalLink size={11} className="shrink-0" />
              </a>
            ) : (
              <span className="text-[#9aa4b1]">No source link provided</span>
            )}
          </dd>
        </dl>
      </section>

      <article className="relative min-h-[320px] rounded-[3px] bg-white px-6 pb-14 pt-6 shadow-[0_3px_10px_#21364f0f,0_0_0_1px_#e2e5e9] sm:px-7">
        <div className="flex justify-between gap-3 text-[9.5px] uppercase tracking-[0.12em] text-[#9ca5b1]">
          <span>Folio / Evidence</span>
          <span>{doc ? fileKind(doc) : ""}</span>
        </div>
        <div className="mb-5 mt-3 h-px bg-[#e7e9ec]" />

        {result?.passage ? (
          <PassageText text={result.passage.text} quote={citation.quote} />
        ) : result?.error ? (
          <div role="alert" className="text-[13px] leading-relaxed text-[#8a4234]">
            <p className="flex items-center gap-2">
              <TriangleAlert size={15} /> {result.error}
            </p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 inline-flex items-center gap-1.5 font-medium hover:underline"
            >
              <RotateCcw size={13} /> Try again
            </button>
          </div>
        ) : (
          <div aria-label="Loading passage" className="flex flex-col gap-3.5">
            <span className="h-3 w-full animate-pulse rounded bg-[#eceff2]" />
            <span className="h-3 w-11/12 animate-pulse rounded bg-[#eceff2]" />
            <span className="h-3 w-4/5 animate-pulse rounded bg-[#eceff2]" />
            <span className="h-3 w-2/3 animate-pulse rounded bg-[#eceff2]" />
          </div>
        )}

        <div className="absolute inset-x-6 bottom-5 flex justify-between gap-3 text-[10px] tracking-[0.04em] text-[#a6adb6] sm:inset-x-7">
          <span>{formatReportDate(citation.report_date)}</span>
          <span className="tabular-nums">
            {citation.page === null ? "No page" : `Page ${citation.page}`}
          </span>
        </div>
      </article>
    </div>
  );
}

function PassageText({ text, quote }: { text: string; quote: string }) {
  const start = text.indexOf(quote);
  const body = "font-serif text-[15px] leading-[1.85] text-[#5d6875]";

  // The contract guarantees the quote is an exact substring; say so if it isn't.
  if (start < 0) {
    return (
      <>
        <p className={body}>{text}</p>
        <p className="mt-4 flex gap-2 rounded-md bg-[#fdf4f2] p-2.5 text-[12px] leading-relaxed text-[#8a4234]">
          <TriangleAlert size={14} className="mt-0.5 shrink-0" />
          The cited quote does not appear in this stored passage.
        </p>
      </>
    );
  }

  return (
    <p className={body}>
      {text.slice(0, start)}
      <mark className="rounded-[2px] bg-[#e2ecfa] text-[#2f4a6d] shadow-[3px_0_0_#e2ecfa,-3px_0_0_#e2ecfa] [box-decoration-break:clone]">
        {quote}
      </mark>
      {text.slice(start + quote.length)}
    </p>
  );
}
