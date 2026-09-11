import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const source = fs.readFileSync(new URL("../ReportBuilder.jsx", import.meta.url), "utf8");

test("6K saved report restores its durable execution result page", () => {
  assert.match(source, /fetchExecutionJobResultPage\(savedExecutionJobId/);
  assert.match(source, /execution_job_id: savedExecutionJobId/);
  assert.match(source, /loadedSourceColumns/);
  assert.match(source, /loadedSourceRows/);
});
