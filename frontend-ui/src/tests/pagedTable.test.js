import test from "node:test";
import assert from "node:assert/strict";
import { getPagedRows, normalizePagedTableState } from "../pagedTable.js";

test("paged table returns only one bounded page", () => {
  const rows = Array.from({ length: 5000 }, (_, index) => index);
  const page = getPagedRows(rows, 3, 500);
  assert.equal(page.offset, 1500);
  assert.equal(page.rows.length, 500);
  assert.equal(page.rows[0], 1500);
});

test("paged table clamps the last page to the logical boundary", () => {
  const state = normalizePagedTableState(1001, 99, 500);
  assert.equal(state.pageIndex, 2);
  assert.equal(state.offset, 1000);
  assert.equal(state.endOffset, 1001);
});
