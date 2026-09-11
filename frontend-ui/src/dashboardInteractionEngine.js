const OPERATORS = Object.freeze({
  CONTAINS: "contains",
  EQUALS: "equals",
  NOT_EQUALS: "not_equals",
  GT: "gt",
  GTE: "gte",
  LT: "lt",
  LTE: "lte",
});

export const FILTER_OPERATORS = OPERATORS;

function text(value) {
  return value == null ? "" : String(value).trim().toLowerCase();
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function distinctValues(rows, field, limit = 100) {
  const seen = new Set();
  const values = [];
  for (const row of Array.isArray(rows) ? rows : []) {
    const value = row?.[field];
    const key = value == null ? "" : String(value);
    if (seen.has(key)) continue;
    seen.add(key);
    values.push(key);
    if (values.length >= limit) break;
  }
  return values;
}

export function matchesFilter(row, filter) {
  if (!filter?.field) return true;
  const actual = row?.[filter.field];
  const expected = filter.value ?? "";
  const operator = filter.operator || OPERATORS.EQUALS;

  if (operator === OPERATORS.CONTAINS) return text(actual).includes(text(expected));
  if (operator === OPERATORS.EQUALS) return text(actual) === text(expected);
  if (operator === OPERATORS.NOT_EQUALS) return text(actual) !== text(expected);

  const actualNumber = number(actual);
  const expectedNumber = number(expected);
  if (actualNumber === null || expectedNumber === null) return false;
  if (operator === OPERATORS.GT) return actualNumber > expectedNumber;
  if (operator === OPERATORS.GTE) return actualNumber >= expectedNumber;
  if (operator === OPERATORS.LT) return actualNumber < expectedNumber;
  if (operator === OPERATORS.LTE) return actualNumber <= expectedNumber;
  return true;
}

export function applyDashboardFilters(rows, filters = []) {
  const active = Array.isArray(filters) ? filters.filter((filter) => filter?.field) : [];
  if (!active.length) return Array.isArray(rows) ? rows : [];
  return (Array.isArray(rows) ? rows : []).filter((row) => active.every((filter) => matchesFilter(row, filter)));
}

export function filterSummary(filters = []) {
  return (Array.isArray(filters) ? filters : [])
    .filter((filter) => filter?.field)
    .map((filter) => `${filter.field} ${filter.operator || OPERATORS.EQUALS} ${filter.value ?? ""}`)
    .join(" · ");
}
