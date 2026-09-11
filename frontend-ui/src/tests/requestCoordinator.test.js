import test from "node:test";
import assert from "node:assert/strict";
import { createRequestCoordinator } from "../requestCoordinator.js";

test("deduplicates identical concurrent requests", async () => {
  const coordinator = createRequestCoordinator();
  let calls = 0;
  const operation = async () => { calls += 1; return { rows: [1] }; };
  const [a, b] = await Promise.all([
    coordinator.request("page:1", operation),
    coordinator.request("page:1", operation),
  ]);
  assert.equal(calls, 1);
  assert.deepEqual(a, b);
});

test("debounces an interactive request without retaining result data", async () => {
  const coordinator = createRequestCoordinator({ debounceMs: 15 });
  let calls = 0;
  const result = await coordinator.request("filter", async () => { calls += 1; return 42; });
  assert.equal(result, 42);
  assert.equal(calls, 1);
});

test("cancels work when caller aborts", async () => {
  const coordinator = createRequestCoordinator();
  const controller = new AbortController();
  const promise = coordinator.request("slow", async ({ signal }) => {
    await new Promise((resolve) => setTimeout(resolve, 25));
    if (signal.aborted) throw new DOMException("The request was aborted.", "AbortError");
    return 1;
  }, { signal: controller.signal });
  controller.abort();
  await assert.rejects(promise, { name: "AbortError" });
});
