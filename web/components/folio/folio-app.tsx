"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, MotionConfig, useReducedMotion } from "motion/react";
import { ArrowLeft, ArrowRight, BookOpen, Check, FileText, MessageCircle, Plus, Sparkles, TrendingUp } from "lucide-react";
import { AnswerView, Composer, type AskState } from "@/components/folio/ask-view";
import { CompareView, type CompareState } from "@/components/folio/compare-view";
import { EvidencePanel } from "@/components/folio/evidence-panel";
import { StoryTimeline } from "@/components/folio/story-timeline";
import { NewsHeader } from "@/components/folio/news-header";
import { UploadDialog } from "@/components/folio/upload-dialog";
import { MAX_ASK_DOCUMENTS, ask, compare, errorMessage, listDocuments, uploadDocument, type UploadRequest } from "@/lib/api";
import { formatReportDate } from "@/lib/reports";
import { storyTitle } from "@/lib/story";
import type { Citation, CompareRequest, FolioDocument } from "@/lib/types";

type View = "catch-up" | "compare" | "ask";
const VIEWS = [{ id: "catch-up", label: "Catch Me Up", icon: Sparkles }, { id: "compare", label: "What Changed", icon: TrendingUp }, { id: "ask", label: "Ask Folio", icon: MessageCircle }] as const;
const CATCH_UP_QUESTION = "Catch me up on this story using the selected reports. Give 3–5 concise key takeaways, one sentence per claim, in report-date order. Distinguish allegations from findings and responses. Include what remains unresolved. Cite the evidence for every claim.";

