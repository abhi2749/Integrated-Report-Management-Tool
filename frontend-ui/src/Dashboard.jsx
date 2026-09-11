import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API, apiFetch } from "./authClient";
import {
  VISUALIZATION_TYPES,
  columnsFromResult,
  createVisualization,
  normalizeVisualizationCollection,
  rowsFromResult,
  visualizationLabel,
} from "./visualizationEngine";
import { distinctValues, FILTER_OPERATORS, filterSummary } from "./dashboardInteractionEngine";
import { fetchExecutionJobResultPage, downloadExecutionJobExport, transformExecutionJob } from "./executionClient";
import { VisualizationRenderer } from "./dashboardWidgets";
const DASHBOARD_STORAGE_KEY = "crt_dashboard_layout_v2";
const LEGACY_STORAGE_KEY = "crt_dashboard_layout_v1";
const GRID_COLUMNS = 12;

const CSS = `
.db-root{max-width:1500px;margin:0 auto;padding:24px 28px 40px;box-sizing:border-box;color:#172033}
.db-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;margin-bottom:18px}.db-kicker{font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#175cd3;margin-bottom:5px}.db-head h2{margin:0;font-size:24px}.db-head p{margin:6px 0 0;color:#667085;font-size:12px}.db-actions{display:flex;gap:8px;flex-wrap:wrap}.db-btn{min-height:36px;padding:0 12px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;color:#344054;font-size:11px;font-weight:750;cursor:pointer}.db-btn.primary{background:#175cd3;border-color:#175cd3;color:#fff}.db-btn.danger{color:#b42318;border-color:#f0b7b7}.db-btn:disabled{opacity:.5;cursor:not-allowed}
.db-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:12px;border:1px solid #e4e7ec;border-radius:10px;background:#fff;margin-bottom:16px}.db-note{font-size:10px;color:#667085;margin-left:auto}.db-filterbar{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap;padding:12px;border:1px solid #e4e7ec;border-radius:10px;background:#fff;margin-bottom:16px}.db-filterbar label{font-size:9px;color:#667085;font-weight:700}.db-filterbar select,.db-filterbar input{height:32px;box-sizing:border-box;margin-top:4px;border:1px solid #d0d5dd;border-radius:7px;background:#fff;padding:0 8px;font-size:10px}.db-filter-meta{font-size:9px;color:#667085;padding:5px 0}.db-status{font-size:9px;color:#667085}.db-empty{padding:60px 24px;border:1px dashed #d0d5dd;border-radius:12px;background:#fff;text-align:center;color:#667085}.db-empty strong{display:block;color:#344054;font-size:14px;margin-bottom:5px}.db-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));grid-auto-rows:minmax(190px,auto);gap:14px;align-items:stretch}.db-card{position:relative;min-width:0;border:1px solid #e4e7ec;border-radius:12px;background:#fff;overflow:hidden;box-shadow:0 2px 8px rgba(16,24,40,.04);display:flex;flex-direction:column}.db-card.dragging{opacity:.55}.db-card.drop-target{outline:2px dashed #84adff;outline-offset:2px}.db-card-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:11px 13px;border-bottom:1px solid #eef2f6;cursor:grab}.db-card-head:active{cursor:grabbing}.db-card-head strong{font-size:11px;color:#344054}.db-card-head span{font-size:9px;color:#98a2b3}.db-card-actions{display:flex;gap:5px}.db-icon-btn{width:26px;height:26px;border:1px solid #e4e7ec;border-radius:6px;background:#fff;cursor:pointer;color:#667085}.db-icon-btn:disabled{opacity:.4;cursor:not-allowed}.db-kpi{display:flex;align-items:center;justify-content:center;min-height:120px}.db-kpi strong{font-size:30px;color:#101828}.db-kpi span{display:block;margin-top:4px;font-size:10px;color:#667085;text-align:center}.db-table-wrap{overflow:auto;max-height:360px}.db-table{width:100%;border-collapse:collapse;font-size:10px}.db-table th,.db-table td{padding:7px 8px;border-bottom:1px solid #eef2f6;text-align:left;white-space:nowrap}.db-table th{position:sticky;top:0;background:#f8fafc;color:#475467}.db-chart{width:100%;min-height:190px}.db-chart svg{width:100%;height:190px;display:block}.db-config{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:12px;background:#f8fafc;border-top:1px solid #eef2f6}.db-config label{font-size:9px;color:#667085;font-weight:700}.db-config select,.db-config input{width:100%;box-sizing:border-box;height:32px;margin-top:4px;border:1px solid #d0d5dd;border-radius:7px;background:#fff;padding:0 8px;font-size:10px}.db-position{font-size:9px;color:#98a2b3;padding:7px 13px;border-top:1px solid #f2f4f7;background:#fcfcfd}.db-drop-hint{padding:6px 9px;border-radius:7px;background:#f2f4f7;color:#667085;font-size:9px}.db-col-12{grid-column:span 12}.db-col-6{grid-column:span 6}.db-col-4{grid-column:span 4}.db-col-3{grid-column:span 3}.db-h-1{grid-row:span 1}\n@media print{.db-actions,.db-filterbar,.db-config,.db-position,.db-note,.db-drop-hint{display:none!important}.db-root{max-width:none;padding:10px}.db-grid{gap:8px}.db-card{break-inside:avoid;box-shadow:none}}.db-h-2{grid-row:span 2}.db-h-3{grid-row:span 3}
@media(max-width:900px){.db-col-6,.db-col-4,.db-col-3{grid-column:span 12}.db-head{display:block}.db-actions{margin-top:12px}.db-note{margin-left:0}.db-config{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.db-root{padding:18px 14px 30px}.db-config{grid-template-columns:1fr}}
`;

