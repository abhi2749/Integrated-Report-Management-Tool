import test from "node:test";
import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";

globalThis.localStorage = {
  getItem() { return "test-token"; },
  setItem() {},
  removeItem() {},
};
globalThis.window = { dispatchEvent() {} };

const execution = await import("../executionClient.js");

function jsonResponse(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function mockFetch(sequence) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    const next = sequence.shift();
    if (typeof next === "function") return next(url, options);
    return next;
  };
  return calls;
}

test("submitExecutionJob sends canonical execution payload and returns job id", async () => {
  const calls = mockFetch([jsonResponse({ job_id: "job-123" })]);
  const payload = { query: { datasource: "mysql", table: "orders" } };

  const jobId = await execution.submitExecutionJob(payload);

  assert.equal(jobId, "job-123");
  assert.equal(calls[0].url, "/execution/jobs");
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.headers.get("Authorization"), "Bearer test-token");
  assert.deepEqual(JSON.parse(calls[0].options.body), payload);
});

test("submitExecutionJob rejects a successful response without a job id", async () => {
  mockFetch([jsonResponse({ success: true })]);
  await assert.rejects(
    () => execution.submitExecutionJob({}),
    /did not return a job id/,
  );
});

test("waitForExecutionJob returns inline completed results", async () => {
  mockFetch([jsonResponse({ job: {
    status: "completed",
    result: { success: true, rows: [{ id: 1 }], columns: ["id"] },
  } })]);

  const result = await execution.waitForExecutionJob("job-1", { pollMs: 0 });
  assert.deepEqual(result.rows, [{ id: 1 }]);
  assert.deepEqual(result.columns, ["id"]);
});

test("waitForExecutionJob defaults to the first result page for large results", async () => {
  const calls = mockFetch([
    jsonResponse({ job: {
      status: "completed",
      result_available: true,
      result_row_count: 12000,
      columns: ["id"],
    } }),
    jsonResponse({ rows: [{ id: 1 }, { id: 2 }], columns: ["id"], has_more: true }),
  ]);

  const result = await execution.waitForExecutionJob("job-2", { pollMs: 0, pageSize: 2 });

  assert.deepEqual(result.rows, [{ id: 1 }, { id: 2 }]);
  assert.equal(result.total_rows, 12000);
  assert.equal(result.has_more, true);
  assert.match(calls[1].url, /result\?offset=0&limit=2$/);
});

test("waitForExecutionJob loadAll follows result pages until completion", async () => {
  const calls = mockFetch([
    jsonResponse({ job: {
      status: "completed",
      result_available: true,
      result_row_count: 3,
      columns: ["id"],
    } }),
    jsonResponse({ rows: [{ id: 1 }, { id: 2 }], columns: ["id"], has_more: true }),
    jsonResponse({ rows: [{ id: 3 }], columns: ["id"], has_more: false }),
  ]);

  const result = await execution.waitForExecutionJob("job-3", { pollMs: 0, pageSize: 2, loadAll: true });

  assert.deepEqual(result.rows, [{ id: 1 }, { id: 2 }, { id: 3 }]);
  assert.equal(result.returned_rows, 3);
  assert.equal(result.has_more, false);
  assert.match(calls[2].url, /result\?offset=2&limit=2$/);
});

test("waitForExecutionJob surfaces failed jobs", async () => {
  mockFetch([jsonResponse({ job: { status: "failed", error: "database unavailable" } })]);
  await assert.rejects(
    () => execution.waitForExecutionJob("job-4", { pollMs: 0 }),
    /database unavailable/,
  );
});

test("fetchExecutionJobResultPage sanitizes offset and limit", async () => {
  const calls = mockFetch([jsonResponse({ rows: [], columns: [], has_more: false })]);
  await execution.fetchExecutionJobResultPage("job-5", { offset: -20, limit: 0 });
  assert.match(calls[0].url, /result\?offset=0&limit=5000$/);
});

