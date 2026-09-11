import test from "node:test";
import assert from "node:assert/strict";
import { createResultWindowCache } from "../resultWindowCache.js";


test("result window cache forwards AbortSignal to the page fetcher", async () => {
  const cache = createResultWindowCache({ maxWindows: 2 });
  const controller = new AbortController();
  let receivedSignal = null;

  const page = await cache.get("job-1", {
    offset: 0,
    limit: 500,
    signal: controller.signal,
  }, async (_jobId, options) => {
    receivedSignal = options.signal;
    return { rows: [{ id: 1 }], columns: ["id"], has_more: false };
  });

  assert.equal(receivedSignal, controller.signal);
  assert.equal(page.rows.length, 1);
});


test("result window cache still deduplicates the same preview page", async () => {
  const cache = createResultWindowCache({ maxWindows: 2 });
  let calls = 0;
  const fetcher = async () => {
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, 5));
    return { rows: [{ id: 1 }], columns: ["id"], has_more: false };
  };

  const [first, second] = await Promise.all([
    cache.get("job-1", { offset: 0, limit: 500 }, fetcher),
    cache.get("job-1", { offset: 0, limit: 500 }, fetcher),
  ]);

  assert.equal(calls, 1);
  assert.deepEqual(first, second);
});


test("JoinDesigner contains stale preview protection and cancellation hooks", async () => {
  const fs = await import("node:fs/promises");
  const source = await fs.readFile(new URL("../JoinDesigner.jsx", import.meta.url), "utf8");
  assert.match(source, /previewRequestRef/);
  assert.match(source, /new AbortController\(\)/);
  assert.match(source, /cancelPreviewRequest\(\)/);
  assert.match(source, /requestSequence/);
  assert.match(source, /controller\.signal\.aborted/);
});
