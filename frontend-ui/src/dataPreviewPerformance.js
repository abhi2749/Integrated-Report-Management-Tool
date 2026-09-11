export function filterPreviewRows(rows, filter) {
  const source = Array.isArray(rows) ? rows : [];
  if (!filter?.column || String(filter?.value ?? '').trim() === '') return source;

  const target = String(filter.value).trim().toLowerCase();
  const operator = filter.operator || 'contains';

  return source.filter((row) => {
    const raw = row?.[filter.column];
    if (raw === null || raw === undefined) return false;
    const value = String(raw).toLowerCase();
    switch (operator) {
      case 'equals': return value === target;
      case 'not_equals': return value !== target;
      case 'starts_with': return value.startsWith(target);
      case 'ends_with': return value.endsWith(target);
      case 'contains':
      default: return value.includes(target);
    }
  });
}

export function collectPreviewFilterValues(rows, column, maxValues = 200) {
  if (!column) return [];
  const source = Array.isArray(rows) ? rows : [];
  const limit = Math.max(1, Number(maxValues) || 200);
  const values = new Set();

  for (const row of source) {
    const value = row?.[column];
    if (value === null || value === undefined || value === '') continue;
    values.add(String(value));
    if (values.size >= limit) break;
  }

  return Array.from(values).sort((a, b) => a.localeCompare(b, undefined, {
    numeric: true,
    sensitivity: 'base',
  }));
}
