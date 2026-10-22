"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ArrowDown, ArrowRight, ArrowUpRight, BookOpen, FileText, Layers3, Plus } from "lucide-react";
import { NewsHeader } from "@/components/folio/news-header";
import { UploadDialog } from "@/components/folio/upload-dialog";
import { errorMessage, listDocuments, uploadDocument, type UploadRequest } from "@/lib/api";
import { formatReportDate, sourceDomain } from "@/lib/reports";
import { storyTitle } from "@/lib/story";
import type { FolioDocument } from "@/lib/types";

export function NewsHome() {
  const reduced = useReducedMotion();
  const [documents, setDocuments] = useState<FolioDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [uploadOpen, setUploadOpen] = useState(false);
  useEffect(() => {
    let cancelled = false;
    listDocuments().then((docs) => { if (!cancelled) { setDocuments(docs); setError(null); } }, (reason) => { if (!cancelled) setError(errorMessage(reason)); });
    return () => { cancelled = true; };
  }, [attempt]);
  async function upload(input: UploadRequest) {
    const document = await uploadDocument(input);
    setDocuments((current) => [...(current ?? []), document].sort((a, b) => a.report_date.localeCompare(b.report_date) || a.doc_id.localeCompare(b.doc_id)));
    setError(null);
    setUploadOpen(false);
  }
  const latest = documents?.at(-1);
  return (
    <div className="news-shell">
      <NewsHeader onUpload={() => setUploadOpen(true)} />
      <main id="main-content" className="news-main">
        <motion.section className="home-intro" initial={{ opacity: 0, y: reduced ? 0 : 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : .4 }}>
          <div><p className="news-eyebrow"><span className="status-dot" /> THE FOLIO BRIEFING</p><h1>A little context.<br />A clearer picture<span>.</span></h1><p className="intro-copy">Pick up the story. Understand what changed.<br className="max-sm:hidden" /> Go straight to the evidence.</p></div>
          <div className="intro-note"><Layers3 size={23} strokeWidth={1.3} /><p>News moves fast.<br /><strong>Context stays with you.</strong></p><a href="#stories" aria-label="Browse the stories"><ArrowDown size={20} /></a></div>
        </motion.section>
        <section id="stories" className="story-list">
          <div className="section-heading"><h2>Your catch-up starts here</h2><span>{documents === null ? "YOUR SOURCE COLLECTION" : `${documents.length ? "01 STORY" : "NO STORIES YET"} / ${String(documents.length).padStart(2, "0")} REPORTS`}</span></div>
          {error ? <div role="alert" className="news-empty"><BookOpen size={28} /><h3>Your reports are a connection away.</h3><p>{error}</p><button className="news-button" onClick={() => { setError(null); setAttempt((n) => n + 1); }}>Retry connection</button></div> : documents === null ? <div className="news-empty" role="status"><Layers3 className="animate-pulse" size={28} /><p>Opening your source collection…</p></div> : documents.length ? (
            <div className="home-grid">
              <Link href="/story" className="lead-story">
                <div className="story-art" aria-hidden="true"><div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" /><span className="art-index">F / 01</span><div className="art-paper paper-back" /><div className="art-paper paper-front"><span>THE STORY SO FAR</span><i /><i /><i /><strong>F.</strong></div><span className="art-caption">FOLLOW THE EVIDENCE</span></div>
                <div className="lead-story-copy"><p className="news-eyebrow"><span className="status-dot" /> IN YOUR COLLECTION</p><h3>{storyTitle(documents)}</h3><p>Key events, changing accounts, and the evidence behind them.</p><div className="story-feature-tags"><span>Catch me up</span><span>What changed</span><span>Ask Folio</span></div><div className="story-card-footer"><span>{documents.length} {documents.length === 1 ? "report" : "reports"} · Latest {formatReportDate(latest!.report_date)}</span><span className="round-arrow"><ArrowUpRight size={21} /></span></div></div>
              </Link>
              <aside className="briefing-note"><span className="note-number">01 / THE APPROACH</span><BookOpen size={32} strokeWidth={1.2} /><h3>Every story has<br />a paper trail.</h3><p>Folio connects the dots across dated reports. Every generated claim comes with a passage you can open and read.</p><div className="note-rule" /><span>YOUR QUESTIONS.<br />THE ORIGINAL SOURCES.</span></aside>
            </div>
          ) : <div className="news-empty"><BookOpen size={30} /><h3>Your story starts with a source.</h3><p>Upload a dated report to create your first story. Only indexed reports appear here.</p><button className="news-button news-button-dark" onClick={() => setUploadOpen(true)}><Plus size={16} /> Upload your first report</button></div>}
        </section>
        {!!documents?.length && <section className="reports-section"><div className="section-heading"><h2>Inside the story</h2><span>THE SOURCE DOCUMENTS</span></div><div className="report-card-grid">{documents.map((doc, i) => <Link href="/story" className="report-card" key={doc.doc_id}><div className="report-card-top"><FileText size={20} strokeWidth={1.4} /><span>REPORT {String(i + 1).padStart(2, "0")}</span><ArrowUpRight size={17} /></div><h3>{doc.title}</h3><span className="report-card-attribution"><span className="status-dot" />{sourceDomain(doc.source_url)}</span><p>{formatReportDate(doc.report_date)} · {doc.passage_count} {doc.passage_count === 1 ? "passage" : "passages"}</p><span className="report-card-link">Explore in story room <ArrowRight size={14} /></span></Link>)}</div></section>}
        <footer className="news-footer"><span className="footer-brand">folio.</span><span>A clearer picture, one source at a time.</span><span>BUILT ON EVIDENCE</span></footer>
      </main>
      {uploadOpen && <UploadDialog onUpload={upload} onClose={() => setUploadOpen(false)} />}
    </div>
  );
}
