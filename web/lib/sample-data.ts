// Sample responses for building the UI before the backend is ready.
// The story is fictional; W4's fixtures replace it once they land in fixtures/.

import type {
  AskRequest,
  AskResponse,
  Change,
  Citation,
  Claim,
  CompareRequest,
  CompareResponse,
  FolioDocument,
  Passage,
} from "@/lib/types";

const OLDER_URL = "https://example.org/reports/river-2026-10-20";
const NEWER_URL = "https://example.org/reports/river-2026-10-21";

// Sorted like GET /documents: report_date ascending, then doc_id.
export const sampleDocuments: FolioDocument[] = [
  {
    doc_id: "doc_older",
    title: "River response — first report",
    filename: "river-2026-10-20.pdf",
    media_type: "application/pdf",
    report_date: "2026-10-20",
    source_url: OLDER_URL,
    uploaded_at: "2026-10-22T03:05:00Z",
    passage_count: 4,
    status: "ready",
  },
  {
    doc_id: "doc_transit",
    title: "Transit advisory — northern district",
    filename: "transit-advisory-2026-10-20.txt",
    media_type: "text/plain",
    report_date: "2026-10-20",
    source_url: null,
    uploaded_at: "2026-10-22T03:06:00Z",
    passage_count: 2,
    status: "ready",
  },
  {
    doc_id: "doc_newer",
    title: "River response — update",
    filename: "river-2026-10-21.pdf",
    media_type: "application/pdf",
    report_date: "2026-10-21",
    source_url: NEWER_URL,
    uploaded_at: "2026-10-22T03:07:00Z",
    passage_count: 4,
    status: "ready",
  },
];

const passage = (
  passage_id: string,
  doc_id: string,
  page: number | null,
  text: string,
): Passage => {
  const doc = sampleDocuments.find((d) => d.doc_id === doc_id)!;
  const { title, report_date, source_url } = doc;
  return { passage_id, doc_id, title, report_date, source_url, page, text };
};

const samplePassages: Passage[] = [
  passage(
    "pas_older_001",
    "doc_older",
    1,
    "Heavy rain pushed the Alder River over its banks before dawn on October 19, flooding low-lying streets across the northern district. The regional water authority said the river peaked at 4.8 metres, more than a metre above flood stage.",
  ),
  passage(
    "pas_older_002",
    "doc_older",
    1,
    "Emergency services evacuated about 1,200 residents overnight, most of them from homes along Mill Road and the lower Eastgate estate. No injuries had been confirmed as of the morning of October 20.",
  ),
  passage(
    "pas_older_003",
    "doc_older",
    2,
    "Ten shelters are open in the northern district. The Eastgate community centre is also accepting pets, and the council has asked residents with spare rooms to register with the volunteer housing line.",
  ),
  passage(
    "pas_older_004",
    "doc_older",
    2,
    "The Route 9 bridge remains closed while engineers inspect its supports. Officials said they could not yet say when it would reopen.",
  ),
  passage(
    "pas_transit_001",
    "doc_transit",
    null,
    "Bus routes 4 and 11 are diverted around the northern district until further notice. Replacement shuttles run every 20 minutes between Northgate station and the Eastgate community centre.",
  ),
  passage(
    "pas_transit_002",
    "doc_transit",
    null,
    "Rail services between Northgate and Central are running at reduced frequency because of water on the line near Alder Junction.",
  ),
  passage(
    "pas_newer_001",
    "doc_newer",
    1,
    "The Alder River fell by 40 centimetres overnight, according to the regional water authority, although it remains above flood stage at several gauges.",
  ),
  passage(
    "pas_newer_002",
    "doc_newer",
    1,
    "Twelve shelters are open in the northern district after two schools were converted on October 20. Officials said the Eastgate centre is close to capacity.",
  ),
  passage(
    "pas_newer_003",
    "doc_newer",
    2,
    "The evacuation count was revised to about 1,450 residents after door-to-door checks on Mill Road and Station Street.",
  ),
  passage(
    "pas_newer_004",
    "doc_newer",
    2,
    "Engineers cleared the Route 9 bridge for one lane of traffic from 6 a.m. on October 22. Heavy vehicles remain barred until a second inspection.",
  ),
];

export const findSamplePassage = (passageId: string) =>
  samplePassages.find((p) => p.passage_id === passageId);

