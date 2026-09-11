import test from "node:test";
import assert from "node:assert/strict";
import { distinctValues, FILTER_OPERATORS } from "../dashboardInteractionEngine.js";

test("dashboard value discovery stays bounded to the loaded window", () => {
  const rows = Array.from({ length: 100000 }, (_, index) => ({ category: `C${index}`, value: index }));
  const values = distinctValues(rows, "category", 100);
  assert.equal(values.length, 100);
});

test("dashboard filter operators preserve the server-transform mapping", () => {
  assert.deepEqual(FILTER_OPERATORS, {
    CONTAINS: "contains",
    EQUALS: "equals",
    NOT_EQUALS: "not_equals",
    GT: "gt",
    GTE: "gte",
    LT: "lt",
    LTE: "lte",
  });
});
