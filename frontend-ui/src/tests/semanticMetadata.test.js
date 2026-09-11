import test from "node:test";
import assert from "node:assert/strict";
import { normalizeSemanticMetadata } from "../semanticFieldAdapter.js";

test("normalizes backend semantic metadata without replacing physical fields", () => {
  const result = normalizeSemanticMetadata({
    semantic_dataset_id: "semantic_d1",
    semantic_model: {
      version: 1,
      datasets: [{
        id: "semantic_d1",
        dimensions: [{ name: "Zone", physical_field: "ZONE", data_type: "string" }],
        measures: [{ name: "Energy", physical_field: "KWH", data_type: "decimal", default_aggregation: "SUM" }],
      }],
    },
    consistency: { consistent: true },
  });
  assert.equal(result.semanticDatasetId, "semantic_d1");
  assert.deepEqual(result.fields.map((item) => item.physicalField), ["ZONE", "KWH"]);
  assert.equal(result.consistent, true);
});

test("marks inconsistent backend metadata explicitly", () => {
  const result = normalizeSemanticMetadata({ consistency: { consistent: false, missing_semantic_fields: ["x"] } });
  assert.equal(result.consistent, false);
  assert.deepEqual(result.consistency.missing_semantic_fields, ["x"]);
});
