import test from "node:test";
import assert from "node:assert/strict";
import { createResultWindowCache } from "../resultWindowCache.js";

test("result window cache reuses the same page request", async () => {
  const cache = createResultWindowCache({ maxWindows: 2 });
  let calls = 0;
  const fetcher = async (_jobId, page) => {
    calls += 1;
    return { ...page, rows: [{ id: calls }] };
  };

  const first = await cache.get("job-1", { offset: 0, limit: 500 }, fetcher);
  const second = await cache.get("job-1", { offset: 0, limit: 500 }, fetcher);

  assert.deepEqual(second, first);
  assert.equal(calls, 1);
  assert.equal(cache.size(), 1);
});

test("result window cache deduplicates concurrent requests", async () => {
  const cache = createResultWindowCache({ maxWindows: 2 });
  let calls = 0;
  const fetcher = async () => {
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, 5));
    return { rows: [{ value: 1 }] };
  };

  const [first, second] = await Promise.all([
    cache.get("job-1", { offset: 500, limit: 500 }, fetcher),
    cache.get("job-1", { offset: 500, limit: 500 }, fetcher),
  ]);

  assert.deepEqual(first, second);
  assert.equal(calls, 1);
});

test("result window cache evicts oldest windows without depending on dataset size", async () => {
  const cache = createResultWindowCache({ maxWindows: 2 });
  const fetcher = async (_jobId, page) => ({ offset: page.offset, rows: [] });

  await cache.get("job-1", { offset: 0, limit: 500 }, fetcher);
  await cache.get("job-1", { offset: 500, limit: 500 }, fetcher);
  await cache.get("job-1", { offset: 1000, limit: 500 }, fetcher);

  assert.equal(cache.size(), 2);
});

test("result window cache invalidates pages for one execution job", async () => {
  const cache = createResultWindowCache({ maxWindows: 4 });
  const fetcher = async () => ({ rows: [] });

  await cache.get("job-1", { offset: 0, limit: 500 }, fetcher);
  await cache.get("job-2", { offset: 0, limit: 500 }, fetcher);
  cache.invalidate("job-1");

  assert.equal(cache.size(), 1);
});

test("result window cache enforces a byte budget for wide pages", async () => {
  const cache = createResultWindowCache({ maxWindows: 8, maxBytes: 100 });
  const fetcher = async (_jobId, page) => ({ ...page, rows: [{ payload: "x".repeat(40) }] });

  await cache.get("job-1", { offset: 0, limit: 1 }, fetcher);
  await cache.get("job-1", { offset: 1, limit: 1 }, fetcher);

  assert.equal(cache.size(), 1);
  assert.ok(cache.bytes() <= 100);
});


test("result window cache does not retain a single page larger than its byte budget", async () => {
  const cache = createResultWindowCache({ maxWindows: 8, maxBytes: 20 });
  const page = await cache.get("job-1", { offset: 0, limit: 1 }, async () => ({ rows: [{ payload: "x".repeat(100) }] }));

  assert.equal(page.rows.length, 1);
  assert.equal(cache.size(), 0);
  assert.equal(cache.bytes(), 0);
});

test("result window cache reuses cached byte accounting without reserializing the page", async () => {
  const cache = createResultWindowCache({ maxWindows: 2, maxBytes: 100_000 });
  const page = { rows: Array.from({ length: 500 }, (_, index) => ({ id: index, value: "x".repeat(80) })) };
  let calls = 0;
  const fetcher = async () => { calls += 1; return page; };

  const first = await cache.get("job-wide", { offset: 0, limit: 500 }, fetcher);
  const second = await cache.get("job-wide", { offset: 0, limit: 500 }, fetcher);

  assert.strictEqual(second, first);
  assert.equal(calls, 1);
  assert.ok(cache.bytes() > 0);
});
