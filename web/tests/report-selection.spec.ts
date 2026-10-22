import { test, expect } from "@playwright/test";

const documents = [1, 2, 3, 4].map((number) => ({
  doc_id: `report-${number}`,
  title: `Story report ${number}`,
  filename: `report-${number}.txt`,
  media_type: "text/plain",
  report_date: `2026-10-2${number}`,
  source_url: null,
  uploaded_at: "2026-10-24T00:00:00Z",
  passage_count: 1,
  status: "ready",
}));

test.beforeEach(async ({ page }) => {
  await page.route("**/documents", (route) => route.fulfill({ json: { documents } }));
  await page.route("**/ask", async (route) => {
    await route.fulfill({ json: {
      ...route.request().postDataJSON(),
      status: "insufficient_evidence", answer: "No supporting evidence for this test.", claims: [],
      meta: { retrieval_mode: "bm25", elapsed_ms: 0, cached: false },
    } });
  });
  await page.route("**/compare", async (route) => {
    await route.fulfill({ json: {
      question: "What changed between these reports?", ...route.request().postDataJSON(),
      status: "compared", summary: "No supported changes identified.", changes: [],
      meta: { retrieval_mode: "bm25", elapsed_ms: 0, cached: false },
    } });
  });
  await page.goto("/story");
});

test("catch-up and ask default to all reports; timeline toggles stay in sync with source checkboxes", async ({ page }) => {
  const timeline = page.getByRole("list", { name: "Report publication timeline" });
  await expect(timeline.locator('[aria-pressed="true"]')).toHaveCount(4);
  const catchRequest = page.waitForRequest((request) => request.url().endsWith("/ask"));
  await page.getByRole("button", { name: "Catch me up", exact: true }).click();
  expect((await catchRequest).postDataJSON().doc_ids).toEqual(documents.map((doc) => doc.doc_id));
  await page.getByRole("button", { name: "Ask Folio", exact: true }).click();
  await expect(page.locator('.source-options input:checked')).toHaveCount(4);
  await timeline.getByRole("button", { name: /Story report 1/ }).click();
  await timeline.getByRole("button", { name: /Story report 2/ }).click();
  await expect(timeline.locator('[aria-pressed="true"]')).toHaveCount(2);
  await expect(page.locator('.source-options input:checked')).toHaveCount(2);
  await page.getByRole("textbox", { name: "Ask a question about the selected reports" }).fill("What happened?");
  const askRequest = page.waitForRequest((request) => request.url().endsWith("/ask"));
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  expect((await askRequest).postDataJSON().doc_ids).toEqual(["report-3", "report-4"]);
  await page.getByRole("button", { name: "Select All", exact: true }).click();
  await expect(timeline.locator('[aria-pressed="true"]')).toHaveCount(4);
});

test("comparison defaults to the latest two and timeline edits reach the comparison request", async ({ page }) => {
  await page.getByRole("button", { name: "What Changed", exact: true }).click();
  const timeline = page.getByRole("list", { name: "Report publication timeline" });
  await expect(page.getByLabel("Older report", { exact: true })).toHaveValue("report-3");
  await expect(page.getByLabel("Newer report", { exact: true })).toHaveValue("report-4");
  await expect(timeline.getByRole("button", { name: /Story report 1/ })).toBeDisabled();
  await timeline.getByRole("button", { name: /Story report 3/ }).click();
  await expect(page.getByRole("button", { name: "Compare reports", exact: true })).toBeDisabled();
  await timeline.getByRole("button", { name: /Story report 1/ }).click();
  await expect(page.getByLabel("Older report", { exact: true })).toHaveValue("report-1");
  const request = page.waitForRequest((request) => request.url().endsWith("/compare"));
  await page.getByRole("button", { name: "Compare reports", exact: true }).click();
  expect((await request).postDataJSON()).toMatchObject({ older_doc_id: "report-1", newer_doc_id: "report-4" });
  await page.getByRole("button", { name: "Catch Me Up", exact: true }).click();
  await expect(timeline.locator('[aria-pressed="true"]')).toHaveCount(4);
  await page.getByRole("button", { name: "What Changed", exact: true }).click();
  await expect(page.getByLabel("Older report", { exact: true })).toHaveValue("report-1");
});
