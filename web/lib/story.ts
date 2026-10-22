import type { FolioDocument } from "@/lib/types";

// The API has one document collection, not a story catalog. Never synthesize
// extra stories or count reports as independent developing stories.
export function storyTitle(documents: FolioDocument[]) {
  const isDuterte = documents.some((doc) => /duterte|impeachment/i.test(doc.title));
  return isDuterte ? "The Sara Duterte impeachment" : documents[0]?.title ?? "Your story starts with a source.";
}