export function FolioApp() {
  const reduced = useReducedMotion();
  const [documents, setDocuments] = useState<FolioDocument[] | null>(null);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [documentsRequest, setDocumentsRequest] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [compareChoices, setCompareChoices] = useState<[string, string] | null>(null);
  const [view, setView] = useState<View>("catch-up");
  const [askState, setAskState] = useState<AskState>({ status: "idle" });
  const [catchState, setCatchState] = useState<AskState>({ status: "idle" });
  const [compareState, setCompareState] = useState<CompareState>({ status: "idle" });
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const askRun = useRef(0);
  const catchRun = useRef(0);
  const compareRun = useRef(0);
  const evidenceRef = useRef<HTMLElement>(null);
  const evidenceTrigger = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDocuments().then((docs) => {
      if (cancelled) return;
      setDocuments(docs);
      setSelectedIds(docs.map((doc) => doc.doc_id));
      setDocumentsError(null);
    }, (error) => { if (!cancelled) setDocumentsError(errorMessage(error)); });
    return () => { cancelled = true; };
  }, [documentsRequest]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && evidenceOpen) {
        setEvidenceOpen(false);
        evidenceTrigger.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [evidenceOpen]);

  const selection = documents?.filter((doc) => selectedIds.includes(doc.doc_id)).map((doc) => doc.doc_id) ?? [];
  const comparisonIds: [string, string] = compareChoices ?? [documents?.at(-2)?.doc_id ?? "", documents?.at(-1)?.doc_id ?? ""];
  const timelineSelection = view === "compare" ? comparisonIds.filter(Boolean) : selection;
  function toggleTimelineDocument(id: string) {
    if (view !== "compare") {
      toggleDocument(id);
      return;
    }
    const ids = comparisonIds.includes(id)
      ? comparisonIds.filter((item) => item && item !== id)
      : [...comparisonIds.filter(Boolean), id];
    if (ids.length > 2) return;
    const sorted = documents?.filter((doc) => ids.includes(doc.doc_id)).map((doc) => doc.doc_id) ?? [];
    setCompareChoices([sorted[0] ?? "", sorted[1] ?? ""]);
  }
  function toggleDocument(id: string) {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }
  async function upload(request: UploadRequest) {
    const doc = await uploadDocument(request);
    setDocuments((current) => [...(current ?? []), doc].sort((a, b) => a.report_date.localeCompare(b.report_date) || a.doc_id.localeCompare(b.doc_id)));
    setSelectedIds((current) => [...current, doc.doc_id]);
    setDocumentsError(null);
    setUploadOpen(false);
  }
  async function askQuestion(question: string, catchUp = false) {
    const docIds = selection;
    if (!docIds.length || docIds.length > MAX_ASK_DOCUMENTS) return;
    const runRef = catchUp ? catchRun : askRun;
    const run = ++runRef.current;
    const setState = catchUp ? setCatchState : setAskState;
    setView(catchUp ? "catch-up" : "ask");
    setActiveCitation(null);
    setState({ status: "loading", question, docIds });
    try {
      const response = await ask({ question, doc_ids: docIds });
      if (run === runRef.current) setState({ status: "done", response });
    } catch (error) {
      if (run === runRef.current) setState({ status: "error", question, docIds, message: errorMessage(error) });
    }
  }
  async function compareReports(request: CompareRequest) {
    const run = ++compareRun.current;
    setActiveCitation(null);
    setCompareState({ status: "loading", request });
    try {
      const response = await compare(request);
      if (run === compareRun.current) setCompareState({ status: "done", response });
    } catch (error) {
      if (run === compareRun.current) setCompareState({ status: "error", request, message: errorMessage(error) });
    }
  }
  function openEvidence() {
    evidenceTrigger.current = document.activeElement as HTMLElement | null;
    setEvidenceOpen(true);
    requestAnimationFrame(() => evidenceRef.current?.focus());
  }
  function openCitation(citation: Citation) {
    setActiveCitation(citation);
    if (!window.matchMedia("(min-width: 80rem)").matches) openEvidence();
  }
  function closeEvidence() {
    setEvidenceOpen(false);
    evidenceTrigger.current?.focus();
  }
  const state = view === "catch-up" ? catchState : askState;
  const latest = documents?.at(-1);
  const rawCitations = view === "compare"
    ? compareState.status === "done" ? compareState.response.changes.flatMap((change) => [...change.older_citations, ...change.newer_citations]) : []
    : state.status === "done" ? state.response.claims.flatMap((claim) => claim.citations) : [];
  const citations = rawCitations.filter((citation, index, all) => all.findIndex((item) => item.passage_id === citation.passage_id && item.quote === citation.quote) === index);

  return (
    <MotionConfig reducedMotion="user">
      <div className="news-shell story-shell">
        <NewsHeader story onUpload={() => setUploadOpen(true)} />
        <main className="story-main">
          <Link href="/" className="back-link"><ArrowLeft size={14} /> Back to the briefing</Link>
          <div className="story-heading"><p className="news-eyebrow"><span className="status-dot" /> THE STORY ROOM</p><h1>{documents === null ? "Opening the story…" : storyTitle(documents)}</h1><p>Understand the story behind the headlines. Every answer starts with a source.</p><div className="story-meta"><span><FileText size={14} /> {documents?.length ?? 0} indexed reports</span>{latest && <span>Latest report · {formatReportDate(latest.report_date)}</span>}</div></div>
          {documentsError && <div className="story-alert" role="alert">{documentsError} <button onClick={() => { setDocumentsError(null); setDocumentsRequest((n) => n + 1); }}>Retry connection</button></div>}
          {!!documents?.length && <StoryTimeline documents={documents} selectedIds={timelineSelection} onToggleReport={toggleTimelineDocument} comparison={view === "compare"} />}
          <div id="story-tools" className="story-workspace">
            <div className="story-content">
              <nav className="story-tabs" aria-label="Story sections">{VIEWS.map(({ id, label, icon: Icon }) => <button key={id} aria-current={view === id ? "page" : undefined} onClick={() => { setView(id); setActiveCitation(null); }}><Icon size={16} />{label}{view === id && <motion.span className="tab-indicator" layoutId="story-active-tab" transition={{ duration: reduced ? 0 : .22 }} />}</button>)}<button className="evidence-tab xl:hidden" onClick={openEvidence}><BookOpen size={16} /><span className="max-sm:sr-only">Evidence</span></button></nav>
              {view !== "compare" && <details className="source-picker" open>
                <summary><span><FileText size={15} /> Reports in this story</span><span>{selection.length} / {documents?.length ?? 0} selected</span></summary>
                <p>Select the reports for Catch Me Up and Ask Folio.</p>
                <div className="source-actions">
                  <button type="button" disabled={!documents?.length || selection.length === documents.length} onClick={() => setSelectedIds(documents?.map((doc) => doc.doc_id) ?? [])}>Select All</button>
                  <button type="button" disabled={!selection.length} onClick={() => setSelectedIds([])}>Clear</button>
                </div>
                <div className="source-options">{documents?.map((doc) => <label key={doc.doc_id}><input type="checkbox" checked={selection.includes(doc.doc_id)} onChange={() => toggleDocument(doc.doc_id)} /><span><strong>{doc.title}</strong><small>{formatReportDate(doc.report_date)}</small></span><Check size={14} className={selection.includes(doc.doc_id) ? "source-check" : "invisible"} /></label>)}</div>
                {documents?.length === 0 && <p>No indexed reports yet. Upload a dated report to begin.</p>}
                {documents && documents.length > 0 && selection.length === 0 && <p role="status">Select at least one report to continue.</p>}
                {selection.length > MAX_ASK_DOCUMENTS && <p role="alert">Select up to {MAX_ASK_DOCUMENTS} reports per question. Clear or uncheck reports to continue.</p>}
                <button type="button" className="source-add" onClick={() => setUploadOpen(true)}><Plus size={14} /> Add a report</button>
              </details>}
              <AnimatePresence mode="wait" initial={false}><motion.div key={view} initial={{ opacity: 0, y: reduced ? 0 : 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: reduced ? 0 : .16 }} className="story-view" aria-live="polite" aria-busy={view === "compare" ? compareState.status === "loading" : state.status === "loading"}>
                {view === "compare" ? <CompareView documents={documents} selectedIds={comparisonIds} onSelectionChange={setCompareChoices} state={compareState} activeCitation={activeCitation} onOpenCitation={openCitation} onCompare={compareReports} /> : state.status !== "idle" ? <><AnswerView heading={view === "catch-up" ? "The story so far" : undefined} state={state} documents={documents ?? []} activeCitation={activeCitation} onOpenCitation={openCitation} onRetry={(question) => askQuestion(question, view === "catch-up")} />{view === "catch-up" && <div className="catch-refresh"><button className="news-button" disabled={!selection.length || selection.length > MAX_ASK_DOCUMENTS || state.status === "loading"} onClick={() => askQuestion(CATCH_UP_QUESTION, true)}>Update catch-up from selected reports <ArrowRight size={15} /></button></div>}</> : view === "catch-up" ? <section className="catch-intro"><span className="intro-icon"><Sparkles size={24} strokeWidth={1.4} /></span><p className="news-eyebrow">THE CONTEXT YOU CAME FOR</p><h2>Get the story so far.</h2><p>A catch-up grounded in your selected reports: the key events, the different accounts, and the questions still open.</p><button className="news-button news-button-dark" disabled={!selection.length || selection.length > MAX_ASK_DOCUMENTS} onClick={() => askQuestion(CATCH_UP_QUESTION, true)}>Catch me up <ArrowRight size={16} /></button><small><BookOpen size={13} /> Claims link directly to their supporting passages.</small></section> : <section className="catch-intro ask-intro"><span className="intro-icon"><MessageCircle size={24} strokeWidth={1.4} /></span><p className="news-eyebrow">GO A LITTLE DEEPER</p><h2>Your questions. The sources.</h2><p>Ask about a detail, a date, or a claim. Folio answers from the reports you select and shows its evidence.</p><Composer selectedCount={selection.length} onAsk={askQuestion} /></section>}
              </motion.div></AnimatePresence>
              {view === "ask" && askState.status !== "idle" && <div className="story-composer"><Composer compact selectedCount={selection.length} onAsk={askQuestion} /></div>}
            </div>
            <div className="story-evidence"><EvidencePanel ref={evidenceRef} citation={activeCitation} citations={citations} onSelectCitation={setActiveCitation} documents={documents ?? []} open={evidenceOpen} onClose={closeEvidence} /></div>
          </div>
        </main>
        {evidenceOpen && <button tabIndex={-1} aria-label="Close evidence overlay" onClick={closeEvidence} className="fixed inset-0 z-40 bg-[#13203640] backdrop-blur-[1px] xl:hidden" />}
        {uploadOpen && <UploadDialog onUpload={upload} onClose={() => setUploadOpen(false)} />}
      </div>
    </MotionConfig>
  );
}
