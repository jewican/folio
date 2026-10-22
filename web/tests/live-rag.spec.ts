// Real production UI + real FastAPI + W2 + configured Gemini. No intercepted requests.
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { AskResponse, CompareResponse, FolioDocument, Passage } from "../lib/types";

const root = resolve(__dirname, "../..");
const manifest = JSON.parse(readFileSync(resolve(root, "corpus/manifest.json"), "utf8")) as {
  documents: { doc_id: string; file: string; title: string; report_date: string; source_url: string }[];
};
const source = manifest.documents.find((doc) => doc.doc_id === "sc-press-briefer-2026-08-05")!;

async function upload(page: Page, document: typeof source) {
  await page.getByRole("button", { name: "Upload report", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator('input[type="file"]').setInputFiles(resolve(root, "corpus", document.file));
  await dialog.getByLabel("Title", { exact: true }).fill(document.title);
  await dialog.getByLabel("Report date", { exact: true }).fill(document.report_date);
  await dialog.getByLabel(/Source link/).fill(document.source_url);
  const saved = page.waitForResponse((r) => r.url().endsWith("/documents") && r.request().method() === "POST");
  await dialog.getByRole("button", { name: "Add report", exact: true }).click();
  const response = await saved;
  expect(response.status()).toBe(201);
  const body = await response.json() as FolioDocument;
  expect(body.title).toBe(document.title);
  expect(body.report_date).toBe(document.report_date);
  expect(body.source_url).toBe(document.source_url);
  expect(body.doc_id).not.toBe(document.doc_id);
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText(document.title, { exact: true }).first()).toBeVisible();
  return body;
}

async function askQuestion(page: Page, question: string) {
  await page.getByRole("textbox", { name: "Ask a question about the selected reports" }).fill(question);
  const answer = page.waitForResponse((r) => r.url().endsWith("/ask") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  return answer;
}

test("real uploads persist and empty evidence stays explicit without sample data", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Connected to backend", { exact: true })).toBeVisible();
  await expect(page.getByText("No reports yet. Upload a dated report to start asking questions.")).toBeVisible();
  const document = await upload(page, source);
  expect(document.passage_count).toBe(1);
  await page.reload();
  await expect(page.getByText(source.title, { exact: true }).first()).toBeVisible();
  const response = await askQuestion(page, "FolioUnmatchedLexicalProbe926713");
  expect(response.status()).toBe(200);
  const answer = await response.json() as AskResponse;
  expect(answer.doc_ids).toEqual([document.doc_id]);
  expect(answer.status).toBe("insufficient_evidence");
  expect(answer.claims).toEqual([]);
  await expect(page.getByText(answer.answer, { exact: true })).toBeVisible();
  await expect(page.locator('[data-slot="web-search-citation"]')).toHaveCount(0);
  await expect(page.getByText(/Sample (data|response)/)).toHaveCount(0);
  await expect(page.getByText(/River response/)).toHaveCount(0);
});

test("real Gemini answer opens canonical source passages on desktop and mobile", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByText("Connected to backend", { exact: true })).toBeVisible();
  await upload(page, source);
  const response = await askQuestion(page,
    "According to the August 5 press briefer, why did the Supreme Court dismiss the impeachment petitions?");
  const body = await response.json();
  await testInfo.attach("real-api-response", { body: JSON.stringify(body, null, 2), contentType: "application/json" });
  if (!response.ok()) {
    await expect(page.locator(".folio-answer").getByRole("alert")).toContainText(body.detail.message);
    await expect(page.locator('[data-slot="web-search-citation"]')).toHaveCount(0);
    throw new Error(`Live generation blocked: HTTP ${response.status()}: ${body.detail.message}`);
  }
  const answer = body as AskResponse;
  expect(answer.status).toBe("answered");
  expect(answer.meta.cached).toBe(false);
  expect(answer.claims.length).toBeGreaterThan(0);
  await expect(page.getByText(answer.claims[0].text, { exact: false }).first()).toBeVisible();
  const citation = answer.claims[0].citations[0];
  const chip = page.getByRole("button", { name: `${citation.title}, Aug 5`, exact: true }).first();
  const evidenceResponse = page.waitForResponse((r) => r.url().includes(`/passages/${citation.passage_id}`));
  await chip.click();
  const passage = await (await evidenceResponse).json() as Passage;
  for (const key of ["passage_id", "doc_id", "title", "report_date", "source_url", "page"] as const) {
    expect(passage[key]).toBe(citation[key]);
  }
  expect(passage.text).toContain(citation.quote);
  const panel = page.getByRole("complementary", { name: "Evidence", exact: true });
  await expect(panel).toBeVisible();
  await expect(panel.locator("mark")).toHaveText(citation.quote);
  await expect(panel.getByRole("link")).toHaveAttribute("href", citation.source_url!);
  await expect(panel.getByText("sc-press-briefer.txt", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 700, height: 900 });
  await chip.click();
  await expect(panel).toBeVisible();
  await expect(panel.locator("mark")).toHaveText(citation.quote);
  await page.keyboard.press("Escape");
  await expect(panel).not.toBeVisible();
});


