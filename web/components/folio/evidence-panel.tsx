"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Check, ChevronLeft, ChevronRight, Copy, ExternalLink, FileText, PanelRightClose, Quote, RotateCcw, TriangleAlert } from "lucide-react";
import { errorMessage, getPassage } from "@/lib/api";
import { fileKind, formatReportDate, reportTone, sourceDomain } from "@/lib/reports";
import type { Citation, FolioDocument, Passage } from "@/lib/types";
import { cn } from "@/lib/utils";

type EvidencePanelProps = {
  citation: Citation | null;
  citations?: Citation[];
  onSelectCitation?: (citation: Citation) => void;
  documents: FolioDocument[];
  open: boolean;
  onClose: () => void;
  ref?: React.Ref<HTMLElement>;
};
type PassageResult = { id: string; passage?: Passage; error?: string };

export function EvidencePanel({ citation, citations = [], onSelectCitation, documents, open, onClose, ref }: EvidencePanelProps) {
  const passageId = citation?.passage_id ?? null;
  const [result, setResult] = useState<PassageResult | null>(null);
  const [attempt, setAttempt] = useState(0);
  const panelRef = useRef<HTMLElement | null>(null);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (!passageId) return;
    let cancelled = false;
    getPassage(passageId).then((passage) => {
      if (!cancelled) setResult({ id: passageId, passage });
    }, (error) => {
      if (!cancelled) setResult({ id: passageId, error: errorMessage(error) });
    });
    return () => { cancelled = true; };
  }, [passageId, attempt]);

  useEffect(() => {
    if (!open) return;
    const desktop = window.matchMedia("(min-width: 80rem)");
    const previousOverflow = document.body.style.overflow;
    const syncScroll = () => { document.body.style.overflow = desktop.matches ? previousOverflow : "hidden"; };
    syncScroll();
    desktop.addEventListener("change", syncScroll);
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== "Tab" || desktop.matches) return;
      const controls = Array.from(panelRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], summary, [tabindex="0"]') ?? []).filter((el) => el.getClientRects().length > 0);
      const first = controls[0];
      const last = controls.at(-1);
      if (!first || !last) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panelRef.current)) { event.preventDefault(); first.focus(); }
    };
    panelRef.current?.addEventListener("keydown", trapFocus);
    const panel = panelRef.current;
    return () => {
      document.body.style.overflow = previousOverflow;
      desktop.removeEventListener("change", syncScroll);
      panel?.removeEventListener("keydown", trapFocus);
    };
  }, [open]);

  const current = result?.id === passageId ? result : null;
  const index = citations.findIndex((item) => item.passage_id === citation?.passage_id && item.quote === citation.quote);
  return (
    <aside id="evidence-panel" ref={(node) => { panelRef.current = node; if (typeof ref === "function") ref(node); else if (ref) ref.current = node; }} tabIndex={-1} aria-label="Evidence"
      className={cn("evidence-panel fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-[#d6dce2] bg-[#eef0f2] outline-none duration-300 ease-out sm:w-[440px] xl:static xl:z-auto xl:w-[400px] xl:translate-x-0 2xl:w-[460px]", open ? "visible translate-x-0 transition-[translate]" : "transition-[translate,visibility] max-xl:invisible max-xl:translate-x-full")}>
      <header className="evidence-header"><div><span className="news-eyebrow"><Quote size={12} /> FOLLOW THE EVIDENCE</span><h2>Go straight to the source.</h2></div><button type="button" onClick={onClose} aria-label="Close evidence" className="evidence-close xl:hidden"><PanelRightClose size={18} /></button></header>
      {citations.length > 0 && <div className="evidence-navigation"><span>{index >= 0 ? `${index + 1} of ${citations.length}` : citations.length} cited {citations.length === 1 ? "passage" : "passages"}</span><div><button type="button" disabled={index <= 0 || !onSelectCitation} aria-label="Previous evidence" onClick={() => onSelectCitation?.(citations[index - 1])}><ChevronLeft size={15} /></button><button type="button" disabled={index >= citations.length - 1 || !onSelectCitation} aria-label="Next evidence" onClick={() => onSelectCitation?.(citations[index + 1])}><ChevronRight size={15} /></button></div></div>}
      <div className="evidence-scroll">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={citation ? `${citation.passage_id}:${citation.quote}` : "empty"} initial={{ opacity: 0, x: reduced ? 0 : 6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: reduced ? 0 : .15 }}>
            {citation ? <EvidenceDetail citation={citation} doc={documents.find((doc) => doc.doc_id === citation.doc_id)} tone={reportTone(citation.doc_id, documents)} result={current} onRetry={() => { setResult(null); setAttempt((n) => n + 1); }} /> : <>
              <div className="evidence-welcome"><span className="evidence-welcome-icon"><Quote size={25} strokeWidth={1.3} /></span><h3>The reporting behind<br />the takeaway.</h3><p>Tap a source beneath any claim to see its exact quote and surrounding context.</p><div className="evidence-guide"><span>01 <strong>Choose a claim</strong></span><span>02 <strong>Read the cited quote</strong></span><span>03 <strong>Explore the full passage</strong></span></div></div>
              {citations.length > 0 && onSelectCitation ? <div className="evidence-source-list"><p className="news-eyebrow">CITED IN THIS VIEW</p>{citations.map((item, i) => <button key={`${item.passage_id}-${i}`} onClick={() => onSelectCitation(item)}><Quote size={14} /><span>{item.title}<small>{formatReportDate(item.report_date)}</small></span><ChevronRight size={13} /></button>)}</div> : documents.length > 0 && <div className="evidence-source-list"><p className="news-eyebrow">IN THE SOURCE COLLECTION</p>{documents.map((doc) => <div key={doc.doc_id}><FileText size={15} /><span>{doc.title}<small>{doc.source_url ? <a href={doc.source_url} target="_blank" rel="noreferrer">{sourceDomain(doc.source_url)} <ExternalLink size={10} /></a> : "Uploaded report"}</small></span></div>)}</div>}
            </>}
          </motion.div>
        </AnimatePresence>
      </div>
    </aside>
  );
}

