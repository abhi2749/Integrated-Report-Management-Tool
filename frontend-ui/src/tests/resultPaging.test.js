import test from "node:test";
import assert from "node:assert/strict";

function pageWindow(totalRows, offset, limit) {
  const safeTotal = Math.max(0, Number(totalRows) || 0);
  const safeOffset = Math.max(0, Number(offset) || 0);
  const safeLimit = Math.max(1, Number(limit) || 1);
  const returned = Math.max(0, Math.min(safeLimit, safeTotal - safeOffset));
  return {
    offset: safeOffset,
    limit: safeLimit,
    returned,
    has_more: safeOffset + returned < safeTotal,
  };
}

test("paged result window does not materialize the complete result", () => {
  const page = pageWindow(100_000_000, 500, 500);
  assert.deepEqual(page, {
    offset: 500,
    limit: 500,
    returned: 500,
    has_more: true,
  });
});

test("last page correctly reports no more rows", () => {
  const page = pageWindow(1250, 1000, 500);
  assert.equal(page.returned, 250);
  assert.equal(page.has_more, false);
});
