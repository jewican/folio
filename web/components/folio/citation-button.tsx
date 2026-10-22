"use client";

import { ArrowUpRight, Quote } from "lucide-react";
import { citationLabel, sourceDomain } from "@/lib/reports";
import type { Citation } from "@/lib/types";

export function CitationButton({ citation, active, onOpen }: {
  citation: Citation;
  active?: boolean;
  onOpen: (citation: Citation) => void;
}) {
  return (
    <button type="button" className="citation-button" data-active={active || undefined}
      aria-label={`Read evidence: ${citation.title}, ${citationLabel(citation)}`}
      aria-controls="evidence-panel" title={citation.title} onClick={() => onOpen(citation)}>
      <Quote size={12} aria-hidden /><span>{sourceDomain(citation.source_url)}</span>
      <time dateTime={citation.report_date}>{citationLabel(citation)}</time><ArrowUpRight size={12} aria-hidden />
    </button>
  );
}
