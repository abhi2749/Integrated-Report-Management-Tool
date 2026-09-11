import test from "node:test";
import assert from "node:assert/strict";
import {
  buildSemanticFieldMap,
  getDefaultAggregation,
  getSemanticDatasetId,
  getSemanticFieldLabel,
  getSemanticFields,
} from "../semanticFieldAdapter.js";

const dataset = {
  id: "meter",
  semantic_dataset_id: "meters_semantic",
  columns: ["Meter_Serial_Number", "Energy_Kwh"],
  semantic: {
    dimensions: [{ name: "Meter", physical_field: "Meter_Serial_Number", display_name: "Meter" }],
    measures: [{ name: "Energy Consumption", physical_field: "Energy_Kwh", display_name: "Energy Consumption", default_aggregation: "SUM" }],
  },
};

test("reads semantic dimensions and measures without replacing physical fields", () => {
  const fields = getSemanticFields(dataset);
  assert.equal(fields.length, 2);
  assert.equal(fields[1].physicalField, "Energy_Kwh");
  assert.equal(fields[1].role, "measure");
});

test("builds semantic labels and default aggregation", () => {
  assert.equal(getSemanticFieldLabel(dataset, "Energy_Kwh"), "Energy Consumption (Energy_Kwh)");
  assert.equal(getDefaultAggregation(dataset, "Energy_Kwh"), "SUM");
});

test("reads semantic dataset id", () => {
  assert.equal(getSemanticDatasetId(dataset), "meters_semantic");
});

test("keeps physical fields usable when semantic metadata is absent", () => {
  const plain = { id: "plain", columns: ["amount"] };
  assert.deepEqual(getSemanticFields(plain), []);
  assert.equal(getSemanticFieldLabel(plain, "amount"), "amount");
  assert.equal(buildSemanticFieldMap(plain).size, 0);
  assert.equal(getDefaultAggregation(plain, "amount"), null);
  assert.equal(getSemanticDatasetId(plain), "");
});