function EvidenceDetail({ citation, doc, tone, result, onRetry }: { citation: Citation; doc: FolioDocument | undefined; tone: string; result: PassageResult | null; onRetry: () => void }) {
  const [context, setContext] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");
  const passage = result?.passage;
  const matches = passage && (["passage_id", "doc_id", "title", "report_date", "source_url", "page"] as const).every((field) => passage[field] === citation[field]) && citation.quote.trim().length > 0 && passage.text.includes(citation.quote);
  const evidenceError = result?.error ?? (passage && !matches ? "The citation does not match this stored passage. Try again." : null);
  async function copyQuote() {
    if (!matches) return;
    try { await navigator.clipboard.writeText(citation.quote); setCopyStatus("Quote copied"); }
    catch { setCopyStatus("Could not copy. You can select and copy the quote below."); }
  }
  return <div className="evidence-detail">
    <div className="evidence-source-card"><span className="source-domain"><span style={{ background: tone }} />{sourceDomain(citation.source_url)}</span><h3>{citation.title}</h3><p><time dateTime={citation.report_date}>{formatReportDate(citation.report_date)}</time><span>·</span>{citation.page === null ? doc ? fileKind(doc) : "Text report" : `Page ${citation.page}`}</p>{citation.source_url && <a className="publisher-link" href={citation.source_url} target="_blank" rel="noreferrer">Open publisher source <ExternalLink size={12} /></a>}</div>
    <div className="evidence-mode" aria-label="Evidence display"><button aria-pressed={!context} onClick={() => setContext(false)}><Quote size={13} /> Cited quote</button><button aria-pressed={context} onClick={() => setContext(true)}><FileText size={13} /> Full passage</button></div>
    <article className="evidence-passage" aria-busy={!passage && !evidenceError}>
      {matches && passage ? <><p className="evidence-match"><Check size={12} /> Exact match in stored passage</p>{context ? <PassageText text={passage.text} quote={citation.quote} /> : <blockquote>{citation.quote}</blockquote>}<div className="evidence-quote-footer"><span>{context ? "Original passage · quote highlighted" : "Verbatim source excerpt"}</span><button onClick={copyQuote} aria-label="Copy cited quote"><Copy size={12} /> Copy</button></div></> : evidenceError ? <div role="alert" className="evidence-error"><TriangleAlert size={17} /><p>{evidenceError}</p><button onClick={onRetry}><RotateCcw size={13} /> Try again</button></div> : <div aria-label="Loading passage" className="evidence-skeleton"><span /><span /><span /><span /></div>}
    </article>
    <p role="status" className="copy-status">{copyStatus}</p>
    <details className="evidence-metadata"><summary>Document details</summary><dl>{doc && <><dt>File</dt><dd>{doc.filename}</dd></>}<dt>Passage ID</dt><dd>{citation.passage_id}</dd><dt>Source link</dt><dd>{citation.source_url ?? "Not provided"}</dd></dl></details>
    <p className="evidence-footnote">This excerpt supports a specific claim. The publisher source provides broader context.</p>
  </div>;
}

function PassageText({ text, quote }: { text: string; quote: string }) {
  const start = text.indexOf(quote);
  if (start < 0) return <p>{text}</p>;
  return <p className="evidence-context">{text.slice(0, start)}<mark>{quote}</mark>{text.slice(start + quote.length)}</p>;
}