test("execution result page preserves encoded job ids", async () => {
  const calls = mockFetch([jsonResponse({ rows: [], columns: [] })]);
  await execution.fetchExecutionJobResultPage("job/with space", { offset: 10, limit: 25 });
  assert.match(calls[0].url, /execution\/jobs\/job%2Fwith%20space\/result\?offset=10&limit=25$/);
});

test("downloadExecutionJobExport rejects unsupported formats before network access", async () => {
  let called = false;
  globalThis.fetch = async () => { called = true; return jsonResponse({}); };
  await assert.rejects(
    () => execution.downloadExecutionJobExport("job-6", "xlsx"),
    /Unsupported export format/,
  );
  assert.equal(called, false);
});

test("runExecutionExportJob accepts the canonical export_id response", async () => {
  const originalURL = globalThis.URL;
  const clicked = [];
  globalThis.URL = {
    ...originalURL,
    createObjectURL() { return "blob:test"; },
    revokeObjectURL() {},
  };
  const originalDocument = globalThis.document;
  globalThis.document = {
    createElement() {
      return {
        style: {},
        click() { clicked.push(true); },
        remove() {},
      };
    },
    body: { appendChild() {} },
  };
  try {
    mockFetch([
      jsonResponse({ export_id: "export-123", status: "queued" }),
      jsonResponse({ export: { id: "export-123", status: "completed" } }),
      new Response("id,name\n1,Alice\n", {
        status: 200,
        headers: { "Content-Type": "text/csv", "Content-Disposition": 'attachment; filename="report.csv"' },
      }),
    ]);
    const job = await execution.runExecutionExportJob("job-7", "csv");
    assert.equal(job.status, "completed");
    assert.deepEqual(clicked, [true]);
  } finally {
    globalThis.URL = originalURL;
    globalThis.document = originalDocument;
  }
});

test("runExecutionExportJob rejects a create response without an export id", async () => {
  mockFetch([jsonResponse({ export: {} })]);
  await assert.rejects(
    () => execution.runExecutionExportJob("job-7", "csv"),
    /no export job id/,
  );
});

test("waitForExecutionJob can return the first streamed page while the job is running", async () => {
  const calls = mockFetch([
    jsonResponse({ job: {
      status: "running",
      result_available: true,
      result_streaming: true,
      result_row_count: 1000,
      columns: ["id"],
      result_page_size: 2,
    } }),
    jsonResponse({ rows: [{ id: 1 }, { id: 2 }], columns: ["id"], total_rows: 1000, has_more: true, status: "running", streaming: true }),
  ]);

  const result = await execution.waitForExecutionJob("job-stream", { pollMs: 0, pageSize: 2, returnOnFirstPage: true });

  assert.deepEqual(result.rows, [{ id: 1 }, { id: 2 }]);
  assert.equal(result.execution_in_progress, true);
  assert.equal(result.execution_status, "running");
  assert.equal(result.total_rows, 1000);
  assert.match(calls[1].url, /result\?offset=0&limit=2$/);
});

test("cancelExecutionJob sends a canonical cancellation request", async () => {
  const calls = mockFetch([jsonResponse({ success: true })]);
  const result = await execution.cancelExecutionJob("job/cancel");
  assert.equal(result.success, true);
  assert.equal(calls[0].options.method, "POST");
  assert.match(calls[0].url, /execution\/jobs\/job%2Fcancel\/cancel$/);
});


test("default execution timeout is not a client-side ceiling", async () => {
  const execution = await import("../executionClient.js");
  const source = await readFile(new URL("../executionClient.js", import.meta.url), "utf8");
  assert.match(source, /DEFAULT_TIMEOUT_MS = 0/);
  assert.equal(typeof execution.waitForExecutionJob, "function");
});

import fs from "node:fs";
import path from "node:path";

test("saved report definition preserves execution job id for durable output", () => {
  const source = fs.readFileSync(path.resolve("src/ReportBuilder.jsx"), "utf8");
  assert.match(source, /execution_job_id:\s*result\?\.execution_job_id \|\| null/);
  assert.match(source, /const savedExecutionJobId = report\.execution_job_id \|\| null/);
});
