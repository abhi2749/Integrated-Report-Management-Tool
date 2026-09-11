import { useCallback, useEffect, useMemo, useState } from "react";
import { API, apiFetch, hasPermission } from "./authClient";

const SAVED_REPORTS_CSS = `
.sr-root{max-width:1400px;margin:0 auto;padding:24px 28px 40px;box-sizing:border-box;color:#172033}
.sr-heading{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;margin-bottom:20px}
.sr-eyebrow{display:block;color:#175cd3;font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px}
.sr-heading h2{margin:0;font-size:24px;line-height:1.2}.sr-heading p{margin:7px 0 0;color:#667085;font-size:12px;line-height:1.5}
.sr-toolbar{display:flex;gap:10px;align-items:center;margin-bottom:18px;flex-wrap:wrap}
.sr-search{flex:1 1 280px;min-width:220px;height:40px;border:1px solid #d0d5dd;border-radius:9px;padding:0 12px;box-sizing:border-box;background:#fff;color:#101828;font:inherit;font-size:12px;outline:none}
.sr-search:focus{border-color:#84adf7;box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.sr-btn{min-height:36px;padding:0 12px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;color:#344054;cursor:pointer;font:inherit;font-size:11px;font-weight:750}
.sr-btn:hover:not(:disabled){background:#f8fafc;border-color:#98a2b3}.sr-btn:disabled{opacity:.55;cursor:not-allowed}
.sr-btn.primary{border-color:#175cd3;background:#175cd3;color:#fff}.sr-btn.primary:hover:not(:disabled){background:#124bb0}
.sr-btn.danger{border-color:#f0b7b7;color:#b42318}.sr-btn.danger:hover:not(:disabled){background:#fff5f5}
.sr-message{margin-bottom:16px;padding:10px 12px;border:1px solid #d0d5dd;border-radius:9px;background:#fff;color:#475467;font-size:11px;line-height:1.45}
.sr-message.error{border-color:#f2c7c7;background:#fff7f7;color:#b42318}
.sr-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.sr-card{border:1px solid #e4e7ec;border-radius:12px;background:#fff;box-shadow:0 2px 8px rgba(16,24,40,.04);overflow:hidden}
.sr-card-head{display:flex;gap:12px;align-items:flex-start;padding:16px 16px 12px;border-bottom:1px solid #eef2f6}
.sr-icon{width:38px;height:38px;flex:0 0 38px;display:grid;place-items:center;border-radius:10px;background:#eef4ff;color:#175cd3;font-size:18px;font-weight:800}
.sr-card-head h3{margin:0;color:#101828;font-size:14px;line-height:1.35;word-break:break-word}.sr-card-head p{margin:5px 0 0;color:#98a2b3;font-size:10px}
.sr-card-body{padding:14px 16px}.sr-meta{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}.sr-meta-item span{display:block;color:#98a2b3;font-size:9px;text-transform:uppercase;letter-spacing:.05em;font-weight:750}.sr-meta-item strong{display:block;margin-top:3px;color:#344054;font-size:11px;word-break:break-word}
.sr-actions{display:flex;gap:8px;flex-wrap:wrap}.sr-detail{margin-top:12px;padding:11px;border:1px solid #eaecf0;border-radius:8px;background:#f8fafc;color:#475467;font-size:10px;line-height:1.5}.sr-detail strong{color:#344054}.sr-empty{padding:46px 20px;border:1px dashed #d0d5dd;border-radius:12px;background:#fff;text-align:center;color:#667085}.sr-empty-icon{font-size:28px;margin-bottom:8px}.sr-empty strong{display:block;color:#344054;font-size:13px}.sr-empty span{display:block;margin-top:5px;font-size:11px}
.sr-count{color:#667085;font-size:10px;margin-left:auto}.sr-selection-bar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:-6px 0 18px;padding:10px 12px;border:1px solid #dbe7ff;border-radius:9px;background:#f8fbff;color:#475467;font-size:10px}.sr-selection-bar strong{color:#175cd3}.sr-select{margin:2px 0 0;accent-color:#175cd3;cursor:pointer;flex:0 0 auto}
@media(max-width:700px){.sr-root{padding:18px 14px 30px}.sr-heading{display:block}.sr-count{margin-left:0}.sr-meta{grid-template-columns:1fr}}
`;

function safeText(value, fallback = "—") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function formatDate(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return safeText(value);
  return date.toLocaleString();
}

function getDefinitionSummary(definition) {
  const sourceCount = Array.isArray(definition?.datasets) ? definition.datasets.length : 0;
  const joinCount = Array.isArray(definition?.joins) ? definition.joins.length : 0;
  const columnCount = Array.isArray(definition?.columns)
    ? definition.columns.filter((column) => column?.selected !== false).length
    : 0;
  return { sourceCount, joinCount, columnCount };
}

