// Real production UI + real FastAPI + W2 + configured Gemini. No intercepted requests.
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { AskResponse, FolioDocument, Passage } from "../lib/types";

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