// Builds a citation the way the contract requires: the quote must be an exact
// substring of the stored passage, so a typo here fails loudly in development.
function cite(passageId: string, quote: string): Citation {
  const stored = findSamplePassage(passageId);
  if (!stored || !stored.text.includes(quote)) {
    throw new Error(`Sample citation ${passageId} does not quote its passage.`);
  }
  const { passage_id, doc_id, title, report_date, source_url, page } = stored;
  return { passage_id, doc_id, title, report_date, source_url, page, quote };
}

type SampleAnswer = {
  question: string;
  keywords: string[];
  claims: Claim[];
};

const sampleAnswers: SampleAnswer[] = [
  {
    question: "How many shelters are open?",
    keywords: ["shelter"],
    claims: [
      {
        text: "The October 20 report counted ten shelters open in the northern district.",
        citations: [
          cite("pas_older_003", "Ten shelters are open in the northern district."),
        ],
      },
      {
        text: "The October 21 update counted twelve, after two schools were converted into shelters.",
        citations: [
          cite(
            "pas_newer_002",
            "Twelve shelters are open in the northern district after two schools were converted",
          ),
        ],
      },
    ],
  },
  {
    question: "How many residents were evacuated?",
    keywords: ["evacuat", "resident"],
    claims: [
      {
        text: "The first report said about 1,200 residents were evacuated overnight.",
        citations: [
          cite("pas_older_002", "Emergency services evacuated about 1,200 residents overnight"),
        ],
      },
      {
        text: "The October 21 update revised the figure to about 1,450 after door-to-door checks.",
        citations: [
          cite(
            "pas_newer_003",
            "The evacuation count was revised to about 1,450 residents after door-to-door checks",
          ),
        ],
      },
    ],
  },
  {
    question: "Is the Route 9 bridge open?",
    keywords: ["bridge", "route 9"],
    claims: [
      {
        text: "On October 20 the Route 9 bridge was closed while engineers inspected its supports.",
        citations: [
          cite("pas_older_004", "The Route 9 bridge remains closed while engineers inspect its supports."),
        ],
      },
      {
        text: "By the October 21 update it was cleared for one lane of traffic, with heavy vehicles still barred.",
        citations: [
          cite("pas_newer_004", "Engineers cleared the Route 9 bridge for one lane of traffic"),
          cite("pas_newer_004", "Heavy vehicles remain barred until a second inspection."),
        ],
      },
    ],
  },
  {
    question: "How is public transport affected?",
    keywords: ["bus", "rail", "train", "transit", "transport"],
    claims: [
      {
        text: "Bus routes 4 and 11 are diverted around the northern district, with replacement shuttles every 20 minutes.",
        citations: [
          cite("pas_transit_001", "Bus routes 4 and 11 are diverted around the northern district"),
          cite("pas_transit_001", "Replacement shuttles run every 20 minutes"),
        ],
      },
      {
        text: "Rail services between Northgate and Central are running at reduced frequency.",
        citations: [
          cite(
            "pas_transit_002",
            "Rail services between Northgate and Central are running at reduced frequency",
          ),
        ],
      },
    ],
  },
];

export const sampleQuestions = sampleAnswers.map((a) => a.question);

/**
 * Answers like POST /ask would, minus `meta`. Claims citing a report outside
 * the selection are dropped, so an earlier selection never sees later evidence.
 */
export function answerSampleQuestion({
  question,
  doc_ids,
}: AskRequest): Omit<AskResponse, "meta"> {
  const normalized = question.toLowerCase();
  const match = sampleAnswers.find((a) =>
    a.keywords.some((keyword) => normalized.includes(keyword)),
  );
  const claims = (match?.claims ?? []).filter((claim) =>
    claim.citations.every((c) => doc_ids.includes(c.doc_id)),
  );

  if (claims.length === 0) {
    return {
      question,
      doc_ids,
      status: "insufficient_evidence",
      answer: match
        ? "The selected reports don't contain a passage that answers this question."
        : "Sample mode only has answers for the suggested questions, so there is no supported answer to show.",
      claims: [],
    };
  }

  return {
    question,
    doc_ids,
    status: "answered",
    answer: claims.map((c) => c.text).join(" "),
    claims,
  };
}

type SampleChange = { keywords: string[]; change: Change };

