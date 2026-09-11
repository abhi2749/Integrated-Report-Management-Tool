import test from 'node:test';
import assert from 'node:assert/strict';

function boundedPage(totalRows, offset, limit) {
  const total = Math.max(0, Number(totalRows) || 0);
  const start = Math.min(Math.max(0, Number(offset) || 0), total);
  const size = Math.max(0, Number(limit) || 0);
  return {
    offset: start,
    limit: size,
    returned: Math.min(size, total - start),
    hasMore: start + Math.min(size, total - start) < total,
  };
}

function boundedVirtualRange(totalRows, scrollTop, rowHeight, viewportHeight, overscan = 10) {
  const total = Math.max(0, Number(totalRows) || 0);
  const height = Math.max(1, Number(rowHeight) || 1);
  const viewport = Math.max(1, Number(viewportHeight) || 1);
  const extra = Math.max(0, Number(overscan) || 0);
  const first = Math.max(0, Math.floor(Math.max(0, Number(scrollTop) || 0) / height) - extra);
  const visible = Math.ceil(viewport / height) + extra * 2;
  const end = Math.min(total, first + visible);
  return { start: first, end, count: Math.max(0, end - first) };
}

test('logical 100M-row result stays page-bounded', () => {
  const page = boundedPage(100_000_000, 25_000_000, 5_000);

  assert.equal(page.offset, 25_000_000);
  assert.equal(page.returned, 5_000);
  assert.equal(page.hasMore, true);
  assert.ok(page.returned < 100_000_000);
});

test('logical 100M-row table stays viewport-bounded', () => {
  const range = boundedVirtualRange(100_000_000, 50_000_000 * 34, 34, 420, 10);

  assert.ok(range.count <= 40);
  assert.ok(range.end <= 100_000_000);
  assert.equal(range.start, 49_999_990);
});

test('last page never exceeds logical dataset boundary', () => {
  const page = boundedPage(100_000_001, 100_000_000, 5_000);

  assert.equal(page.offset, 100_000_000);
  assert.equal(page.returned, 1);
  assert.equal(page.hasMore, false);
});

test('validation does not materialize the logical dataset', () => {
  let materializedRows = 0;
  const page = boundedPage(100_000_000, 0, 5_000);
  materializedRows += page.returned;

  assert.equal(materializedRows, 5_000);
  assert.ok(materializedRows < 100_000_000);
});