function loadWidgets() {
  try {
    const current = JSON.parse(localStorage.getItem(DASHBOARD_STORAGE_KEY) || "null");
    if (Array.isArray(current)) return normalizeVisualizationCollection(current);
    const legacy = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY) || "[]");
    return normalizeVisualizationCollection(legacy);
  } catch {
    return [];
  }
}



export default function Dashboard({ result, initialDashboard = null, onOpenDataSources, onOpenDataPreview, onOpenReportBuilder }) {
  const [widgets, setWidgets] = useState(() => {
    const saved = initialDashboard?.definition?.widgets;
    return Array.isArray(saved)
      ? normalizeVisualizationCollection(saved)
      : loadWidgets();
  });
  const [editingId, setEditingId] = useState("");
  const [draggedId, setDraggedId] = useState("");
  const [dropTargetId, setDropTargetId] = useState("");
  const [filterDraft, setFilterDraft] = useState({ field: "", operator: FILTER_OPERATORS.EQUALS, value: "" });
  const [filters, setFilters] = useState(() => (
    Array.isArray(initialDashboard?.definition?.filters)
      ? initialDashboard.definition.filters
      : []
  ));
  const [currentDashboardId, setCurrentDashboardId] = useState(
    () => initialDashboard?.id || ""
  );
  const [dashboardName, setDashboardName] = useState(
    () => initialDashboard?.name || ""
  );
  const [dashboardAccessList, setDashboardAccessList] = useState([]);
  const [shareUsername, setShareUsername] = useState("");
  const [sharePanelOpen, setSharePanelOpen] = useState(false);
  const [loadedExecutionResult, setLoadedExecutionResult] = useState(null);
  const [filterLoading, setFilterLoading] = useState(false);
  const [filterMessage, setFilterMessage] = useState("");
  const filterControllerRef = useRef(null);
  const initialFilterAppliedRef = useRef(false);
  const baseExecutionJobIdRef = useRef("");
  const propExecutionJobId = result?.execution_job_id || initialDashboard?.definition?.execution_job_id || "";

  const baseExecutionJobId = result?.execution_job_id || initialDashboard?.definition?.execution_job_id || "";

  useEffect(() => {
    baseExecutionJobIdRef.current = baseExecutionJobId;
    filterControllerRef.current?.abort();
    filterControllerRef.current = null;
    initialFilterAppliedRef.current = false;
  }, [baseExecutionJobId]);

  useEffect(() => {
    let cancelled = false;
    async function loadSavedExecutionPreview() {
      if (result || !propExecutionJobId) return;
      try {
        const page = await fetchExecutionJobResultPage(propExecutionJobId, { offset: 0, limit: 5000 });
        if (cancelled || !page?.success) return;
        setLoadedExecutionResult({
          success: true,
          execution_job_id: propExecutionJobId,
          columns: Array.isArray(page.columns) ? page.columns : [],
          rows: Array.isArray(page.rows) ? page.rows : [],
          total_rows: Number(page.total_rows ?? page.rows?.length ?? 0) || 0,
          returned_rows: Number(page.returned_rows ?? page.rows?.length ?? 0) || 0,
          page_offset: Number(page.offset ?? 0) || 0,
          page_size: Number(page.limit ?? page.rows?.length ?? 0) || 0,
          has_more: Boolean(page.has_more),
          source_base_job_id: propExecutionJobId,
        });
      } catch {
        // Keep the empty state; the saved dashboard definition is still usable.
      }
    }
    void loadSavedExecutionPreview();
    return () => { cancelled = true; };
  }, [result, propExecutionJobId]);

  const effectiveResult = useMemo(() => {
    const loadedForCurrentBase = loadedExecutionResult?.source_base_job_id === baseExecutionJobId;
    return (loadedForCurrentBase ? loadedExecutionResult : null) || result || {};
  }, [baseExecutionJobId, result, loadedExecutionResult]);
  const columns = useMemo(() => columnsFromResult(effectiveResult), [effectiveResult]);
  const sourceRows = useMemo(() => rowsFromResult(effectiveResult), [effectiveResult]);
  const executionJobId = effectiveResult?.execution_job_id || propExecutionJobId;
  const totalResultRows = Number(effectiveResult?.total_rows ?? sourceRows.length) || 0;
  // Do not truncate the logical result in the dashboard. Large tables are rendered
  // through viewport virtualization below, while charts intentionally summarize
  // their loaded result rather than imposing a dataset-access ceiling.
  const rows = sourceRows;
  const filteredRows = rows;
  const filterValues = useMemo(() => distinctValues(rows, filterDraft.field), [rows, filterDraft.field]);

  useEffect(() => {
    localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify(widgets));
  }, [widgets]);

  const runDashboardFilters = useCallback(async (nextFilters, successMessage) => {
    const baseJobId = baseExecutionJobIdRef.current || propExecutionJobId;
    if (!baseJobId) {
      setFilterMessage("Run the report before applying dashboard filters. Server-side filtering requires an execution job.");
      return null;
    }

    filterControllerRef.current?.abort();
    const controller = new AbortController();
    filterControllerRef.current = controller;
    setFilterLoading(true);
    setFilterMessage("");
    try {
      const serverFilters = (Array.isArray(nextFilters) ? nextFilters : [])
        .filter((item) => item?.field && String(item.value ?? "").trim() !== "")
        .map((item) => ({
          field: item.field,
          operator: ({ contains: "CONTAINS", equals: "=", not_equals: "!=", gt: ">", gte: ">=", lt: "<", lte: "<=" })[item.operator] || "=",
          value: item.value,
          logic: "AND",
        }));

      if (!serverFilters.length) {
        const page = await fetchExecutionJobResultPage(baseJobId, { offset: 0, limit: 5000, signal: controller.signal });
        if (!page?.success) throw new Error(page?.message || "Unable to restore the dashboard result.");
        const restored = {
          success: true, execution_job_id: baseJobId,
          columns: Array.isArray(page.columns) ? page.columns : [],
          rows: Array.isArray(page.rows) ? page.rows : [],
          total_rows: Number(page.total_rows ?? page.rows?.length ?? 0) || 0,
          returned_rows: Number(page.returned_rows ?? page.rows?.length ?? 0) || 0,
          page_offset: Number(page.offset ?? 0) || 0,
          page_size: Number(page.limit ?? page.rows?.length ?? 0) || 0,
          has_more: Boolean(page.has_more),
          source_base_job_id: baseJobId,
        };
        setLoadedExecutionResult(restored);
        setFilterMessage(successMessage || "Dashboard filters cleared.");
        return restored;
      }

      const { jobId, result: nextResult } = await transformExecutionJob(baseJobId, { filters: serverFilters }, {
        loadAll: false, pageSize: 5000, returnOnFirstPage: true, signal: controller.signal,
      });
      const normalized = {
        ...nextResult, execution_job_id: jobId,
        applied_filters: nextFilters,
        source_base_job_id: baseJobId,
      };
      setLoadedExecutionResult(normalized);
      setFilterMessage(successMessage || "Dashboard filters executed server-side. Only the result page is loaded into the browser.");
      return normalized;
    } catch (error) {
      if (error?.name !== "AbortError") setFilterMessage(`Dashboard filter failed: ${error.message}`);
      return null;
    } finally {
      if (filterControllerRef.current === controller) {
        filterControllerRef.current = null;
        setFilterLoading(false);
      }
    }
  }, [propExecutionJobId]);

  useEffect(() => {
    const savedFilters = Array.isArray(initialDashboard?.definition?.filters)
      ? initialDashboard.definition.filters
      : [];
    if (result || !propExecutionJobId || !savedFilters.length || initialFilterAppliedRef.current) return;
    initialFilterAppliedRef.current = true;
    void runDashboardFilters(savedFilters, "Saved dashboard filters executed server-side.");
  }, [result, propExecutionJobId, initialDashboard, runDashboardFilters]);

  const addFilter = async () => {
    const field = filterDraft.field || columns[0] || "";
    if (!field || !String(filterDraft.value ?? "").trim() || !propExecutionJobId) return;
    const nextFilters = [...filters, { ...filterDraft, field, value: String(filterDraft.value) }];
    const nextResult = await runDashboardFilters(nextFilters, "Dashboard filter executed server-side. Only the result page is loaded into the browser.");
    if (nextResult) setFilters(nextFilters);
  };
  const clearFilters = async () => {
    const nextResult = await runDashboardFilters([], "Dashboard filters cleared. Base execution result restored.");
    if (nextResult) setFilters([]);
  };

  const addWidget = (type) => {
    if (!columns.length) return;
    setWidgets((current) => [...current, createVisualization(type, columns)]);
  };
  const updateWidget = (id, patch) => setWidgets((current) => current.map((widget) => widget.id === id ? { ...widget, ...patch } : widget));
  const removeWidget = (id) => setWidgets((current) => current.filter((widget) => widget.id !== id));
  const moveWidget = (id, direction) => setWidgets((current) => {
    const index = current.findIndex((widget) => widget.id === id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= current.length) return current;
    const next = [...current];
    [next[index], next[target]] = [next[target], next[index]];
    return next;
  });
  const handleDrop = (targetId) => {
    if (!draggedId || draggedId === targetId) {
      setDraggedId(""); setDropTargetId(""); return;
    }
    setWidgets((current) => {
      const from = current.findIndex((widget) => widget.id === draggedId);
      const to = current.findIndex((widget) => widget.id === targetId);
      if (from < 0 || to < 0) return current;
      const next = [...current];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
    setDraggedId(""); setDropTargetId("");
  };
  const clearDashboard = () => { setWidgets([]); setFilters([]); setCurrentDashboardId(""); setDashboardName(""); localStorage.removeItem(DASHBOARD_STORAGE_KEY); localStorage.removeItem(LEGACY_STORAGE_KEY); };
  const saveDashboard = async () => {
    const name = dashboardName.trim();
    if (!name) return window.alert("Enter a dashboard name before saving.");
    const id = currentDashboardId || (globalThis.crypto?.randomUUID?.() || `dash_${Date.now()}`);
    const definition = { widgets, filters, execution_job_id: executionJobId || null };
    try {
      const response = await apiFetch(`${API}/dashboards`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id, name, definition }) });
      let body = null;
      try { body = await response.json(); } catch { body = null; }
      if (!response.ok || !body?.success) {
        throw new Error(body?.message || `Unable to save dashboard (HTTP ${response.status}).`);
      }
      setCurrentDashboardId(body.dashboard.id);
      localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify(widgets));
      window.alert("Dashboard saved successfully. Manage it from Saved Dashboards.");
    } catch (error) { window.alert(error?.message || "Unable to save dashboard."); }
  };

  const loadDashboardAccess = async () => {
    if (!currentDashboardId) return;
    try {
      const response = await apiFetch(`${API}/dashboards/${encodeURIComponent(currentDashboardId)}/shares`);
      const body = await response.json();
      if (!response.ok || !body?.success) throw new Error(body?.message || "Unable to load dashboard shares.");
      setDashboardAccessList(body.shares || []);
    } catch (error) { window.alert(error?.message || "Unable to load dashboard shares."); }
  };

  const shareDashboard = async () => {
    if (!currentDashboardId) return window.alert("Save the dashboard before sharing it.");
    const username = shareUsername.trim();
    if (!username) return;
    try {
      const response = await apiFetch(`${API}/dashboards/${encodeURIComponent(currentDashboardId)}/shares`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username }) });
      const body = await response.json();
      if (!response.ok || !body?.success) throw new Error(body?.message || "Unable to share dashboard.");
      setDashboardAccessList(body.shares || []);
      setShareUsername("");
    } catch (error) { window.alert(error?.message || "Unable to share dashboard."); }
  };

  const removeDashboardShare = async (share) => {
    if (!currentDashboardId || !window.confirm(`Remove dashboard access for ${share.shared_with_username}?`)) return;
    try {
      const response = await apiFetch(`${API}/dashboards/${encodeURIComponent(currentDashboardId)}/shares/${encodeURIComponent(share.shared_with_id)}`, { method: "DELETE" });
      const body = await response.json();
      if (!response.ok || !body?.success) throw new Error(body?.message || "Unable to remove dashboard share.");
      setDashboardAccessList((current) => current.filter((item) => item.shared_with_id !== share.shared_with_id));
    } catch (error) { window.alert(error?.message || "Unable to remove dashboard share."); }
  };

  const downloadDashboard = async (format) => {
    const hasResult = Boolean(columns.length || sourceRows.length || executionJobId);
    if (format !== "json" && !hasResult) return window.alert("Run the report before exporting dashboard data.");

    try {
      // Data exports use the execution job so they contain the complete result,
      // independently of the dashboard's virtualized rendering window.
      if (executionJobId && (format === "csv" || format === "json")) {
        await downloadExecutionJobExport(executionJobId, format, dashboardName.trim() || "dashboard");
        return;
      }

      const endpoint = currentDashboardId
        ? `${API}/dashboards/${encodeURIComponent(currentDashboardId)}/export/${format}`
        : `${API}/dashboards/export/${format}`;
      const options = currentDashboardId ? undefined : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: dashboardName.trim() || "Dashboard",
          definition: { widgets, filters, execution_job_id: executionJobId || null },
          result: {
            ...(effectiveResult || {}),
            columns,
            rows,
            total_rows: totalResultRows,
            execution_job_id: executionJobId || null,
          },
        }),
      };
      const response = await apiFetch(endpoint, options);
      if (!response.ok) {
        let message = "Unable to export dashboard.";
        try { const body = await response.json(); message = body?.message || body?.detail || message; } catch { /* non-JSON error */ }
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${dashboardName.trim() || "dashboard"}.${format === "package" ? "zip" : format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { window.alert(error?.message || "Unable to export dashboard."); }
  };

  const printDashboard = () => {
    window.print();
  };

  return <>
    <style>{CSS}</style>
    <section className="db-root">
      <div className="db-head">
        <div><div className="db-kicker">Presentation workspace</div><h2>Dashboard</h2><p>Compose a responsive canvas from the same reporting result used by Report Builder.</p></div>
        <div className="db-actions">
          <button className="db-btn" type="button" onClick={onOpenDataSources}>Data &amp; Query</button>
          <button className="db-btn" type="button" onClick={onOpenDataPreview}>Data Preview</button>
          <button className="db-btn" type="button" onClick={onOpenReportBuilder}>Report View</button>
          <button className="db-btn" type="button" onClick={() => addWidget(VISUALIZATION_TYPES.KPI)} disabled={!columns.length}>+ KPI</button>
          <button className="db-btn" type="button" onClick={() => addWidget(VISUALIZATION_TYPES.TABLE)} disabled={!columns.length}>+ Table</button>
          <button className="db-btn" type="button" onClick={() => addWidget(VISUALIZATION_TYPES.BAR)} disabled={!columns.length}>+ Bar</button>
          <button className="db-btn" type="button" onClick={() => addWidget(VISUALIZATION_TYPES.LINE)} disabled={!columns.length}>+ Line</button>
          <button className="db-btn" type="button" onClick={() => addWidget(VISUALIZATION_TYPES.PIE)} disabled={!columns.length}>+ Pie</button>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 190, fontSize: 9, color: "#667085", fontWeight: 700 }}>Dashboard name<input value={dashboardName} onChange={(event) => setDashboardName(event.target.value)} placeholder="Enter dashboard name" maxLength={200} style={{ height: 36, boxSizing: "border-box", border: "1px solid #d0d5dd", borderRadius: 8, background: "#fff", padding: "0 10px", fontSize: 11, fontWeight: 500, color: "#344054" }} aria-label="Dashboard name" /></label>
          <button className="db-btn primary" type="button" onClick={saveDashboard} disabled={!dashboardName.trim()}>Save Dashboard</button>
          <button className="db-btn" type="button" onClick={printDashboard} disabled={!columns.length}>Print</button>
          <span className="db-drop-hint">Saved dashboard management: use Saved Dashboards</span>
          <button className="db-btn" type="button" onClick={() => { setSharePanelOpen((open) => !open); if (!sharePanelOpen) void loadDashboardAccess(); }} disabled={!currentDashboardId}>Share</button>
          <button className="db-btn" type="button" onClick={() => downloadDashboard("json")} disabled={!widgets.length && !dashboardName.trim()}>Export JSON</button>
          <button className="db-btn" type="button" onClick={() => downloadDashboard("csv")} disabled={!result?.columns?.length && !result?.rows?.length}>Export CSV</button>
          <button className="db-btn" type="button" onClick={() => downloadDashboard("xlsx")} disabled={!result?.columns?.length && !result?.rows?.length}>Export Excel</button>
          <button className="db-btn" type="button" onClick={() => downloadDashboard("pdf")} disabled={!result?.columns?.length && !result?.rows?.length}>Export PDF</button>
          <button className="db-btn primary" type="button" onClick={() => downloadDashboard("package")} disabled={!result?.columns?.length && !result?.rows?.length}>Download Package</button>
          <button className="db-btn danger" type="button" onClick={clearDashboard} disabled={!widgets.length}>Clear</button>
        </div>
      </div>
      {!columns.length ? <div className="db-empty"><strong>No report result loaded</strong><span>Run a report from Report Builder or Join Designer first, then open Dashboard to compose the presentation.</span></div> : <>
        <div className="db-toolbar"><strong style={{ fontSize: 11 }}>{filteredRows.length.toLocaleString()} / {totalResultRows.toLocaleString()} rows · {columns.length} columns · {widgets.length} widgets</strong><span className="db-drop-hint">Dashboard tables use virtualized rendering. Data exports use the complete execution job.</span><span className="db-status">{executionJobId ? `Execution job: ${executionJobId}` : "Current report result"}</span><span className="db-note">{totalResultRows > rows.length ? `Loaded ${rows.length.toLocaleString()} of ${totalResultRows.toLocaleString()} result rows.` : "Dashboard filters apply to the loaded result."}</span></div>
        {currentDashboardId && sharePanelOpen && <div className="db-toolbar" style={{ alignItems: "flex-end" }}><div style={{ display: "flex", flexDirection: "column", gap: 4 }}><strong style={{ fontSize: 11 }}>Share dashboard</strong><span className="db-status">Grant another registered user access to view this saved dashboard.</span></div><label style={{ fontSize: 9, color: "#667085", fontWeight: 700 }}>Username<input value={shareUsername} onChange={(event) => setShareUsername(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void shareDashboard(); }} placeholder="Enter username" maxLength={100} style={{ display: "block", marginTop: 4, height: 32, minWidth: 190, border: "1px solid #d0d5dd", borderRadius: 7, padding: "0 8px", boxSizing: "border-box" }} /></label><button className="db-btn primary" type="button" onClick={shareDashboard} disabled={!shareUsername.trim()}>Grant Access</button><button className="db-btn" type="button" onClick={loadDashboardAccess}>Refresh</button><button className="db-btn" type="button" onClick={() => setSharePanelOpen(false)}>Close</button>{dashboardAccessList.length ? <div style={{ width: "100%", display: "flex", gap: 7, flexWrap: "wrap" }}><strong style={{ fontSize: 10 }}>Current access:</strong>{dashboardAccessList.map((share) => <span key={share.shared_with_id} className="db-drop-hint">{share.shared_with_username} <button className="db-icon-btn" type="button" onClick={() => removeDashboardShare(share)} aria-label={`Remove ${share.shared_with_username}`}>×</button></span>)}</div> : <span className="db-status">No users currently have explicit shared access.</span>}</div>}
        <div className="db-filterbar">
          <label>Filter field<select value={filterDraft.field || columns[0] || ""} onChange={(event) => setFilterDraft((current) => ({ ...current, field: event.target.value, value: "" }))}>{columns.map((column) => <option key={column}>{column}</option>)}</select></label>
          <label>Operator<select value={filterDraft.operator} onChange={(event) => setFilterDraft((current) => ({ ...current, operator: event.target.value }))}><option value={FILTER_OPERATORS.EQUALS}>Equals</option><option value={FILTER_OPERATORS.NOT_EQUALS}>Not equals</option><option value={FILTER_OPERATORS.CONTAINS}>Contains</option><option value={FILTER_OPERATORS.GT}>Greater than</option><option value={FILTER_OPERATORS.GTE}>Greater/equal</option><option value={FILTER_OPERATORS.LT}>Less than</option><option value={FILTER_OPERATORS.LTE}>Less/equal</option></select></label>
          <label>Value{filterValues.length && [FILTER_OPERATORS.EQUALS, FILTER_OPERATORS.NOT_EQUALS].includes(filterDraft.operator) ? <select value={filterDraft.value} onChange={(event) => setFilterDraft((current) => ({ ...current, value: event.target.value }))}><option value="">Select…</option>{filterValues.map((value) => <option key={value} value={value}>{value || "(blank)"}</option>)}</select> : <input value={filterDraft.value} onChange={(event) => setFilterDraft((current) => ({ ...current, value: event.target.value }))} placeholder="Filter value" />}</label>
          <button className="db-btn primary" type="button" onClick={() => void addFilter()} disabled={filterLoading || !propExecutionJobId || !(filterDraft.field || columns[0]) || !String(filterDraft.value ?? "").trim()}>{filterLoading ? "Applying…" : "Apply Filter"}</button>
          <button className="db-btn" type="button" onClick={() => void clearFilters()} disabled={filterLoading || !filters.length || !propExecutionJobId}>Clear Filters</button>
          <span className="db-filter-meta">{filterMessage || (filters.length ? filterSummary(filters) : "No dashboard filters applied")}</span>
        </div>
        <div className="db-grid">
          {widgets.map((widget, index) => <article key={widget.id} draggable className={`db-card db-col-${widget.span || 6} db-h-${widget.height || 1}${draggedId === widget.id ? " dragging" : ""}${dropTargetId === widget.id ? " drop-target" : ""}`} onDragStart={() => setDraggedId(widget.id)} onDragOver={(event) => { event.preventDefault(); if (draggedId !== widget.id) setDropTargetId(widget.id); }} onDragLeave={() => setDropTargetId("")} onDrop={() => handleDrop(widget.id)} onDragEnd={() => { setDraggedId(""); setDropTargetId(""); }}>
            <div className="db-card-head">
              <div><strong>{widget.title}</strong><span> · {visualizationLabel(widget.type)}</span></div>
              <div className="db-card-actions">
                <button className="db-icon-btn" type="button" onClick={() => moveWidget(widget.id, -1)} disabled={index === 0} aria-label="Move widget up">↑</button>
                <button className="db-icon-btn" type="button" onClick={() => moveWidget(widget.id, 1)} disabled={index === widgets.length - 1} aria-label="Move widget down">↓</button>
                <button className="db-icon-btn" type="button" onClick={() => setEditingId(editingId === widget.id ? "" : widget.id)} aria-label="Configure widget">⚙</button>
                <button className="db-icon-btn" type="button" onClick={() => removeWidget(widget.id)} aria-label="Remove widget">×</button>
              </div>
            </div>
            <div className="db-card-body"><VisualizationRenderer widget={widget} rows={filteredRows} columns={columns} /></div>
            <div className="db-position">Widget {index + 1} · width {widget.span}/{GRID_COLUMNS} · height {widget.height || 1} row{(widget.height || 1) === 1 ? "" : "s"}</div>
            {editingId === widget.id && <div className="db-config">
              <label>Title<input value={widget.title} onChange={(event) => updateWidget(widget.id, { title: event.target.value })} /></label>
              <label>Width<select value={widget.span} onChange={(event) => updateWidget(widget.id, { span: Number(event.target.value) })}><option value="12">Full</option><option value="6">Half</option><option value="4">One third</option><option value="3">One quarter</option></select></label>
              <label>Height<select value={widget.height || 1} onChange={(event) => updateWidget(widget.id, { height: Number(event.target.value) })}><option value="1">1 row</option><option value="2">2 rows</option><option value="3">3 rows</option></select></label>
              {widget.type !== VISUALIZATION_TYPES.KPI && widget.type !== VISUALIZATION_TYPES.TABLE && <><label>Category / X<select value={widget.x} onChange={(event) => updateWidget(widget.id, { x: event.target.value })}>{columns.map((column) => <option key={column}>{column}</option>)}</select></label><label>Measure / Y<select value={widget.y} onChange={(event) => updateWidget(widget.id, { y: event.target.value })}>{columns.map((column) => <option key={column}>{column}</option>)}</select></label></>}
            </div>}
          </article>)}
        </div>
        {!widgets.length && <div className="db-empty" style={{ marginTop: 14 }}><strong>Your dashboard canvas is empty</strong><span>Use the buttons above to add a KPI, table, or visualization.</span></div>}
      </>}
    </section>
  </>;
}
