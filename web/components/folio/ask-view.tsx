"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ScannableText } from "@/components/folio/scannable-text";
import { CitationButton } from "@/components/folio/citation-button";
import {
  ArrowUp,
  CircleSlash,
  RotateCcw,
  Search,
  TriangleAlert,
} from "lucide-react";
import { AiStatus } from "@/components/ui/ai-status";
import {
  WebSearch,
  type WebSource,
} from "@/components/ui/web-search";
import {
  citationLabel,
  formatShortDate,
  reportBadge,
  reportTone,
} from "@/lib/reports";
import type { AskResponse, Citation, FolioDocument } from "@/lib/types";
import { cn } from "@/lib/utils";
import { MAX_ASK_DOCUMENTS } from "@/lib/api";

export type AskState =
  | { status: "idle" }
  | { status: "loading"; question: string; docIds: string[] }
  | { status: "done"; response: AskResponse }
  | { status: "error"; question: string; docIds: string[]; message: string };

export function Composer({
  compact = false,
  selectedCount,
  onAsk,
}: {
  compact?: boolean;
  selectedCount: number;
  onAsk: (question: string) => void;
}) {
  const [value, setValue] = useState("");
  const noSelection = selectedCount === 0;
  const tooManySelected = selectedCount > MAX_ASK_DOCUMENTS;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        const question = value.trim();
        if (!question || noSelection || tooManySelected) return;
        onAsk(question);
        setValue("");
      }}
      className="overflow-hidden rounded-[13px] border border-[#d7dce2] bg-white shadow-[0_2px_3px_#15233803,0_8px_25px_#15233804] transition-[border-color,box-shadow] focus-within:border-[#8eafd3] focus-within:shadow-[0_0_0_3px_#c6d9ee40,0_6px_24px_#15233805]"
    >
      <div
        className={cn(
          "flex items-center gap-3 text-[#a1abb8]",
          compact ? "px-4 pb-1.5 pt-3" : "px-5 pb-2.5 pt-5",
        )}
      >
        <Search size={compact ? 17 : 21} strokeWidth={1.6} aria-hidden />
        <input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          maxLength={2000}
          autoComplete="off"
          aria-label="Ask a question about the selected reports"
          placeholder={
            compact ? "Ask another question…" : "Ask a question. See the source."
          }
          className={cn(
            "min-w-0 flex-1 bg-transparent py-1 text-[#333d4a] outline-none placeholder:text-[#868e99]",
            compact ? "text-[14px]" : "text-[17px] tracking-[-0.02em]",
          )}
        />
        <button
          type="submit"
          disabled={!value.trim() || noSelection || tooManySelected}
          aria-label="Ask question"
          className={cn(
            "grid shrink-0 place-items-center rounded-lg bg-[#252d37] text-white transition hover:enabled:-translate-y-px hover:enabled:bg-[#476c9a] disabled:bg-[#eceef0] disabled:text-[#a6adb6]",
            compact ? "size-7" : "size-8",
          )}
        >
          <ArrowUp size={compact ? 16 : 18} />
        </button>
      </div>
      <p
        className={cn(
          "text-[11px]",
          compact ? "px-4 pb-2.5" : "px-5 pb-3.5",
          noSelection || tooManySelected ? "text-[#b4593f]" : "text-[#8b95a1]",
        )}
      >
        {noSelection
          ? "Select at least one report to ask a question."
          : tooManySelected
            ? `Select up to ${MAX_ASK_DOCUMENTS} reports per question.`
            : `Answers only from the ${selectedCount} selected ${selectedCount === 1 ? "report" : "reports"}.`}
      </p>
    </form>
  );
}

export function AskIntro({
  selectedCount,
  onAsk,
}: {
  selectedCount: number;
  onAsk: (question: string) => void;
}) {
  return (
    <section className="mx-auto w-full max-w-[720px] px-5 pb-16 pt-10 sm:px-8 sm:pt-16">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#95a0ad]">
        Ask the reports
      </p>
      <h1 className="mt-3 text-[27px] font-semibold leading-[1.2] tracking-[-0.035em] text-[#2c333d] sm:text-[32px]">
        What changed, when was it reported, and which report says so?
      </h1>
      <p className="mt-3 max-w-xl text-[14px] leading-relaxed text-[#77818d]">
        Choose the reports to search, then ask a question. Every claim in the
        answer links to the exact passage that supports it.
      </p>
      <div className="mt-8">
        <Composer selectedCount={selectedCount} onAsk={onAsk} />
      </div>

    </section>
  );
}

type AnswerViewProps = {
  heading?: string;
  state: Exclude<AskState, { status: "idle" }>;
  documents: FolioDocument[];
  activeCitation: Citation | null;
  onOpenCitation: (citation: Citation) => void;
  onRetry: (question: string) => void;
};

