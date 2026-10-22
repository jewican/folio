"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, CalendarDays, ExternalLink, FileText } from "lucide-react";
import { formatReportDate, formatShortDate, sourceDomain } from "@/lib/reports";
import type { FolioDocument } from "@/lib/types";

export function StoryTimeline({ documents, onSelectReport }: {
  documents: FolioDocument[];
  onSelectReport: (id: string) => void;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const reduced = useReducedMotion();
  const docs = [...documents].sort((a, b) => a.report_date.localeCompare(b.report_date) || a.doc_id.localeCompare(b.doc_id));
  const active = docs.find((doc) => doc.doc_id === activeId) ?? docs.at(-1);
  if (!active) return null;
  return (
    <section className="report-timeline" aria-labelledby="timeline-heading">
      <div className="timeline-heading"><div><p className="news-eyebrow"><CalendarDays size={12} /> FOLLOW THE REPORTING</p><h2 id="timeline-heading">The story, over time.</h2></div><span>{docs.length} dated {docs.length === 1 ? "report" : "reports"}</span></div>
      <ol className="timeline-track" aria-label="Report publication timeline">
        {docs.map((doc, index) => <li key={doc.doc_id} data-active={active.doc_id === doc.doc_id || undefined}>
          <button type="button" aria-pressed={active.doc_id === doc.doc_id} onClick={() => setActiveId(doc.doc_id)} aria-controls="timeline-report">
            <time dateTime={doc.report_date}>{formatShortDate(doc.report_date)}</time>
            <span className="timeline-node" aria-hidden>{active.doc_id === doc.doc_id && <motion.span layoutId="timeline-selection" transition={{ duration: reduced ? 0 : .22 }} />}</span>
            <span className="timeline-report-title">{doc.title}</span><small>{index === docs.length - 1 ? "Latest indexed report" : sourceDomain(doc.source_url)}</small>
          </button>
        </li>)}
      </ol>
        <motion.div key={active.doc_id} id="timeline-report" className="timeline-detail" initial={{opacity:0, y:reduced ? 0 : 5}} animate={{opacity:1,y:0}} transition={{duration:reduced ? 0 : .15}}>
          <span className="timeline-file-icon"><FileText size={20} strokeWidth={1.5} /></span>
          <div><h3>{active.title}</h3><p><time dateTime={active.report_date}>{formatReportDate(active.report_date)}</time><span>·</span>{active.passage_count} indexed {active.passage_count === 1 ? "passage" : "passages"}</p>{active.source_url && <a href={active.source_url} target="_blank" rel="noreferrer">{sourceDomain(active.source_url)} <ExternalLink size={11} /></a>}</div>
          <button type="button" className="timeline-use" onClick={() => onSelectReport(active.doc_id)}>Use this report <ArrowRight size={13} /></button>
        </motion.div>
      <p className="timeline-caption">Dates reflect report publication, not necessarily when the events occurred.</p>
    </section>
  );
}
