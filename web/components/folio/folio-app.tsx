"use client";

import { useEffect, useRef, useState } from "react";
import { MotionConfig } from "motion/react";
import { BookOpen, ChevronRight, Menu } from "lucide-react";
import { AnswerView, AskIntro, Composer, type AskState } from "@/components/folio/ask-view";
import { CompareView, type CompareState } from "@/components/folio/compare-view";
import {
  DocumentSidebar,
  VIEWS,
  type View,
} from "@/components/folio/document-sidebar";
import { EvidencePanel } from "@/components/folio/evidence-panel";
import { UploadDialog } from "@/components/folio/upload-dialog";
import {
  MAX_ASK_DOCUMENTS,
  USING_SAMPLE_DATA,
  ask,
  compare,
  errorMessage,
  listDocuments,
  uploadDocument,
  type UploadRequest,
} from "@/lib/api";
import type { Citation, CompareRequest, FolioDocument } from "@/lib/types";

// Matches Tailwind's xl breakpoint, where the evidence panel becomes a column.
const EVIDENCE_COLUMN_QUERY = "(min-width: 80rem)";

export function FolioApp() {
  const [documents, setDocuments] = useState<FolioDocument[] | null>(null);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [documentsRequest, setDocumentsRequest] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [view, setView] = useState<View>("ask");
  const [askState, setAskState] = useState<AskState>({ status: "idle" });
  const [compareState, setCompareState] = useState<CompareState>({ status: "idle" });
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [newIds, setNewIds] = useState<string[]>([]);

  const askRun = useRef(0);
  const compareRun = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const evidenceRef = useRef<HTMLElement>(null);
  const evidenceTrigger = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDocuments().then(
      (docs) => {
        if (cancelled) return;
        setDocuments(docs);
        setSelectedIds(docs.slice(0, MAX_ASK_DOCUMENTS).map((d) => d.doc_id));
      },
      (error) => {
        if (!cancelled) setDocumentsError(errorMessage(error));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [documentsRequest]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (evidenceOpen) {
        setEvidenceOpen(false);
        evidenceTrigger.current?.focus();
      } else if (navOpen) {
        setNavOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [evidenceOpen, navOpen]);

  // Keep the selection in report-date order, as the backend lists documents.
  const selection =
    documents?.filter((d) => selectedIds.includes(d.doc_id)).map((d) => d.doc_id) ?? [];

  function toggleDocument(docId: string) {
    setSelectedIds((current) =>
      current.includes(docId)
        ? current.filter((id) => id !== docId)
        : current.length >= MAX_ASK_DOCUMENTS
          ? current
          : [...current, docId],
    );
  }

  async function upload(request: UploadRequest) {
    const doc = await uploadDocument(request);
    // Keep GET /documents order: report_date, then doc_id.
    setDocuments((current) =>
      [...(current ?? []), doc].sort(
        (a, b) =>
          a.report_date.localeCompare(b.report_date) || a.doc_id.localeCompare(b.doc_id),
      ),
    );
    setSelectedIds((current) =>
      current.length < MAX_ASK_DOCUMENTS ? [...current, doc.doc_id] : current,
    );
    setNewIds((current) => [...current, doc.doc_id]);
    setUploadOpen(false);
  }

  async function askQuestion(question: string) {
    const docIds = selection;
    if (docIds.length === 0) return;
    // A newer question supersedes any request still in flight.
    const run = ++askRun.current;
    setView("ask");
    setActiveCitation(null);
    setAskState({ status: "loading", question, docIds });
    scrollRef.current?.scrollTo({ top: 0 });
    try {
      const response = await ask({ question, doc_ids: docIds });
      if (run === askRun.current) setAskState({ status: "done", response });
    } catch (error) {
      if (run === askRun.current) {
        setAskState({ status: "error", question, docIds, message: errorMessage(error) });
      }
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
      if (run === compareRun.current) {
        setCompareState({ status: "error", request, message: errorMessage(error) });
      }
    }
  }

  // Below xl the panel is an overlay: move focus in, and back out on close.
  function openEvidence() {
    evidenceTrigger.current = document.activeElement as HTMLElement | null;
    setEvidenceOpen(true);
    requestAnimationFrame(() => evidenceRef.current?.focus());
  }

  function openCitation(citation: Citation) {
    setActiveCitation(citation);
    if (!window.matchMedia(EVIDENCE_COLUMN_QUERY).matches) openEvidence();
  }

  function closeEvidence() {
    setEvidenceOpen(false);
    evidenceTrigger.current?.focus();
  }

  const showFollowUp = view === "ask" && askState.status !== "idle";

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex h-dvh overflow-hidden bg-background text-foreground">
        {navOpen && (
          <button
            type="button"
            tabIndex={-1}
            aria-label="Close reports"
            onClick={() => setNavOpen(false)}
            className="fixed inset-0 z-30 bg-[#13203670] backdrop-blur-[2px] md:hidden"
          />
        )}

        <DocumentSidebar
          documents={documents}
          documentsError={documentsError}
          onRetryDocuments={() => {
            setDocumentsError(null);
            setDocumentsRequest((n) => n + 1);
          }}
          selectedIds={selection}
          onToggleDocument={toggleDocument}
          view={view}
          onViewChange={(next) => {
            setView(next);
            setNavOpen(false);
          }}
          open={navOpen}
          onClose={() => setNavOpen(false)}
          onUploadClick={() => {
            setNavOpen(false);
            setUploadOpen(true);
          }}
          newIds={newIds}
        />

        {uploadOpen && (
          <UploadDialog onUpload={upload} onClose={() => setUploadOpen(false)} />
        )}

        <main className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-[#e4e5e4] bg-[#f8f8f6cc] px-3 backdrop-blur-md sm:h-16 sm:px-8">
            <div className="flex min-w-0 items-center gap-1.5">
              <button
                type="button"
                onClick={() => setNavOpen(true)}
                aria-label="Open reports"
                aria-controls="document-sidebar"
                aria-expanded={navOpen}
                className="grid size-9 shrink-0 place-items-center rounded-md text-[#73859b] hover:bg-[#dde3eb60] md:hidden"
              >
                <Menu size={20} />
              </button>
              <p className="flex min-w-0 items-center gap-2 text-[12px] text-[#9b9fa5]">
                <span className="max-sm:hidden">Story workspace</span>
                <ChevronRight size={13} className="shrink-0 max-sm:hidden" />
                <strong className="truncate font-medium text-[#525960]">
                  {VIEWS.find((v) => v.id === view)?.label}
                </strong>
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {USING_SAMPLE_DATA && (
                <span
                  title="Responses come from built-in sample data, not the backend"
                  className="inline-flex items-center gap-1.5 rounded-full border border-[#eadfc8] bg-[#fbf7ee] px-2.5 py-1 text-[11px] font-medium text-[#8f7343]"
                >
                  <span className="size-1.5 rounded-full bg-[#d3a75c]" />
                  Sample data
                </span>
              )}
              <button
                type="button"
                onClick={openEvidence}
                aria-controls="evidence-panel"
                aria-expanded={evidenceOpen}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#d9dcdf] bg-white px-2.5 py-1.5 text-[12px] font-medium text-[#3e4856] shadow-[0_1px_2px_#00000005] hover:bg-[#eef3fa] xl:hidden"
              >
                <BookOpen size={15} />
                <span className="max-sm:sr-only">Evidence</span>
              </button>
            </div>
          </header>

          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
            {view === "compare" ? (
              <CompareView
                documents={documents}
                state={compareState}
                activeCitation={activeCitation}
                onOpenCitation={openCitation}
                onCompare={compareReports}
              />
            ) : askState.status === "idle" ? (
              <AskIntro selectedCount={selection.length} onAsk={askQuestion} />
            ) : (
              <AnswerView
                state={askState}
                documents={documents ?? []}
                activeCitation={activeCitation}
                onOpenCitation={openCitation}
                onRetry={askQuestion}
              />
            )}
          </div>

          {showFollowUp && (
            <div className="shrink-0 border-t border-[#e4e5e4] bg-[#f5f5f3]/95 px-3 py-3 backdrop-blur sm:px-8">
              <div className="mx-auto max-w-[656px]">
                <Composer compact selectedCount={selection.length} onAsk={askQuestion} />
              </div>
            </div>
          )}
        </main>

        {evidenceOpen && (
          <button
            type="button"
            tabIndex={-1}
            aria-label="Close evidence"
            onClick={closeEvidence}
            className="fixed inset-0 z-40 bg-[#13203640] backdrop-blur-[1px] xl:hidden"
          />
        )}

        <EvidencePanel
          ref={evidenceRef}
          citation={activeCitation}
          documents={documents ?? []}
          open={evidenceOpen}
          onClose={closeEvidence}
        />
      </div>
    </MotionConfig>
  );
}
