import { createRequestCoordinator } from "./requestCoordinator.js";
import { API, apiFetch } from "./authClient.js";

const DEFAULT_POLL_MS = 250;
const DEFAULT_TIMEOUT_MS = 0;

const executionRequestCoordinator = createRequestCoordinator();

export function createExecutionRequestCoordinator(options) {
  return createRequestCoordinator(options);
}

function extractError(data, status) {
  const detail = Array.isArray(data?.detail)
    ? data.detail.map((item) => typeof item === "string" ? item : item?.msg || item?.message || item?.detail || JSON.stringify(item)).join("; ")
    : typeof data?.detail === "object"
      ? data.detail?.msg || data.detail?.message || data.detail?.detail || JSON.stringify(data.detail)
      : data?.detail;
  return data?.message || detail || `Execution request failed with HTTP ${status}.`;
}

async function readJson(response) {
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`The execution API returned an invalid response (HTTP ${response.status}).`);
  }
  if (!response.ok || data?.success === false) {
    throw new Error(extractError(data, response.status));
  }
  return data;
}

export async function submitExecutionJob(payload) {
  const response = await apiFetch(`${API}/execution/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await readJson(response);
  if (!data?.job_id) throw new Error("The execution API did not return a job id.");
  return data.job_id;
}

export async function waitForExecutionJob(jobId, {
  pollMs = DEFAULT_POLL_MS,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  pageSize = 5000,
  loadAll = false,
  returnOnFirstPage = false,
  onProgress,
  signal,
} = {}) {
  const started = Date.now();
  while (timeoutMs <= 0 || Date.now() - started < timeoutMs) {
    if (signal?.aborted) throw new DOMException("The export request was aborted.", "AbortError");
    const response = await apiFetch(`${API}/execution/jobs/${encodeURIComponent(jobId)}`, {
      headers: { Accept: "application/json" },
      signal,
    });
    const data = await readJson(response);
    const job = data?.job;
    if (!job) throw new Error("The execution API returned no job information.");
    if (typeof onProgress === "function") onProgress(job);

    if ((job.status === "running" || job.status === "completed") && returnOnFirstPage && job.result_available) {
      const safePageSize = Math.max(1, Number(pageSize) || Number(job.result_page_size) || 5000);
      const pageResponse = await apiFetch(
        `${API}/execution/jobs/${encodeURIComponent(jobId)}/result?offset=0&limit=${safePageSize}`,
        { headers: { Accept: "application/json" }, signal },
      );
      const pageData = await readJson(pageResponse);
      const pageRows = Array.isArray(pageData?.rows) ? pageData.rows : [];
      if (pageRows.length > 0 || job.status === "completed") {
        return {
          success: true,
          rows: pageRows,
          columns: Array.isArray(pageData?.columns) && pageData.columns.length ? pageData.columns : (Array.isArray(job.columns) ? job.columns : []),
          total_rows: Math.max(0, Number(pageData?.total_rows ?? job.result_row_count ?? 0) || 0),
          returned_rows: pageRows.length,
          page_offset: 0,
          page_size: safePageSize,
          has_more: Boolean(pageData?.has_more),
          execution_status: job.status,
          execution_in_progress: job.status !== "completed",
        };
      }
    }

    if (job.status === "completed") {
      if (job.result) {
        return job.result;
      }

      if (job.result_available) {
        const safePageSize = Math.max(1, Number(pageSize) || Number(job.result_page_size) || 5000);
        const totalRows = Math.max(0, Number(job.result_row_count) || 0);
        const rows = [];
        let offset = 0;
        let columns = Array.isArray(job.columns) ? job.columns : [];

        // Large results are page-backed at the API boundary. Only callers that
        // explicitly opt into loadAll may materialize the complete result in
        // the browser. This keeps the default UI independent of dataset size.
        do {
          const pageResponse = await apiFetch(
            `${API}/execution/jobs/${encodeURIComponent(jobId)}/result?offset=${offset}&limit=${safePageSize}`,
            { headers: { Accept: "application/json" } },
          );
          const pageData = await readJson(pageResponse);
          const pageRows = Array.isArray(pageData?.rows) ? pageData.rows : [];
          if (Array.isArray(pageData?.columns) && pageData.columns.length) columns = pageData.columns;
          rows.push(...pageRows);
          offset += pageRows.length;
          if (!loadAll || !pageData?.has_more || pageRows.length === 0) {
            return {
              success: true,
              rows,
              columns,
              total_rows: totalRows,
              returned_rows: rows.length,
              page_offset: 0,
              page_size: safePageSize,
              has_more: Boolean(pageData?.has_more),
            };
          }
        } while (offset < totalRows);

        return { success: true, rows, columns, total_rows: totalRows, returned_rows: rows.length, has_more: false };
      }

      return { success: true, rows: [], columns: [] };
    }
    if (job.status === "failed" || job.status === "cancelled") {
      throw new Error(job.error || `Report execution ${job.status}.`);
    }
    await new Promise((resolve, reject) => {
      if (signal?.aborted) { reject(new DOMException("The execution request was aborted.", "AbortError")); return; }
      const timer = setTimeout(resolve, pollMs);
      signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("The execution request was aborted.", "AbortError")); }, { once: true });
    });
  }
  throw new Error(`Report execution timed out after ${Math.round(timeoutMs / 1000)} seconds.`);
}

export async function executeReportJob(payload, options) {
  const jobId = await submitExecutionJob(payload);
  const result = await waitForExecutionJob(jobId, options);
  return { jobId, result };
}

export async function transformExecutionJob(jobId, operations = {}, options = {}) {
  const response = await apiFetch(
    `${API}/execution/jobs/${encodeURIComponent(jobId)}/transform`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(operations),
      signal: options.signal,
    },
  );
  const data = await readJson(response);
  if (!data?.job_id) throw new Error("The execution transform API did not return a job id.");
  try {
    const result = await waitForExecutionJob(data.job_id, { ...options });
    return { jobId: data.job_id, sourceJobId: jobId, result };
  } catch (error) {
    if (error?.name === "AbortError") {
      // Aborting the browser request alone would leave the server worker alive.
      // Best-effort backend cancellation keeps obsolete interactive transforms
      // from consuming execution capacity.
      try { await cancelExecutionJob(data.job_id); } catch { /* cancellation is best effort */ }
    }
    throw error;
  }
}


export async function cancelExecutionJob(jobId) {
  const response = await apiFetch(
    `${API}/execution/jobs/${encodeURIComponent(jobId)}/cancel`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
  return readJson(response);
}

export async function fetchExecutionJobResultPage(jobId, { offset = 0, limit = 5000, signal, coordinator = executionRequestCoordinator } = {}) {
  const safeOffset = Math.max(0, Number(offset) || 0);
  const safeLimit = Math.max(1, Number(limit) || 5000);
  const key = `result:${jobId}:${safeOffset}:${safeLimit}`;
  return coordinator.request(key, async ({ signal: coordinatedSignal }) => {
    const response = await apiFetch(
      `${API}/execution/jobs/${encodeURIComponent(jobId)}/result?offset=${safeOffset}&limit=${safeLimit}`,
      { headers: { Accept: "application/json" }, signal: coordinatedSignal },
    );
    return readJson(response);
  }, { signal });
}

export async function downloadExecutionJobExport(jobId, format, filename = "report", options = {}) {
  const normalizedFormat = String(format || "").toLowerCase();
  if (!["csv", "json"].includes(normalizedFormat)) {
    throw new Error("Unsupported export format.");
  }
  return runExecutionExportJob(jobId, normalizedFormat, filename, options);
}

export async function createExecutionExportJob(jobId, format, filename = "report") {
  const normalizedFormat = String(format || "").toLowerCase();
  if (!["csv", "json", "xlsx", "pdf", "package"].includes(normalizedFormat)) {
    throw new Error("Unsupported export format.");
  }
  const query = new URLSearchParams({
    format: normalizedFormat,
    filename: String(filename || "report").trim() || "report",
  });
  const response = await apiFetch(
    `${API}/execution/jobs/${encodeURIComponent(jobId)}/export?${query.toString()}`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
  return readJson(response);
}

export async function waitForExecutionExport(exportId, {
  pollMs = DEFAULT_POLL_MS,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  onProgress,
  signal,
} = {}) {
  const started = Date.now();
  while (timeoutMs <= 0 || Date.now() - started < timeoutMs) {
    const response = await apiFetch(
      `${API}/execution/exports/${encodeURIComponent(exportId)}`,
      { headers: { Accept: "application/json" } },
    );
    const data = await readJson(response);
    const job = data?.export;
    if (!job) throw new Error("The export API returned no job information.");
    if (typeof onProgress === "function") {
      onProgress(job);
    }
    if (job.status === "completed") return job;
    if (job.status === "failed" || job.status === "cancelled") {
      throw new Error(job.error || `Export ${job.status}.`);
    }
    await new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, pollMs);
      signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("The export request was aborted.", "AbortError")); }, { once: true });
    });
  }
  throw new Error(`Export timed out after ${Math.round(timeoutMs / 1000)} seconds.`);
}


export async function cancelExecutionExportJob(exportId) {
  const response = await apiFetch(
    `${API}/execution/exports/${encodeURIComponent(exportId)}/cancel`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
  return readJson(response);
}

export async function runExecutionExportJob(jobId, format, filename = "report", options = {}) {
  const created = await createExecutionExportJob(jobId, format, filename);
  const exportId = created?.export_id || created?.export?.id || created?.id;
  if (!exportId) throw new Error("The export API returned no export job id.");
  const job = await waitForExecutionExport(exportId, options);
  await downloadExecutionExportJob(exportId);
  return job;
}
export async function downloadExecutionExportJob(exportId) {
  const response = await apiFetch(
    `${API}/execution/exports/${encodeURIComponent(exportId)}/download`,
    { headers: { Accept: "*/*" } },
  );
  if (!response.ok) {
    let message = `Export download failed with HTTP ${response.status}.`;
    try {
      message = extractError(await response.json(), response.status);
    } catch {
      // Keep HTTP fallback.
    }
    throw new Error(message);
  }

  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const downloadName = match?.[1] || "report";

  if (window.showSaveFilePicker && response.body) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: downloadName,
      });
      const writable = await handle.createWritable();
      await response.body.pipeTo(writable);
      return { filename: downloadName };
    } catch (error) {
      if (error?.name === "AbortError") throw error;
      // Fall back to the browser download path when direct file streaming is unavailable.
    }
  }

  const blob = await response.blob();
  if (!blob.size) throw new Error("The server returned an empty export.");
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = downloadName;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return { filename: downloadName, size: blob.size };
}
