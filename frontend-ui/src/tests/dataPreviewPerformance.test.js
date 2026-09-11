import test from 'node:test';
import assert from 'node:assert/strict';
import { collectPreviewFilterValues, filterPreviewRows } from '../dataPreviewPerformance.js';

test('filters only the supplied preview window', () => {
  const rows = [
    { id: 1, zone: 'West' },
    { id: 2, zone: 'North' },
    { id: 3, zone: 'West' },
  ];

  const result = filterPreviewRows(rows, {
    column: 'zone',
    operator: 'equals',
    value: 'west',
  });

  assert.deepEqual(result.map((row) => row.id), [1, 3]);
  assert.equal(rows.length, 3);
});

test('preview value discovery stops at the UI suggestion bound', () => {
  const rows = Array.from({ length: 1000 }, (_, index) => ({
    value: `Value-${String(index).padStart(4, '0')}`,
  }));

  const result = collectPreviewFilterValues(rows, 'value', 25);

  assert.equal(result.length, 25);
  assert.equal(result[0], 'Value-0000');
  assert.equal(result[24], 'Value-0024');
});

test('preview value discovery ignores empty values and sorts naturally', () => {
  const result = collectPreviewFilterValues([
    { value: '' },
    { value: null },
    { value: '10' },
    { value: '2' },
    { value: '10' },
  ], 'value', 200);

  assert.deepEqual(result, ['2', '10']);
});
