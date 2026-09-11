/**
 * Small, connector-neutral result-window cache.
 *
 * The cache stores only requested pages for an execution job. It never knows
 * whether the backend result came from MySQL, MongoDB, ClickHouse, or an
 * application/cross-source JOIN.
 */
export function createResultWindowCache({ maxWindows = 8, maxBytes = 8 * 1024 * 1024 } = {}) {
  const limit = Math.max(1, Number(maxWindows) || 8);
  const byteLimit = Math.max(0, Number(maxBytes) || 0);
  const entries = new Map();
  const inflight = new Map();
  let cachedBytes = 0;

  function estimateBytes(value) {
    try {
      return new TextEncoder().encode(JSON.stringify(value)).byteLength;
    } catch {
      return 0;
    }
  }

  function key(jobId, offset, pageSize) {
    return `${String(jobId)}:${Math.max(0, Number(offset) || 0)}:${Math.max(1, Number(pageSize) || 1)}`;
  }

  function touch(cacheKey, value) {
    const bytes = estimateBytes(value);
    const existing = entries.get(cacheKey);
    if (existing) {
      cachedBytes = Math.max(0, cachedBytes - existing.bytes);
      entries.delete(cacheKey);
    }
    if (byteLimit > 0 && bytes > byteLimit) return value;
    entries.set(cacheKey, { value, bytes });
    cachedBytes += bytes;
    while (entries.size > limit || (byteLimit > 0 && cachedBytes > byteLimit)) {
      const oldest = entries.keys().next().value;
      if (oldest === undefined) break;
      const oldestEntry = entries.get(oldest);
      cachedBytes = Math.max(0, cachedBytes - (oldestEntry?.bytes || 0));
      entries.delete(oldest);
    }
    return value;
  }

  async function get(jobId, { offset = 0, limit: pageSize = 500, signal } = {}, fetcher) {
    if (!jobId) throw new Error("A result execution job id is required.");
    if (typeof fetcher !== "function") throw new Error("A result page fetcher is required.");

    const safeOffset = Math.max(0, Number(offset) || 0);
    const safePageSize = Math.max(1, Number(pageSize) || 500);
    const cacheKey = key(jobId, safeOffset, safePageSize);
    const cached = entries.get(cacheKey);
    if (cached) {
      entries.delete(cacheKey);
      entries.set(cacheKey, cached);
      return cached.value;
    }

    const pending = inflight.get(cacheKey);
    if (pending) return pending;

    const request = Promise.resolve(fetcher(jobId, {
      offset: safeOffset,
      limit: safePageSize,
      signal,
    })).then((page) => {
      const normalized = page && typeof page === "object" ? page : {};
      touch(cacheKey, normalized);
      return normalized;
    }).finally(() => {
      inflight.delete(cacheKey);
    });

    inflight.set(cacheKey, request);
    return request;
  }

  function invalidate(jobId) {
    const prefix = `${String(jobId)}:`;
    for (const cacheKey of entries.keys()) {
      if (cacheKey.startsWith(prefix)) {
        const entry = entries.get(cacheKey);
        cachedBytes = Math.max(0, cachedBytes - (entry?.bytes || 0));
        entries.delete(cacheKey);
      }
    }
  }

  function clear() {
    entries.clear();
    cachedBytes = 0;
  }

  function bytes() {
    return cachedBytes;
  }

  function size() {
    return entries.size;
  }

  return { get, invalidate, clear, size, bytes };
}
