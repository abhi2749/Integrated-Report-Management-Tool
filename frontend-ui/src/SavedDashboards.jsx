import { useCallback, useEffect, useMemo, useState } from "react";
import { API, apiFetch, hasPermission } from "./authClient";

const CSS = `
.sd-root{max-width:1400px;margin:0 auto;padding:24px 28px 40px;color:#172033}.sd-head{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;margin-bottom:20px}.sd-eyebrow{display:block;color:#175cd3;font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px}.sd-head h2{margin:0;font-size:24px}.sd-head p{margin:7px 0 0;color:#667085;font-size:12px;line-height:1.5}.sd-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px}.sd-search{flex:1 1 280px;min-width:220px;height:40px;border:1px solid #d0d5dd;border-radius:9px;padding:0 12px;background:#fff;color:#101828;font:inherit;font-size:12px}.sd-btn{min-height:36px;padding:0 12px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;color:#344054;cursor:pointer;font:inherit;font-size:11px;font-weight:750}.sd-btn:hover:not(:disabled){background:#f8fafc}.sd-btn.primary{background:#175cd3;border-color:#175cd3;color:#fff}.sd-btn.danger{border-color:#f0b7b7;color:#b42318}.sd-btn:disabled{opacity:.5;cursor:not-allowed}.sd-count{color:#667085;font-size:10px;margin-left:auto}.sd-message{padding:10px 12px;margin-bottom:16px;border:1px solid #d0d5dd;border-radius:9px;background:#fff;color:#475467;font-size:11px}.sd-message.error{border-color:#f2c7c7;background:#fff7f7;color:#b42318}.sd-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px}.sd-card{border:1px solid #e4e7ec;border-radius:12px;background:#fff;box-shadow:0 2px 8px rgba(16,24,40,.04);overflow:hidden}.sd-card-head{display:flex;gap:12px;padding:16px;border-bottom:1px solid #eef2f6}.sd-icon{width:38px;height:38px;flex:0 0 38px;display:grid;place-items:center;border-radius:10px;background:#eef4ff;color:#175cd3;font-size:18px;font-weight:800}.sd-card h3{margin:0;color:#101828;font-size:14px;line-height:1.35}.sd-card-head p{margin:5px 0 0;color:#98a2b3;font-size:10px}.sd-body{padding:14px 16px}.sd-meta{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}.sd-meta span{display:block;color:#98a2b3;font-size:9px;text-transform:uppercase;letter-spacing:.05em;font-weight:750}.sd-meta strong{display:block;margin-top:3px;color:#344054;font-size:11px;word-break:break-word}.sd-actions{display:flex;gap:8px;flex-wrap:wrap}.sd-detail{margin-top:12px;padding:11px;border:1px solid #eaecf0;border-radius:8px;background:#f8fafc;color:#475467;font-size:10px;line-height:1.55}.sd-detail strong{color:#344054}.sd-empty{padding:46px 20px;border:1px dashed #d0d5dd;border-radius:12px;background:#fff;text-align:center;color:#667085}.sd-empty strong{display:block;color:#344054;font-size:13px}.sd-empty span{display:block;margin-top:5px;font-size:11px}@media(max-width:700px){.sd-root{padding:18px 14px 30px}.sd-head{display:block}.sd-count{margin-left:0}.sd-meta{grid-template-columns:1fr}}
`;

function safeText(value, fallback = "—") { const text = String(value ?? "").trim(); return text || fallback; }
function formatDate(value) { if (!value) return "Not available"; const date = new Date(value); return Number.isNaN(date.getTime()) ? safeText(value) : date.toLocaleString(); }
function summary(definition) { return { widgets: Array.isArray(definition?.widgets) ? definition.widgets.length : 0, filters: Array.isArray(definition?.filters) ? definition.filters.length : 0, execution: definition?.execution_job_id || "None" }; }

