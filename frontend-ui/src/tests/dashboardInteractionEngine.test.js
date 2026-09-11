import test from "node:test";
import assert from "node:assert/strict";
import {
  FILTER_OPERATORS,
  distinctValues,
  matchesFilter,
  applyDashboardFilters,
  filterSummary,
} from "../dashboardInteractionEngine.js";

test("matchesDashboardFilters supports text and numeric operators", () => {
  const row = { name: "Alpha Meter", value: 42 };
  assert.equal(matchesFilter(row, { field: "name", operator: FILTER_OPERATORS.CONTAINS, value: "meter" }), true);
  assert.equal(matchesFilter(row, { field: "name", operator: FILTER_OPERATORS.EQUALS, value: "alpha meter" }), true);
  assert.equal(matchesFilter(row, { field: "value", operator: FILTER_OPERATORS.GTE, value: 40 }), true);
  assert.equal(matchesFilter(row, { field: "value", operator: FILTER_OPERATORS.LT, value: 40 }), false);
});

test("applyDashboardFilters combines active filters without mutating input", () => {
  const rows = [
    { zone: "West", value: 10 },
    { zone: "West", value: 20 },
    { zone: "East", value: 30 },
  ];
  const filtered = applyDashboardFilters(rows, [
    { field: "zone", operator: FILTER_OPERATORS.EQUALS, value: "west" },
    { field: "value", operator: FILTER_OPERATORS.GT, value: 10 },
  ]);
  assert.deepEqual(filtered, [{ zone: "West", value: 20 }]);
  assert.deepEqual(rows, [
    { zone: "West", value: 10 },
    { zone: "West", value: 20 },
    { zone: "East", value: 30 },
  ]);
});

test("distinctValues returns stable unique values and honors an explicit UI list limit", () => {
  const rows = [
    { zone: "West" },
    { zone: "west" },
    { zone: "East" },
    { zone: "North" },
  ];
  assert.deepEqual(distinctValues(rows, "zone", 2), ["West", "west"]);
  assert.deepEqual(distinctValues(rows, "zone", 10), ["West", "west", "East", "North"]);
});

test("filterSummary produces a readable dashboard filter description", () => {
  assert.equal(
    filterSummary([{ field: "zone", operator: FILTER_OPERATORS.EQUALS, value: "West" }]),
    "zone equals West",
  );
});
