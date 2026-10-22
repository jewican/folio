"use client";

import { useState } from "react";
import {
  ArrowLeftRight,
  ArrowRight,
  CircleSlash,
  GitCompareArrows,
  RotateCcw,
  Search,
  TriangleAlert,
} from "lucide-react";
import { toSource } from "@/components/folio/ask-view";
import { AiStatus } from "@/components/ui/ai-status";
import { WebSearchCitation } from "@/components/ui/web-search";
import { formatShortDate, reportTone } from "@/lib/reports";
import type {
  Change,
  Citation,
  CompareRequest,
  CompareResponse,
  FolioDocument,
} from "@/lib/types";
import { cn } from "@/lib/utils";

export type CompareState =
  | { status: "idle" }
  | { status: "loading"; request: CompareRequest }
  | { status: "done"; response: CompareResponse }
  | { status: "error"; request: CompareRequest; message: string };

type CompareViewProps = {
  documents: FolioDocument[] | null;
  state: CompareState;
  activeCitation: Citation | null;
  onOpenCitation: (citation: Citation) => void;
  onCompare: (request: CompareRequest) => void;
};

export function CompareView({
  documents,
  state,
  activeCitation,
  onOpenCitation,
  onCompare,
}: CompareViewProps) {
  const docs = documents ?? [];
  const lastRequest =
    state.status === "idle"
      ? null
      : state.status === "done"
        ? state.response
        : state.request;

  // null means "not picked yet": default to the earliest and latest reports.
  const [olderChoice, setOlderChoice] = useState<string | null>(
    lastRequest?.older_doc_id ?? null,
  );
  const [newerChoice, setNewerChoice] = useState<string | null>(
    lastRequest?.newer_doc_id ?? null,
  );
  const [question, setQuestion] = useState("");

  const olderId = olderChoice ?? docs[0]?.doc_id ?? "";
  const newerId = newerChoice ?? docs[docs.length - 1]?.doc_id ?? "";
  const older = docs.find((d) => d.doc_id === olderId);
  const newer = docs.find((d) => d.doc_id === newerId);

  // The backend rejects equal or reversed dates; it never swaps them for us.
  let problem: string | null = null;
  if (docs.length < 2) {
    problem = "Upload at least two reports with different report dates to compare them.";
  } else if (!older || !newer) {
    problem = "Pick an older and a newer report.";
  } else if (older.doc_id === newer.doc_id) {
    problem = "Pick two different reports.";
  } else if (older.report_date === newer.report_date) {
    problem = `Both reports are dated ${formatShortDate(older.report_date)}. Pick reports from different dates.`;
  } else if (older.report_date > newer.report_date) {
    problem = "The older report is dated after the newer one.";
  }
  const reversed = !!older && !!newer && older.report_date > newer.report_date;
  const loading = state.status === "loading";

  return (
    <div className="mx-auto w-full max-w-[760px] px-5 pb-12 pt-10 sm:px-8 sm:pt-14">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#95a0ad]">
        Compare versions
      </p>
      <h1 className="mt-3 text-[25px] font-semibold leading-[1.2] tracking-[-0.035em] text-[#2c333d] sm:text-[29px]">
        What changed between two dated reports?
      </h1>
      <p className="mt-3 max-w-xl text-[14px] leading-relaxed text-[#77818d]">
        Pick an older and a newer report. Each change is backed by passages from
        both versions; information only in the newer report is marked as added.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (problem || loading) return;
          const trimmed = question.trim();
          onCompare({
            older_doc_id: olderId,
            newer_doc_id: newerId,
            ...(trimmed ? { question: trimmed } : {}),
          });
        }}
        className="mt-8 rounded-[13px] border border-[#d7dce2] bg-white p-4 shadow-[0_2px_3px_#15233803,0_8px_25px_#15233804] sm:p-5"
      >
        <div className="grid items-end gap-3 sm:grid-cols-[1fr_auto_1fr]">
          <ReportPicker
            label="Older report"
            value={olderId}
            documents={docs}
            onChange={setOlderChoice}
          />
          <span
            aria-hidden
            className="hidden size-9 place-items-center text-[#a1abb8] sm:grid"
          >
            <ArrowRight size={17} />
          </span>
          <ReportPicker
            label="Newer report"
            value={newerId}
            documents={docs}
            onChange={setNewerChoice}
          />
        </div>

        <label className="mt-4 flex items-center gap-3 rounded-lg border border-[#e1e5ea] px-3 text-[#a1abb8] focus-within:border-[#8eafd3]">
          <Search size={16} strokeWidth={1.6} aria-hidden />
          <span className="sr-only">Question (optional)</span>
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={2000}
            autoComplete="off"
            placeholder="Optional: what should the comparison focus on?"
            className="min-w-0 flex-1 bg-transparent py-2.5 text-[14px] text-[#333d4a] outline-none placeholder:text-[#868e99]"
          />
        </label>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p
            role={problem && documents ? "alert" : undefined}
            className={cn(
              "flex items-center gap-2 text-[12px]",
              problem && documents ? "text-[#b4593f]" : "text-[#8b95a1]",
            )}
          >
            {!documents
              ? "Loading reports…"
              : (problem ??
                `Compares the ${formatShortDate(older!.report_date)} report with the ${formatShortDate(newer!.report_date)} report.`)}
            {reversed && (
              <button
                type="button"
                onClick={() => {
                  setOlderChoice(newerId);
                  setNewerChoice(olderId);
                }}
                className="inline-flex items-center gap-1 font-medium text-[#315f9e] hover:underline"
              >
                <ArrowLeftRight size={12} /> Swap
              </button>
            )}
          </p>
          <button
            type="submit"
            disabled={!!problem || loading || !documents}
            className="inline-flex items-center gap-2 rounded-lg bg-[#252d37] px-3.5 py-2 text-[13px] font-medium text-white transition hover:enabled:-translate-y-px hover:enabled:bg-[#476c9a] disabled:bg-[#eceef0] disabled:text-[#a6adb6]"
          >
            <GitCompareArrows size={15} />
            {loading ? "Comparing…" : "Compare reports"}
          </button>
        </div>
      </form>

      {state.status !== "idle" && (
        <CompareResult
          state={state}
          documents={docs}
          activeCitation={activeCitation}
          onOpenCitation={onOpenCitation}
          onRetry={onCompare}
        />
      )}
    </div>
  );
}