test("backend upload validation and connection errors stay visible", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByText("Connected to backend", { exact: true })).toBeVisible();
  await upload(page, source);
  await page.getByRole("button", { name: "Upload report", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "empty.txt", mimeType: "text/plain", buffer: Buffer.from(" \n"),
  });
  await dialog.getByLabel("Title", { exact: true }).fill("Unreadable report");
  await dialog.getByLabel("Report date", { exact: true }).fill("2026-08-05");
  const rejected = page.waitForResponse((r) => r.url().endsWith("/documents") && r.request().method() === "POST");
  await dialog.getByRole("button", { name: "Add report", exact: true }).click();
  expect((await rejected).status()).toBe(422);
  await expect(dialog.getByRole("alert")).toContainText(/no text|readable text/);
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await context.setOffline(true);
  await page.getByRole("textbox", { name: "Ask a question about the selected reports" }).fill("What does the report say?");
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(page.locator(".folio-answer").getByRole("alert")).toContainText("Can't reach the Folio backend");
  await expect(page.locator('[data-slot="web-search-citation"]')).toHaveCount(0);
});

test("held-out upload produces a real comparison with inspectable evidence on both sides", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByText("Connected to backend", { exact: true })).toBeVisible();
  const initial = await page.request.get("http://127.0.0.1:8000/documents");
  expect((await initial.json()).documents.every((d: FolioDocument) => d.report_date !== "2026-10-13")).toBe(true);
  const olderSource = manifest.documents.find((d) => d.doc_id === "articles-2026")!;
  const newerSource = manifest.documents.find((d) => d.doc_id === "house-press-10322-2026-10-13")!;
  const older = await upload(page, olderSource);
  const newer = await upload(page, newerSource);
  await page.getByRole("button", { name: "Compare versions", exact: true }).click();
  await page.getByLabel("Older report").selectOption(older.doc_id);
  await page.getByLabel("Newer report").selectOption(newer.doc_id);
  await page.getByRole("textbox", { name: "Question (optional)" }).fill(
    "Compare the original Articles with the October 13 update: which articles would the prosecution continue pursuing, and which would it cease pursuing?");
  const pending = page.waitForResponse((r) => r.url().endsWith("/compare") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Compare reports", exact: true }).click();
  const response = await pending;
  const result = await response.json() as CompareResponse;
  await testInfo.attach("real-comparison-response", { body: JSON.stringify(result, null, 2), contentType: "application/json" });
  expect(response.status()).toBe(200);
  expect(result.status).toBe("compared");
  expect(result.meta.cached).toBe(false);
  const change = result.changes.find((c) => c.kind === "updated")!;
  expect(change).toBeTruthy();
  expect(change.older_citations.length).toBeGreaterThan(0);
  expect(change.newer_citations.length).toBeGreaterThan(0);
  await expect(page.getByText(result.summary, { exact: true }).first()).toBeVisible();
  for (const [citation, date, docId] of [
    [change.older_citations[0], "May 11", older.doc_id],
    [change.newer_citations[0], "Oct 13", newer.doc_id],
  ] as const) {
    expect(citation.doc_id).toBe(docId);
    const evidenceResponse = page.waitForResponse((r) => r.url().endsWith(`/passages/${citation.passage_id}`));
    await page.getByRole("button", { name: `${citation.title}, ${date}`, exact: true }).first().click();
    const passage = await (await evidenceResponse).json() as Passage;
    expect(passage.doc_id).toBe(docId);
    expect(passage.text).toContain(citation.quote);
    const panel = page.getByRole("complementary", { name: "Evidence", exact: true });
    await expect(panel.locator("mark")).toHaveText(citation.quote);
    await expect(panel.getByRole("link")).toHaveAttribute("href", citation.source_url!);
  }
  await page.screenshot({ path: testInfo.outputPath("comparison-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 700, height: 900 });
  await expect(page.getByRole("complementary", { name: "Evidence", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("comparison-mobile.png"), fullPage: true });
});
