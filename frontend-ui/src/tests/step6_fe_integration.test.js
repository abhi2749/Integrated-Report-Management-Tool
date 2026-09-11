import test from "node:test";
import assert from "node:assert/strict";
import { getPagedRows } from "../pagedTable.js";
import { applyDashboardFilters } from "../dashboardInteractionEngine.js";
import { submitExecutionJob, waitForExecutionJob } from "../executionClient.js";

function makeRows(count, columns = 2) {
  return Array.from({ length: count }, (_, index) => {
    const row = { id: index, value: count - index, group: index % 5 };
    for (let column = 4; column <= columns; column += 1) {
      row[`column_${column}`] = `${index}-${column}`;
    }
    return row;
  });
}

test("6A 50-row dataset stays fully page-addressable", () => {
  const rows = makeRows(50);
  const page = getPagedRows(rows, 0, 500);
  assert.equal(page.totalRows, 50);
  assert.equal(page.rows.length, 50);
});

test("6B 500-row dataset fills exactly one UI page", () => {
  const rows = makeRows(500);
  const page = getPagedRows(rows, 0, 500);
  assert.equal(page.totalRows, 500);
  assert.equal(page.rows.length, 500);
  assert.equal(page.rows[499].id, 499);
});

test("6C 100K-row dataset exposes only the requested page", () => {
  const rows = makeRows(100_000);
  const page = getPagedRows(rows, 100, 500);
  assert.equal(page.totalRows, 100_000);
  assert.equal(page.offset, 50_000);
  assert.equal(page.rows.length, 500);
  assert.equal(page.rows[0].id, 50_000);
});

test("6D 500K-row dataset remains page-bounded", () => {
  const rows = makeRows(500_000);
  const page = getPagedRows(rows, 999, 500);
  assert.equal(page.totalRows, 500_000);
  assert.equal(page.rows.length, 500);
  assert.equal(page.rows[0].id, 499_500);
});

test("6E 1M-row dataset remains page-bounded at the last page", () => {
  const rows = makeRows(1_000_000);
  const page = getPagedRows(rows, 1_999, 500);
  assert.equal(page.totalRows, 1_000_000);
  assert.equal(page.pageCount, 2_000);
  assert.equal(page.rows.length, 500);
  assert.equal(page.rows[499].id, 999_999);
});

test("6F 123-column result preserves all columns without row multiplication", () => {
  const rows = makeRows(500, 123);
  const page = getPagedRows(rows, 0, 500);
  assert.equal(page.rows.length, 500);
  assert.equal(Object.keys(page.rows[0]).length, 123);
  assert.equal(page.rows[0].column_123, "0-123");
});

test("6G JOIN-shaped result remains pageable after combining matching rows", () => {
  const left = makeRows(1_000).map((row) => ({ key: row.id, left_value: row.value }));
  const right = makeRows(1_000).map((row) => ({ key: row.id, right_value: row.group }));
  const rightByKey = new Map(right.map((row) => [row.key, row]));
  const joined = left.flatMap((row) => {
    const match = rightByKey.get(row.key);
    return match ? [{ ...row, ...match }] : [];
  });
  const page = getPagedRows(joined, 1, 500);
  assert.equal(joined.length, 1_000);
  assert.equal(page.rows.length, 500);
  assert.equal(page.rows[0].key, 500);
  assert.equal(page.rows[0].right_value, 0);
});

test("6H filter, sort, group and aggregation operate on bounded UI data", () => {
  const rows = makeRows(2_000);
  const filtered = applyDashboardFilters(rows, [{ field: "group", operator: "equals", value: 2 }]);
  const sorted = [...filtered].sort((a, b) => b.value - a.value);
  const grouped = new Map();
  for (const row of sorted.slice(0, 500)) {
    grouped.set(row.group, (grouped.get(row.group) || 0) + row.value);
  }
  assert.equal(filtered.length, 400);
  assert.equal(sorted[0].value, 1_998);
  assert.equal(grouped.get(2), 400_200);
});

test("6I browser-performance contract keeps a million-row result viewport-bounded", () => {
  const rows = makeRows(1_000_000);
  const started = Date.now();
  const page = getPagedRows(rows, 1_000, 500);
  const elapsed = Date.now() - started;
  assert.equal(page.rows.length, 500);
  assert.equal(page.totalRows, 1_000_000);
  assert.ok(elapsed < 1_000, `page extraction took ${elapsed}ms`);
});

test("6J FE ↔ BE execution contract returns job id and page-backed result", async () => {
  globalThis.localStorage = { getItem: () => "" };
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (String(url).endsWith("/execution/jobs")) {
      return new Response(JSON.stringify({ success: true, job_id: "step6-job" }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (String(url).includes("/execution/jobs/step6-job/result")) {
      return new Response(JSON.stringify({ success: true, rows: [{ id: 1 }], columns: ["id"], total_rows: 100_000, has_more: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (String(url).endsWith("/execution/jobs/step6-job")) {
      return new Response(JSON.stringify({ success: true, job: { status: "completed", result_available: true, result_row_count: 100_000, columns: ["id"] } }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  const jobId = await submitExecutionJob({ datasets: [], limit: 0 });
  const execution = await waitForExecutionJob(jobId, { returnOnFirstPage: true, pageSize: 500 });
  assert.equal(jobId, "step6-job");
  assert.equal(execution.total_rows, 100_000);
  assert.equal(execution.rows.length, 1);
  assert.ok(calls.some((call) => call.url.includes("/execution/jobs/step6-job/result?offset=0&limit=500")));
});
