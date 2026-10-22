// Production UI + FastAPI + SQLite + BM25 + citation validation.
// Only the external model response is deterministic (selection-backend.py).
import { test, expect } from "@playwright/test";
import type { AskResponse, CompareResponse, FolioDocument, Passage } from "../lib/types";

test("multi-select scopes catch-up and questions, preserves timeline, and compares exactly two reports", async ({ page, request }) => {
  const api = "http://127.0.0.1:8011";
  // Point the production build's API adapter at this isolated real backend.
  await page.route("http://localhost:8000/**", async (route) => {
    const response = await route.fetch({ url: route.request().url().replace("http://localhost:8000", api) });
    await route.fulfill({ response });
  });
  await page.goto("/story");
  await expect(page.getByText("No indexed reports yet. Upload a dated report to begin.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Catch me up", exact: true })).toBeDisabled();

  async function upload(index: number) {
    const response = await request.post(`${api}/documents`, {
      multipart: {
        file: { name: `report-${index}.txt`, mimeType: "text/plain", buffer: Buffer.from(`Report ${index}: ${index * 10} shelters are open. The story remains unresolved.`) },
        title: `Shelter report ${index}`, report_date: `2026-10-${20 + index}`,
      },
    });
    expect(response.status()).toBe(201);
    return await response.json() as FolioDocument;
  }
  const docs = [await upload(1), await upload(2), await upload(3)];
  const ids = docs.map((d) => d.doc_id);
  await page.reload();
  const picker = page.locator(".source-picker");
  await expect(picker.getByRole("checkbox")).toHaveCount(3);
  for (const checkbox of await picker.getByRole("checkbox").all()) await expect(checkbox).toBeChecked();

  async function catchUp(expected: string[]) {
    const pending = page.waitForResponse((r) => r.url().endsWith("/ask") && r.request().method() === "POST");
    await page.getByRole("button", { name: /^(Catch me up|Update catch-up from selected reports)$/ }).click();
    const response = await pending;
    expect(response.request().postDataJSON().doc_ids).toEqual(expected);
    expect(response.status()).toBe(200);
    const body = await response.json() as AskResponse;
    expect(body.doc_ids).toEqual(expected);
    expect(body.status).toBe("answered");
    const citedIds = [...new Set(body.claims.flatMap((claim) => claim.citations.map((c) => c.doc_id)))].sort();
    expect(citedIds).toEqual([...expected].sort());
    await expect(page.locator(".takeaway-card")).toHaveCount(body.claims.length);
    return body;
  }
  await catchUp(ids);
  await picker.getByRole("checkbox").nth(1).uncheck();
  await catchUp([ids[0], ids[2]]);
  await picker.getByRole("button", { name: "Clear", exact: true }).click();
  await expect(page.getByRole("button", { name: /Update catch-up/ })).toBeDisabled();
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(0);

  // Browsing the timeline does not alter selection. Using a report adds it.
  const timeline = page.getByRole("list", { name: "Report publication timeline" });
  await timeline.getByRole("button").nth(0).click();
  await expect(page.locator("#timeline-report h3")).toHaveText(docs[0].title);
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Use this report" }).click();
  await timeline.getByRole("button").nth(2).click();
  await page.getByRole("button", { name: "Use this report" }).click();
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(2);
  await page.getByRole("button", { name: "Use this report" }).click();
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(2);

  await page.getByRole("button", { name: "Ask Folio", exact: true }).click();
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(2);
  await page.getByRole("textbox", { name: "Ask a question about the selected reports" }).fill("How many shelters are open?");
  const asking = page.waitForResponse((r) => r.url().endsWith("/ask") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  const response = await asking;
  expect(response.request().postDataJSON().doc_ids).toEqual([ids[0], ids[2]]);
  const answer = await response.json() as AskResponse;
  expect(new Set(answer.claims.flatMap((c) => c.citations.map((p) => p.doc_id)))).toEqual(new Set([ids[0], ids[2]]));
  const citation = answer.claims[0].citations[0];
  await page.locator(".takeaway-card .citation-button").first().click();
  await expect(page.getByText("Exact match in stored passage", { exact: true })).toBeVisible();
  const passage = await (await request.get(`${api}/passages/${citation.passage_id}`)).json() as Passage;
  expect(passage.doc_id).toBe(citation.doc_id);
  expect(passage.text).toContain(citation.quote);
  await page.getByRole("button", { name: "Full passage", exact: true }).click();
  await expect(page.locator(".evidence-context mark")).toHaveText(citation.quote);
  await page.setViewportSize({ width: 700, height: 900 });
  await page.locator(".takeaway-card .citation-button").first().click();
  await expect(page.getByRole("complementary", { name: "Evidence", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("complementary", { name: "Evidence", exact: true })).not.toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });

  await page.getByRole("button", { name: "What Changed", exact: true }).click();
  await expect(picker).toHaveCount(0);
  await expect(page.getByRole("combobox")).toHaveCount(2);
  await page.getByLabel("Older report").selectOption(ids[0]);
  await page.getByLabel("Newer report").selectOption(ids[0]);
  await expect(page.getByRole("button", { name: "Compare reports" })).toBeDisabled();
  await page.getByLabel("Newer report").selectOption(ids[2]);
  const comparing = page.waitForResponse((r) => r.url().endsWith("/compare") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Compare reports" }).click();
  const compared = await comparing;
  expect(compared.request().postDataJSON()).toEqual({ older_doc_id: ids[0], newer_doc_id: ids[2] });
  expect(compared.status()).toBe(200);
  const comparison = await compared.json() as CompareResponse;
  expect(comparison.status).toBe("compared");
  expect(comparison.changes[0].older_citations[0].doc_id).toBe(ids[0]);
  expect(comparison.changes[0].newer_citations[0].doc_id).toBe(ids[2]);
  await page.locator(".change-card .citation-button").last().click();
  await expect(page.getByText("Exact match in stored passage", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Catch Me Up", exact: true }).click();
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(2);
  await picker.getByRole("button", { name: "Select All", exact: true }).click();
  await catchUp(ids);

  // A fresh load really selects every report, with the v1 request limit visible.
  await page.getByRole("button", { name: "Upload report", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "report-4.txt", mimeType: "text/plain", buffer: Buffer.from("Report 4: 40 shelters are open. The story remains unresolved."),
  });
  await dialog.getByLabel("Title", { exact: true }).fill("Shelter report 4");
  await dialog.getByLabel("Report date", { exact: true }).fill("2026-10-24");
  await dialog.getByRole("button", { name: "Add report", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(4);
  await upload(5); await upload(6);
  await page.reload();
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(6);
  await expect(picker.getByRole("alert")).toContainText("Select up to 5 reports");
  await expect(page.getByRole("button", { name: "Catch me up", exact: true })).toBeDisabled();
  await picker.getByRole("checkbox").last().uncheck();
  await expect(page.getByRole("button", { name: "Catch me up", exact: true })).toBeEnabled();
  await picker.getByRole("button", { name: "Clear", exact: true }).click();
  await picker.getByRole("button", { name: "Select All", exact: true }).click();
  await expect(picker.getByRole("checkbox", { checked: true })).toHaveCount(6);
  await page.getByRole("button", { name: "Ask Folio", exact: true }).click();
  await page.getByRole("textbox", { name: "Ask a question about the selected reports" }).fill("shelters");
  await expect(page.getByRole("button", { name: "Ask question", exact: true })).toBeDisabled();
  await picker.getByRole("button", { name: "Clear", exact: true }).click();
  await expect(page.getByRole("button", { name: "Ask question", exact: true })).toBeDisabled();
});