export function AnswerView({
  heading,
  state,
  documents,
  activeCitation,
  onOpenCitation,
  onRetry,
}: AnswerViewProps) {
  const reduced = useReducedMotion();
  const response = state.status === "done" ? state.response : null;
  const question =
    state.status === "done" ? state.response.question : state.question;
  const docIds =
    state.status === "done" ? state.response.doc_ids : state.docIds;

  // One source card per cited passage; chips share the card's number.
  const citations = response?.claims.flatMap((c) => c.citations) ?? [];
  const sources: WebSource[] = [];
  const seen = new Set<string>();
  for (const citation of citations) {
    if (seen.has(citation.passage_id)) continue;
    sources.push(toSource(citation, documents, onOpenCitation));
    seen.add(citation.passage_id);
  }
  const citedReports = new Set(citations.map((c) => c.doc_id)).size;

  return (
    <article className="folio-answer mx-auto w-full max-w-[720px] px-5 pb-10 pt-8 sm:px-8 sm:pt-10">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#95a0ad]">
        {heading ? "Catch Me Up" : "Question"}
      </p>
      <h1 className="mt-2 text-[23px] font-medium leading-snug tracking-[-0.025em] text-[#2c333d] sm:text-[25px]">
        {heading ?? question}
      </h1>

      <ul aria-label="Reports searched" className="mt-3 flex flex-wrap gap-1.5">
        {documents
          .filter((doc) => docIds.includes(doc.doc_id))
          .map((doc) => (
            <li
              key={doc.doc_id}
              className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-[#e1e5ea] bg-white/70 px-2.5 py-1 text-[11px] text-[#5f6b79]"
            >
              <span
                aria-hidden
                className="size-1.5 shrink-0 rounded-full"
                style={{ background: reportTone(doc.doc_id, documents) }}
              />
              <span className="truncate">{doc.title}</span>
              <span className="shrink-0 text-[#9aa4b1]">
                {formatShortDate(doc.report_date)}
              </span>
            </li>
          ))}
      </ul>

      <div className="mt-6">
        {state.status === "loading" ? (
          <AiStatus
            state="researching"
            label={`Searching ${docIds.length} ${docIds.length === 1 ? "report" : "reports"}`}
          />
        ) : state.status === "error" ? (
          <AiStatus state="error" label="The request failed" timer={false} />
        ) : state.response.status === "answered" ? (
          <AiStatus
            state="done"
            timer={false}
            label={`Answered from ${sources.length} ${sources.length === 1 ? "passage" : "passages"}`}
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
                label: "No supported answer",
                active: false,
                icon: <CircleSlash size={16} className="text-[#b08a46]" />,
              },
            }}
          />
        )}
      </div>

      {state.status === "loading" && (
        <div aria-hidden className="briefing-skeleton">{[0, 1, 2].map((i) => <div key={i}><i /><span><b /><b /><b /></span></div>)}</div>
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
              onClick={() => onRetry(state.question)}
              className="mt-2 inline-flex items-center gap-1.5 font-medium text-[#6f3024] hover:underline"
            >
              <RotateCcw size={13} /> Try again
            </button>
          </div>
        </div>
      )}

      {response?.status === "insufficient_evidence" && (
        <div className="mt-5 rounded-xl border border-[#eadfc8] bg-[#fbf7ee] p-4 text-[14px] leading-relaxed text-[#6d5a35]">
          <p>{response.answer}</p>
          <p className="mt-2 text-[12px] text-[#8f7c57]">
            Folio only answers from passages it can cite. Try rephrasing, or
            include more reports in the selection.
          </p>
        </div>
      )}

      {response?.status === "answered" && (
        <>
          <div className="takeaway-heading"><h2>{heading ? "The key takeaways" : "At a glance"}</h2><span><span className="status-dot" /> AI GENERATED · SOURCE LINKED</span></div>
          <ol className="takeaway-grid">
            {response.claims.map((claim, claimIndex) => (
              <motion.li key={`${response.question}-${claimIndex}`} className="takeaway-card"
                initial={{ opacity: 0, y: reduced ? 0 : 10 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduced ? 0 : .25, delay: reduced ? 0 : Math.min(claimIndex * .045, .2) }}>
                <span className="takeaway-number">{String(claimIndex + 1).padStart(2, "0")}</span>
                <div><ScannableText text={claim.text} /><div className="claim-attribution">
                  {claim.citations.map((citation, i) => <CitationButton key={i} citation={citation}
                    active={activeCitation?.passage_id === citation.passage_id && activeCitation.quote === citation.quote}
                    onOpen={onOpenCitation} />)}
                </div></div>
              </motion.li>
            ))}
          </ol>
          <details className="answer-context"><summary>Read the full answer</summary><p>{response.answer}</p></details>

          <WebSearch
            className="folio-sources mt-7 w-full"
            sources={sources}
            linked={false}
            label={`${sources.length} ${sources.length === 1 ? "passage" : "passages"} from ${citedReports} ${citedReports === 1 ? "report" : "reports"}`}
          />
        </>
      )}

      {response && (
        <p className="mt-8 flex flex-wrap gap-x-4 gap-y-1 border-t border-[#e4e7ea] pt-4 text-[11px] text-[#9ca5b1]">
          <span>Generated from selected reports</span>
          <span>{(response.meta.elapsed_ms / 1000).toFixed(1)}s</span>
          <span>{response.meta.cached ? "Cached result" : "Not cached"}</span>
        </p>
      )}
    </article>
  );
}

export function toSource(
  citation: Citation,
  documents: FolioDocument[],
  onOpen: (citation: Citation) => void,
): WebSource {
  return {
    id: citation.passage_id,
    title: citation.title,
    url: citation.source_url ?? `#${citation.passage_id}`,
    snippet: citation.quote,
    favicon: reportBadge(reportTone(citation.doc_id, documents)),
    pageLabel: citationLabel(citation),
    onOpen: () => onOpen(citation),
  };
}
