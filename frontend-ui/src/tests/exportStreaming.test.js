import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const source = fs.readFileSync(
  path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "executionClient.js"),
  "utf8",
);

test("legacy export client routes through background export jobs", () => {
  assert.match(source, /return runExecutionExportJob\(jobId, normalizedFormat, filename, options\)/);
});

test("export download supports direct response streaming to disk", () => {
  assert.match(source, /showSaveFilePicker/);
  assert.match(source, /response\.body\.pipeTo/);
});