// POST /compare for doc_older -> doc_newer. Each item follows the contract's
// evidence rules: `updated` and `unresolved` cite both versions, `added` cites
// only the newer one and asserts no earlier state.
const sampleChanges: SampleChange[] = [
  {
    keywords: ["shelter"],
    change: {
      kind: "updated",
      summary: "The number of open shelters in the northern district rose from ten to twelve.",
      before: "Ten shelters were open in the northern district.",
      after: "Twelve shelters were open after two schools were converted on October 20.",
      older_citations: [
        cite("pas_older_003", "Ten shelters are open in the northern district."),
      ],
      newer_citations: [
        cite(
          "pas_newer_002",
          "Twelve shelters are open in the northern district after two schools were converted on October 20.",
        ),
      ],
    },
  },
  {
    keywords: ["evacuat", "resident"],
    change: {
      kind: "updated",
      summary: "The evacuation count was revised upward after door-to-door checks.",
      before: "About 1,200 residents were evacuated overnight.",
      after: "About 1,450 residents, after checks on Mill Road and Station Street.",
      older_citations: [
        cite("pas_older_002", "Emergency services evacuated about 1,200 residents overnight"),
      ],
      newer_citations: [
        cite(
          "pas_newer_003",
          "The evacuation count was revised to about 1,450 residents after door-to-door checks on Mill Road and Station Street.",
        ),
      ],
    },
  },
  {
    keywords: ["bridge", "route 9", "road"],
    change: {
      kind: "updated",
      summary: "The Route 9 bridge went from fully closed to one lane open.",
      before: "Closed while engineers inspected its supports, with no reopening date.",
      after: "One lane open from 6 a.m. on October 22; heavy vehicles still barred.",
      older_citations: [
        cite(
          "pas_older_004",
          "The Route 9 bridge remains closed while engineers inspect its supports.",
        ),
      ],
      newer_citations: [
        cite(
          "pas_newer_004",
          "Engineers cleared the Route 9 bridge for one lane of traffic from 6 a.m. on October 22.",
        ),
      ],
    },
  },
  {
    keywords: ["river", "level", "flood"],
    change: {
      kind: "unresolved",
      summary:
        "Both reports describe the river level, but one gives a peak height and the other an overnight fall, so the current level can't be worked out from them.",
      before: "The river peaked at 4.8 metres, more than a metre above flood stage.",
      after: "The river fell by 40 centimetres overnight and remains above flood stage at several gauges.",
      older_citations: [
        cite(
          "pas_older_001",
          "the river peaked at 4.8 metres, more than a metre above flood stage",
        ),
      ],
      newer_citations: [
        cite(
          "pas_newer_001",
          "The Alder River fell by 40 centimetres overnight",
        ),
      ],
    },
  },
  {
    keywords: ["shelter", "capacity", "eastgate"],
    change: {
      kind: "added",
      summary: "The newer report says the Eastgate centre is close to capacity.",
      before: null,
      after: "Officials said the Eastgate centre is close to capacity.",
      older_citations: [],
      newer_citations: [
        cite("pas_newer_002", "Officials said the Eastgate centre is close to capacity."),
      ],
    },
  },
];

export const DEFAULT_COMPARE_QUESTION = "What changed between these reports?";

/**
 * Compares like POST /compare would, minus `meta`. Only doc_older -> doc_newer
 * has sample evidence; a question that names a topic narrows the changes.
 */
export function compareSampleReports({
  older_doc_id,
  newer_doc_id,
  question,
}: CompareRequest): Omit<CompareResponse, "meta"> {
  const asked = question ?? DEFAULT_COMPARE_QUESTION;
  const base = { older_doc_id, newer_doc_id, question: asked };

  if (older_doc_id !== "doc_older" || newer_doc_id !== "doc_newer") {
    return {
      ...base,
      status: "insufficient_evidence",
      summary:
        "Sample mode only has comparison evidence for the October 20 first report and the October 21 update, so no supported changes can be shown for this pair.",
      changes: [],
    };
  }

  const normalized = asked.toLowerCase();
  const matching = sampleChanges.filter((c) =>
    c.keywords.some((keyword) => normalized.includes(keyword)),
  );
  const changes = (matching.length > 0 ? matching : sampleChanges).map(
    (c) => c.change,
  );

  return {
    ...base,
    status: "compared",
    summary: changes.map((c) => c.summary).join(" "),
    changes,
  };
}