function ReportPicker({
  label,
  value,
  documents,
  onChange,
}: {
  label: string;
  value: string;
  documents: FolioDocument[];
  onChange: (docId: string) => void;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="flex items-center gap-1.5 text-[11px] font-medium text-[#6b7684]">
        {value && (
          <span
            aria-hidden
            className="size-1.5 rounded-full"
            style={{ background: reportTone(value, documents) }}
          />
        )}
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={documents.length === 0}
        className="w-full min-w-0 truncate rounded-lg border border-[#d9dcdf] bg-white px-2.5 py-2 text-[13px] text-[#333d4a] outline-none focus:border-[#8eafd3] focus:shadow-[0_0_0_3px_#c6d9ee40]"
      >
        {documents.map((doc) => (
          <option key={doc.doc_id} value={doc.doc_id}>
            {formatShortDate(doc.report_date)} · {doc.title}
          </option>
        ))}
      </select>
    </label>
  );
}

function CompareResult({
  state,
  documents,
  activeCitation,
  onOpenCitation,
  onRetry,
}: {
  state: Exclude<CompareState, { status: "idle" }>;
  documents: FolioDocument[];
  activeCitation: Citation | null;
  onOpenCitation: (citation: Citation) => void;
  onRetry: (request: CompareRequest) => void;
}) {
  const response = state.status === "done" ? state.response : null;
  const request = state.status === "done" ? state.response : state.request;
  const older = documents.find((d) => d.doc_id === request.older_doc_id);
  const newer = documents.find((d) => d.doc_id === request.newer_doc_id);

  // Chips share one number per cited passage across the whole comparison.
  const sourceNumber = new Map<string, number>();
  for (const change of response?.changes ?? []) {
    for (const c of [...change.older_citations, ...change.newer_citations]) {
      if (!sourceNumber.has(c.passage_id)) {
        sourceNumber.set(c.passage_id, sourceNumber.size + 1);
      }
    }
  }

  return (
    <article className="folio-answer mt-10 border-t border-[#e4e7ea] pt-8">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#95a0ad]">
        Comparison
      </p>
      <h2 className="mt-2 text-[21px] font-medium leading-snug tracking-[-0.025em] text-[#2c333d]">
        {response?.question ?? request.question ?? "What changed between these reports?"}
      </h2>
      <p className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] text-[#5f6b79]">
        {[older, newer].map((doc, i) =>
          doc ? (
            <span key={doc.doc_id} className="contents">
              {i === 1 && <ArrowRight size={12} className="text-[#a1abb8]" />}
              <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-[#e1e5ea] bg-white/70 px-2.5 py-1">
                <span
                  aria-hidden
                  className="size-1.5 shrink-0 rounded-full"
                  style={{ background: reportTone(doc.doc_id, documents) }}
                />
                <span className="truncate">{doc.title}</span>
                <span className="shrink-0 text-[#9aa4b1]">
                  {formatShortDate(doc.report_date)}
                </span>
              </span>
            </span>
          ) : null,
        )}
      </p>

      <div className="mt-6">
        {state.status === "loading" ? (
          <AiStatus state="researching" label="Comparing both reports" />
        ) : state.status === "error" ? (
          <AiStatus state="error" label="The comparison failed" timer={false} />
        ) : state.response.status === "compared" ? (
          <AiStatus
            state="done"
            timer={false}
            label={
              state.response.changes.length === 0
                ? "No supported changes"
                : `${state.response.changes.length} ${state.response.changes.length === 1 ? "change" : "changes"} found`
            }
            detail={
              state.response.meta.cached
                ? "cached"
                : `${(state.response.meta.elapsed_ms / 1000).toFixed(1)}s`
            }
          />
        ) : (
          <AiStatus
            state="insufficient"
            timer={false}
            states={{
              insufficient: {
                label: "Not enough evidence to compare",
                active: false,
                icon: <CircleSlash size={16} className="text-[#b08a46]" />,
              },
            }}
          />
        )}
      </div>

      {state.status === "loading" && (
        <div aria-hidden className="mt-5 grid gap-3">
          {[0, 1].map((i) => (
            <div key={i} className="rounded-xl border border-[#e6e9ec] bg-white p-4">
              <span className="block h-3 w-1/4 animate-pulse rounded bg-[#e5e9ed]" />
              <span className="mt-3 block h-3 w-3/4 animate-pulse rounded bg-[#e5e9ed]" />
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <span className="h-16 animate-pulse rounded-lg bg-[#eef0f2]" />
                <span className="h-16 animate-pulse rounded-lg bg-[#eef0f2]" />
              </div>
            </div>
          ))}
        </div>
      )}

      {state.status === "error" && (
        <div
          role="alert"
          className="mt-5 flex gap-3 rounded-xl border border-[#efd3cd] bg-[#fdf4f2] p-4 text-[13px] leading-relaxed text-[#8a4234]"
        >
          <TriangleAlert size={17} className="mt-0.5 shrink-0" />
          <div>
            <p>{state.message}</p>
            <button
              type="button"
              onClick={() => onRetry(state.request)}
              className="mt-2 inline-flex items-center gap-1.5 font-medium text-[#6f3024] hover:underline"
            >
              <RotateCcw size={13} /> Try again
            </button>
          </div>
        </div>
      )}

      {response?.status === "insufficient_evidence" && (
        <div className="mt-5 rounded-xl border border-[#eadfc8] bg-[#fbf7ee] p-4 text-[14px] leading-relaxed text-[#6d5a35]">
          <p>{response.summary}</p>
          <p className="mt-2 text-[12px] text-[#8f7c57]">
            Missing evidence doesn&apos;t mean nothing changed. Try a narrower
            question, or a different pair of reports.
          </p>
        </div>
      )}

      {response?.status === "compared" && (
        <>
          <p className="mt-5 text-[15px] leading-[1.8] text-[#4a5664]">
            {response.summary}
          </p>
          {response.changes.length > 0 && (
            <ol className="mt-6 grid gap-3.5">
              {response.changes.map((change, index) => (
                <ChangeCard
                  key={index}
                  change={change}
                  documents={documents}
                  sourceNumber={sourceNumber}
                  activeCitation={activeCitation}
                  onOpenCitation={onOpenCitation}
                />
              ))}
            </ol>
          )}
        </>
      )}

      {response && (
        <p className="mt-8 flex flex-wrap gap-x-4 gap-y-1 border-t border-[#e4e7ea] pt-4 text-[11px] text-[#9ca5b1]">
          <span>BM25 retrieval</span>
          <span>{response.meta.elapsed_ms.toLocaleString("en-US")} ms</span>
          <span>{response.meta.cached ? "Cached result" : "Not cached"}</span>
        </p>
      )}
    </article>
  );
}

const KIND_STYLES: Record<Change["kind"], { label: string; className: string }> = {
  updated: { label: "Updated", className: "bg-[#e9f0f9] text-[#3f6ea8]" },
  added: { label: "Added", className: "bg-[#eaf4ec] text-[#4b8256]" },
  unresolved: { label: "Unresolved", className: "bg-[#fbf3e3] text-[#9a7432]" },
};

function ChangeCard({
  change,
  documents,
  sourceNumber,
  activeCitation,
  onOpenCitation,
}: {
  change: Change;
  documents: FolioDocument[];
  sourceNumber: Map<string, number>;
  activeCitation: Citation | null;
  onOpenCitation: (citation: Citation) => void;
}) {
  const kind = KIND_STYLES[change.kind];
  const side = (
    label: string,
    text: string | null,
    citations: Citation[],
    emptyText: string,
  ) => {
    const cited = citations[0];
    return (
      <div className="min-w-0 rounded-lg bg-[#f6f7f8] p-3">
        <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8e98a5]">
          {cited && (
            <span
              aria-hidden
              className="size-1.5 rounded-full"
              style={{ background: reportTone(cited.doc_id, documents) }}
            />
          )}
          {label}
          {cited && (
            <span className="font-normal normal-case tracking-normal text-[#a3acb7]">
              · {formatShortDate(cited.report_date)}
            </span>
          )}
        </p>
        {text ? (
          <p className="mt-1.5 text-[13.5px] leading-relaxed text-[#3e4856]">
            {text}
            {citations.map((citation, i) => (
              <WebSearchCitation
                key={i}
                linked={false}
                source={toSource(citation, documents, onOpenCitation)}
                index={sourceNumber.get(citation.passage_id)}
                data-active={
                  activeCitation?.passage_id === citation.passage_id &&
                  activeCitation.quote === citation.quote
                }
              />
            ))}
          </p>
        ) : (
          <p className="mt-1.5 text-[13px] italic text-[#9aa3ae]">{emptyText}</p>
        )}
      </div>
    );
  };

  return (
    <li className="rounded-xl border border-[#e3e6ea] bg-white p-4 shadow-[0_1px_2px_#00000005] sm:p-5">
      <span
        className={cn(
          "inline-block rounded-full px-2 py-0.5 text-[11px] font-medium",
          kind.className,
        )}
      >
        {kind.label}
      </span>
      <p className="mt-2 text-[14.5px] font-medium leading-snug text-[#2f3843]">
        {change.summary}
      </p>
      <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
        {side(
          "Before",
          change.before,
          change.older_citations,
          "No earlier statement cited for this.",
        )}
        {side("After", change.after, change.newer_citations, "")}
      </div>
      {change.kind === "unresolved" && (
        <p className="mt-2.5 text-[12px] leading-relaxed text-[#8f7c57]">
          The two reports don&apos;t describe this in comparable terms, so no
          change is asserted.
        </p>
      )}
    </li>
  );
}