export default function SavedReports({ currentUser, onOpenReportBuilder }) {
  const [reports, setReports] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [expandedId, setExpandedId] = useState("");
  const [details, setDetails] = useState({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selectedReportId, setSelectedReportId] = useState("");

  const canView = hasPermission(currentUser, "reports.view");
  const canCreate = hasPermission(currentUser, "reports.create");
  const canDelete = hasPermission(currentUser, "reports.delete");

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch(`${API}/reports`, {
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || data.detail || `Unable to load saved reports (HTTP ${response.status}).`);
      }
      setReports(Array.isArray(data.reports) ? data.reports : []);
    } catch (requestError) {
      setError(requestError.message || "Unable to load saved reports.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;

    const initialize = async () => {
      try {
        const response = await apiFetch(`${API}/reports`, {
          headers: { Accept: "application/json" },
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
          throw new Error(data.message || data.detail || `Unable to load saved reports (HTTP ${response.status}).`);
        }
        if (active) {
          setReports(Array.isArray(data.reports) ? data.reports : []);
          setError("");
          setLoading(false);
        }
      } catch (requestError) {
        if (active) {
          setError(requestError.message || "Unable to load saved reports.");
          setLoading(false);
        }
      }
    };

    initialize();
    return () => { active = false; };
  }, []);

  const selectedReport = reports.find((report) => report.id === selectedReportId) || null;

  const filteredReports = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return reports;
    return reports.filter((report) =>
      [report.name, report.id, report.owner_username]
        .some((value) => String(value ?? "").toLowerCase().includes(needle))
    );
  }, [reports, search]);

  const toggleDetails = async (reportId) => {
    if (expandedId === reportId) {
      setExpandedId("");
      return;
    }
    setExpandedId(reportId);
    if (details[reportId]) return;

    setBusyId(reportId);
    setError("");
    try {
      const response = await apiFetch(`${API}/reports/${encodeURIComponent(reportId)}`, {
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || data.detail || "Unable to load report details.");
      }
      setDetails((current) => ({ ...current, [reportId]: data.report || null }));
    } catch (requestError) {
      setError(requestError.message || "Unable to load report details.");
      setExpandedId("");
    } finally {
      setBusyId("");
    }
  };

  const deleteReport = async (report) => {
    if (!canDelete) return;
    if (!window.confirm(`Delete saved report "${report.name || "this report"}"? This cannot be undone.`)) return;

    setBusyId(report.id);
    setMessage("");
    setError("");
    try {
      const response = await apiFetch(`${API}/reports/${encodeURIComponent(report.id)}`, {
        method: "DELETE",
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || data.detail || "Unable to delete saved report.");
      }
      setReports((current) => current.filter((item) => item.id !== report.id));
      setExpandedId("");
      setMessage(`Report "${report.name || report.id}" deleted successfully.`);
    } catch (requestError) {
      setError(requestError.message || "Unable to delete saved report.");
    } finally {
      setBusyId("");
    }
  };

  const exportReport = async (report, format) => {
    setBusyId(report.id);
    setMessage("");
    setError("");
    try {
      const response = await apiFetch(`${API}/reports/${encodeURIComponent(report.id)}/export/${format}`, { method: "POST", headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to create report export.");
      setMessage(`${format.toUpperCase()} export queued. Export job: ${data.export_id}`);
    } catch (requestError) {
      setError(requestError.message || "Unable to export report.");
    } finally {
      setBusyId("");
    }
  };

  const duplicateReport = async (report) => {
    if (!canCreate) return;
    setBusyId(report.id);
    setMessage("");
    setError("");
    try {
      const response = await apiFetch(`${API}/reports/${encodeURIComponent(report.id)}/duplicate`, {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || data.detail || "Unable to duplicate saved report.");
      }
      await loadReports();
      const duplicated = data.report || {};
      setMessage(`Report duplicated${duplicated.name ? ` as "${duplicated.name}"` : " successfully"}.`);
    } catch (requestError) {
      setError(requestError.message || "Unable to duplicate saved report.");
    } finally {
      setBusyId("");
    }
  };

  if (!canView) {
    return (
      <div className="sr-root">
        <style>{SAVED_REPORTS_CSS}</style>
        <div className="sr-empty">
          <div className="sr-empty-icon">▤</div>
          <strong>Saved Reports access required</strong>
          <span>You do not have permission to view saved reports.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="sr-root">
      <style>{SAVED_REPORTS_CSS}</style>
      <div className="sr-heading">
        <div>
          <span className="sr-eyebrow">REPORT LIBRARY</span>
          <h2>Saved Reports</h2>
          <p>Find, review, duplicate and manage reusable report configurations.</p>
        </div>
        <button type="button" className="sr-btn primary" onClick={onOpenReportBuilder}>
          + Build New Report
        </button>
      </div>

      <div className="sr-toolbar">
        <input
          className="sr-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search reports by name, ID or owner..."
          aria-label="Search saved reports"
        />
        <span className="sr-count">{filteredReports.length} of {reports.length} report(s)</span>
        <button type="button" className="sr-btn" onClick={loadReports} disabled={loading}>
          {loading ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      <div className="sr-selection-bar">
        <span><strong>{selectedReport ? safeText(selectedReport.name, "Selected report") : "No report selected"}</strong></span>
        <div className="sr-actions">
          <button type="button" className="sr-btn primary" disabled={!selectedReport} onClick={() => onOpenReportBuilder?.(selectedReportId)}>Load</button>
          <button type="button" className="sr-btn" disabled={!selectedReport} onClick={() => onOpenReportBuilder?.(selectedReportId)}>Configure / Modify</button>
          <button type="button" className="sr-btn danger" disabled={!selectedReport || !canDelete} onClick={() => selectedReport && deleteReport(selectedReport)}>Delete</button>
        </div>
      </div>

      {message && <div className="sr-message">{message}</div>}
      {error && <div className="sr-message error" role="alert">{error}</div>}

      {loading && reports.length === 0 ? (
        <div className="sr-empty"><div className="sr-empty-icon">◌</div><strong>Loading saved reports...</strong><span>Please wait while the report library is loaded.</span></div>
      ) : filteredReports.length === 0 ? (
        <div className="sr-empty">
          <div className="sr-empty-icon">▤</div>
          <strong>{reports.length ? "No matching reports" : "No saved reports yet"}</strong>
          <span>{reports.length ? "Try a different search term." : "Save a report from Report Builder and it will appear here."}</span>
        </div>
      ) : (
        <div className="sr-grid">
          {filteredReports.map((report) => {
            const detail = details[report.id];
            const definition = detail?.definition || detail || {};
            const summary = getDefinitionSummary(definition);
            const busy = busyId === report.id;

            return (
              <article className="sr-card" key={report.id}>
                <div className="sr-card-head">
                  <input className="sr-select" type="radio" name="saved-report-selection" checked={selectedReportId === report.id} onChange={() => setSelectedReportId(report.id)} aria-label={`Select ${report.name || "saved report"}`} />
                  <div className="sr-icon">▤</div>
                  <div>
                    <h3>{safeText(report.name, "Untitled Report")}</h3>
                    <p>Updated {formatDate(report.updated_at)}</p>
                  </div>
                </div>
                <div className="sr-card-body">
                  <div className="sr-meta">
                    <div className="sr-meta-item"><span>Report ID</span><strong>{safeText(report.id)}</strong></div>
                    <div className="sr-meta-item"><span>Created</span><strong>{formatDate(report.created_at)}</strong></div>
                    {detail && <div className="sr-meta-item"><span>Datasets</span><strong>{summary.sourceCount}</strong></div>}
                    {detail && <div className="sr-meta-item"><span>JOINs</span><strong>{summary.joinCount}</strong></div>}
                  </div>

                  <div className="sr-actions">
                    <button type="button" className="sr-btn primary" onClick={() => onOpenReportBuilder(report.id)} disabled={busy}>Load / Configure</button>
                    <button type="button" className="sr-btn" onClick={() => toggleDetails(report.id)} disabled={busy}>
                      {busy ? "Loading..." : expandedId === report.id ? "Hide Details" : "View Details"}
                    </button>
                    {canCreate && <button type="button" className="sr-btn" onClick={() => duplicateReport(report)} disabled={busy}>Duplicate</button>}<button type="button" className="sr-btn" onClick={() => exportReport(report, "csv")} disabled={busy}>CSV</button><button type="button" className="sr-btn" onClick={() => exportReport(report, "json")} disabled={busy}>JSON</button><button type="button" className="sr-btn" onClick={() => exportReport(report, "xlsx")} disabled={busy}>Excel</button><button type="button" className="sr-btn" onClick={() => exportReport(report, "pdf")} disabled={busy}>PDF</button><button type="button" className="sr-btn" onClick={() => exportReport(report, "package")} disabled={busy}>Package</button>
                    {canDelete && <button type="button" className="sr-btn danger" onClick={() => deleteReport(report)} disabled={busy}>Delete</button>}
                  </div>

                  {expandedId === report.id && detail && (
                    <div className="sr-detail">
                      <strong>Configuration summary</strong><br />
                      {summary.sourceCount} dataset(s) · {summary.joinCount} JOIN(s) · {summary.columnCount} selected column(s)<br />
                      Visualization: <strong>{safeText(definition.visualization, "table")}</strong>
                      {definition.owner_username && <><br />Owner: <strong>{definition.owner_username}</strong></>}
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
