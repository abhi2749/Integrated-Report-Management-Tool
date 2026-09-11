import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const src = path.resolve('src');
const read = (name) => fs.readFileSync(path.join(src, name), 'utf8');

test('10I FE execution contract remains production-oriented', () => {
  const client = read('executionClient.js');
  assert.match(client, /DEFAULT_TIMEOUT_MS\s*=\s*0/);
  assert.match(client, /AbortSignal|signal/);
  assert.match(client, /cancelExecutionJob/);
  assert.match(client, /runExecutionExportJob/);
});

test('10I FE large-result contract stays page/window bounded', () => {
  const cache = read('resultWindowCache.js');
  assert.match(cache, /maxBytes|cachedBytes/);
  assert.match(cache, /evict|cache/i);
});

test('10I report builder uses completed execution jobs for exports', () => {
  const builder = read('ReportBuilder.jsx');
  assert.match(builder, /runExecutionExportJob/);
  assert.match(builder, /execution_job_id/);
});
