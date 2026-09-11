import test from "node:test";
import assert from "node:assert/strict";

function displayedRows(filterActive, previewRows, sourceRows) {
  return filterActive ? previewRows : sourceRows;
}

test("report result selection does not clone or sort the source window", () => {
  const rows = Array.from({ length: 100000 }, (_, index) => ({ id: index }));
  const selected = displayedRows(false, [{ id: 1 }], rows);
  assert.strictEqual(selected, rows);
});

test("server-filtered report window is used without client-side row transformation", () => {
  const source = [{ id: 1 }, { id: 2 }];
  const filtered = [{ id: 2 }];
  assert.strictEqual(displayedRows(true, filtered, source), filtered);
});