export default function SavedDashboards({ currentUser, onOpenDashboard }) {
  const [dashboards, setDashboards] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [expandedId, setExpandedId] = useState("");
  const [details, setDetails] = useState({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const canView = hasPermission(currentUser, "reports.view");
  const canCreate = hasPermission(currentUser, "reports.create");
  const canDelete = hasPermission(currentUser, "reports.delete");

  const loadDashboards = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const response = await apiFetch(`${API}/dashboards`, { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to load saved dashboards.");
      setDashboards(Array.isArray(data.dashboards) ? data.dashboards : []);
    } catch (requestError) { setError(requestError.message || "Unable to load saved dashboards."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDashboards();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadDashboards]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return dashboards;
    return dashboards.filter((item) => [item.name, item.id, item.owner_username].some((value) => String(value ?? "").toLowerCase().includes(needle)));
  }, [dashboards, search]);

  const loadDetails = async (dashboardId) => {
    setBusyId(dashboardId); setError("");
    try {
      const response = await apiFetch(`${API}/dashboards/${encodeURIComponent(dashboardId)}`, { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to load dashboard.");
      setDetails((current) => ({ ...current, [dashboardId]: data.dashboard }));
      setExpandedId(dashboardId);
      return data.dashboard;
    } catch (requestError) { setError(requestError.message || "Unable to load dashboard."); return null; }
    finally { setBusyId(""); }
  };

  const openDashboard = async (dashboardId) => {
    const item = details[dashboardId] || await loadDetails(dashboardId);
    if (!item) return;
    onOpenDashboard?.(item);
  };

  const deleteDashboard = async (item) => {
    if (!canDelete || !window.confirm(`Delete saved dashboard "${item.name || "this dashboard"}"? This cannot be undone.`)) return;
    setBusyId(item.id); setError(""); setMessage("");
    try {
      const response = await apiFetch(`${API}/dashboards/${encodeURIComponent(item.id)}`, { method: "DELETE", headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to delete dashboard.");
      setDashboards((current) => current.filter((dashboard) => dashboard.id !== item.id));
      setDetails((current) => { const next = { ...current }; delete next[item.id]; return next; });
      setMessage(`Dashboard "${item.name || item.id}" deleted successfully.`);
    } catch (requestError) { setError(requestError.message || "Unable to delete dashboard."); }
    finally { setBusyId(""); }
  };

  const duplicateDashboard = async (item) => {
    if (!canCreate) return;
    const source = details[item.id] || await loadDetails(item.id);
    if (!source) return;
    const newId = globalThis.crypto?.randomUUID?.() || `dash_${Date.now()}`;
    const name = window.prompt("New dashboard name", `${item.name || "Dashboard"} Copy`);
    if (!name?.trim()) return;
    setBusyId(item.id); setError("");
    try {
      const response = await apiFetch(`${API}/dashboards`, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ id: newId, name: name.trim(), definition: source.definition || {} }) });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to duplicate dashboard.");
      await loadDashboards(); setMessage(`Dashboard "${name.trim()}" created.`);
    } catch (requestError) { setError(requestError.message || "Unable to duplicate dashboard."); }
    finally { setBusyId(""); }
  };

  const exportDashboard = async (item, format) => {
    try {
      const response = await apiFetch(`${API}/dashboards/${encodeURIComponent(item.id)}/export/${format}`);
      if (!response.ok) { let message = "Unable to export dashboard."; try { const body = await response.json(); message = body?.message || body?.detail || message; } catch { /* non-JSON */ } throw new Error(message); }
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `dashboard-${item.id}.${format}`; document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
    } catch (requestError) { setError(requestError.message || "Unable to export dashboard."); }
  };

  if (!canView) return <div className="sd-root"><style>{CSS}</style><div className="sd-empty"><strong>Saved Dashboards access required</strong><span>You do not have permission to view saved dashboards.</span></div></div>;

  return <div className="sd-root"><style>{CSS}</style>
    <div className="sd-head"><div><span className="sd-eyebrow">DASHBOARD LIBRARY</span><h2>Saved Dashboards</h2><p>Monitor, load, configure, share, export and delete saved dashboards. Dashboard is the separate workspace for editing the canvas.</p></div><button type="button" className="sd-btn primary" onClick={() => onOpenDashboard?.(null)}>+ New Dashboard</button></div>
    <div className="sd-toolbar"><input className="sd-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search dashboards by name, ID or owner..." aria-label="Search saved dashboards"/><span className="sd-count">{filtered.length} of {dashboards.length} dashboard(s)</span><button type="button" className="sd-btn" onClick={loadDashboards} disabled={loading}>{loading ? "Refreshing..." : "↻ Refresh"}</button></div>
    {message && <div className="sd-message">{message}</div>}{error && <div className="sd-message error" role="alert">{error}</div>}
    {loading && dashboards.length === 0 ? <div className="sd-empty"><strong>Loading saved dashboards...</strong><span>Please wait while the dashboard library is loaded.</span></div> : filtered.length === 0 ? <div className="sd-empty"><strong>{dashboards.length ? "No matching dashboards" : "No saved dashboards yet"}</strong><span>{dashboards.length ? "Try a different search term." : "Create and save a dashboard from Dashboard Workspace."}</span></div> : <div className="sd-grid">
      {filtered.map((item) => { const detail = details[item.id]; const info = summary(detail?.definition || item.definition); const busy = busyId === item.id; return <article className="sd-card" key={item.id}>
        <div className="sd-card-head"><div className="sd-icon">▤</div><div><h3>{safeText(item.name, "Untitled Dashboard")}</h3><p>Updated {formatDate(item.updated_at)}</p></div></div>
        <div className="sd-body"><div className="sd-meta"><div><span>Dashboard ID</span><strong>{safeText(item.id)}</strong></div><div><span>Version</span><strong>{safeText(item.version, "1")}</strong></div><div><span>Owner</span><strong>{safeText(item.owner_username)}</strong></div><div><span>Widgets</span><strong>{info.widgets}</strong></div></div>
          <div className="sd-actions"><button type="button" className="sd-btn primary" onClick={() => openDashboard(item.id)} disabled={busy}>Load &amp; Configure</button><button type="button" className="sd-btn" onClick={() => loadDetails(item.id)} disabled={busy}>{expandedId === item.id ? "Refresh Details" : "Monitor"}</button>{canCreate && <button type="button" className="sd-btn" onClick={() => duplicateDashboard(item)} disabled={busy}>Duplicate</button>}<button type="button" className="sd-btn" onClick={() => exportDashboard(item, "json")} disabled={busy}>Export JSON</button><button type="button" className="sd-btn" onClick={() => exportDashboard(item, "csv")} disabled={busy || !info.execution}>Export CSV</button><button type="button" className="sd-btn" onClick={() => exportDashboard(item, "xlsx")} disabled={busy || !info.execution}>Export Excel</button><button type="button" className="sd-btn" onClick={() => exportDashboard(item, "pdf")} disabled={busy || !info.execution}>Export PDF</button><button type="button" className="sd-btn primary" onClick={() => exportDashboard(item, "package")} disabled={busy || !info.execution}>Download Package</button>{canDelete && <button type="button" className="sd-btn danger" onClick={() => deleteDashboard(item)} disabled={busy}>Delete</button>}</div>
          {expandedId === item.id && <div className="sd-detail"><strong>Dashboard status</strong><br/>{info.widgets} widget(s) · {info.filters} filter(s) · Execution: <strong>{info.execution}</strong><br/>Created: {formatDate(item.created_at)}<br/>Last updated: {formatDate(item.updated_at)}</div>}
        </div></article>; })}
    </div>}
  </div>;
}
