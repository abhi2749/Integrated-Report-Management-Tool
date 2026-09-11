import test from "node:test";
import assert from "node:assert/strict";
import { getVirtualRowRange } from "../virtualizedTable.js";

test("virtual range renders only a bounded window", () => {
  const range = getVirtualRowRange(10000000, 0, 360, 36, 8);
  assert.equal(range.start, 0);
  assert.ok(range.end < 10000000);
});

test("virtual range follows scroll position without depending on dataset size", () => {
  const range = getVirtualRowRange(10000000, 3600, 360, 36, 8);
  assert.equal(range.start, 92);
  assert.equal(range.end - range.start, 26);
});

test("virtual range handles empty and invalid inputs safely", () => {
  assert.deepEqual(getVirtualRowRange(0, 0, 360), { start: 0, end: 0, rowHeight: 36 });
  assert.deepEqual(getVirtualRowRange(-1, -10, 0, 0, -1), { start: 0, end: 0, rowHeight: 1 });
});

test("virtual range remains bounded for wide row sets", () => {
  const range = getVirtualRowRange(1_000_000, 50_000, 520, 34, 8);
  assert.ok(range.end - range.start < 100);
  assert.ok(range.start >= 0);
  assert.ok(range.end <= 1_000_000);
});
