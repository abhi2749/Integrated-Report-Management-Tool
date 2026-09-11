import test from "node:test";
import assert from "node:assert/strict";
import {
  VISUALIZATION_TYPES,
  rowsFromResult,
  columnsFromResult,
  numeric,
  isVisualizationType,
  normalizeVisualization,
  normalizeVisualizationCollection,
  buildChartPoints,
} from "../visualizationEngine.js";

test("result helpers normalize rows and columns safely", () => {
  const result = {
    rows: [{ name: "A", value: "10" }],
    columns: [{ name: "name" }, { field: "value" }],
  };
  assert.deepEqual(rowsFromResult(result), [{ name: "A", value: "10" }]);
  assert.deepEqual(columnsFromResult(result), ["name", "value"]);
  assert.equal(numeric("10.5"), 10.5);
  assert.equal(numeric("not-a-number"), null);
});

test("visualization types and normalization enforce valid presentation metadata", () => {
  assert.equal(isVisualizationType(VISUALIZATION_TYPES.TABLE), true);
  assert.equal(isVisualizationType("unknown"), false);
  const widget = normalizeVisualization({ type: "unknown", span: 99, height: 99, title: "" }, 2);
  assert.equal(widget.type, VISUALIZATION_TYPES.TABLE);
  assert.equal(widget.span, 12);
  assert.equal(widget.height, 3);
  assert.equal(widget.title, "Table");
});

test("chart point construction skips non-numeric values and preserves explicit point limit", () => {
  const rows = [
    { label: "A", value: 10 },
    { label: "B", value: "20" },
    { label: "C", value: "bad" },
    { label: "D", value: 40 },
  ];
  assert.deepEqual(buildChartPoints(rows, "label", "value", 3), [
    { label: "A", value: 10 },
    { label: "B", value: 20 },
  ]);
});

test("visualization collection normalization safely handles non-array input", () => {
  assert.deepEqual(normalizeVisualizationCollection(null), []);
  const collection = normalizeVisualizationCollection([{ type: "bar", span: 6 }]);
  assert.equal(collection.length, 1);
  assert.equal(collection[0].type, "bar");
});
