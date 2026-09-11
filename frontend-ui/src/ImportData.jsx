import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "./authClient";

const styles = `
.import-page { max-width: 1180px; margin: 0 auto; padding: 28px; }
.import-head { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:22px; }
.import-head h2 { margin:0 0 6px; color:#101828; }
.import-head p { margin:0; color:#667085; }
.import-card { background:#fff; border:1px solid #e4e7ec; border-radius:14px; padding:20px; box-shadow:0 2px 8px rgba(16,24,40,.04); }
.import-upload { display:flex; flex-wrap:wrap; align-items:center; gap:12px; }
.import-upload input { max-width:360px; }
.import-button { border:1px solid #175cd3; background:#175cd3; color:#fff; border-radius:9px; padding:9px 14px; cursor:pointer; font-weight:700; }
.import-button.secondary { background:#fff; color:#344054; border-color:#d0d5dd; }
.import-button:disabled { opacity:.55; cursor:not-allowed; }
.import-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
.import-error { margin-top:14px; color:#b42318; background:#fef3f2; border:1px solid #fecdca; padding:10px 12px; border-radius:9px; }
.import-success { margin-top:14px; color:#027a48; background:#ecfdf3; border:1px solid #abefc6; padding:10px 12px; border-radius:9px; }
.import-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; margin-top:20px; }
.import-item { border:1px solid #eaecf0; border-radius:12px; padding:16px; background:#fcfcfd; }
.import-item h3 { margin:0 0 7px; font-size:16px; color:#101828; }
.import-meta { color:#667085; font-size:13px; line-height:1.6; }
.import-preview { margin-top:20px; overflow:auto; border:1px solid #eaecf0; border-radius:10px; }
.import-preview table { border-collapse:collapse; min-width:100%; font-size:13px; }
.import-preview th,.import-preview td { padding:8px 10px; border-bottom:1px solid #eaecf0; text-align:left; white-space:nowrap; }
.import-preview th { background:#f9fafb; color:#344054; }
`;

function ImportData() {
  const [items, setItems] = useState([]);
  const [file, setFile] = useState(null);
  const [selected, setSelected] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const inputRef = useRef(null);

  const loadItems = useCallback(async () => {
    setLoadingList(true);
    try {
      const response = await apiFetch("/data/imported");
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.detail || payload.message || "Unable to load imported data.");
      setItems(Array.isArray(payload.datasets) ? payload.datasets : []);
    } catch (err) {
      setError(err.message || "Unable to load imported data.");
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadInitialItems = async () => {
      try {
        const response = await apiFetch("/data/imported");
        const payload = await response.json();
        if (!response.ok || !payload.success) {
          throw new Error(payload.detail || payload.message || "Unable to load imported data.");
        }
        if (!cancelled) {
          setItems(Array.isArray(payload.datasets) ? payload.datasets : []);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load imported data.");
        }
      } finally {
        if (!cancelled) {
          setLoadingList(false);
        }
      }
    };

    void loadInitialItems();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await apiFetch("/data/import", { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.detail || payload.message || "Import failed.");
      setSuccess(`Imported ${payload.dataset.name} successfully.`);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      await loadItems();
      setSelected(payload.dataset);
      setPreview(payload.preview || null);
    } catch (err) {
      setError(err.message || "Import failed.");
    } finally {
      setLoading(false);
    }
  };

  const renameItem = async (item) => {
    const nextName = window.prompt("Dataset name", item.name || "");
    if (nextName === null) return;
    const name = nextName.trim();
    if (!name || name === item.name) return;
    setError("");
    try {
      const response = await apiFetch(`/data/imported/${encodeURIComponent(item.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ name }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.detail || payload.message || "Unable to rename dataset.");
      setSelected(payload.dataset);
      await loadItems();
    } catch (err) {
      setError(err.message || "Unable to rename dataset.");
    }
  };

  const deleteItem = async (item) => {
    if (!window.confirm(`Delete imported dataset "${item.name}"? This removes the saved data asset.`)) return;
    setError("");
    try {
      const response = await apiFetch(`/data/imported/${encodeURIComponent(item.id)}`, { method: "DELETE" });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.detail || payload.message || "Unable to delete dataset.");
      if (selected?.id === item.id) {
        setSelected(null);
        setPreview(null);
      }
      await loadItems();
    } catch (err) {
      setError(err.message || "Unable to delete dataset.");
    }
  };

  const openItem = async (id) => {
    setError("");
    try {
      const response = await apiFetch(`/data/imported/${encodeURIComponent(id)}`);
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.detail || "Unable to open imported dataset.");
      setSelected(payload.dataset);
      setPreview(payload.preview || null);
    } catch (err) {
      setError(err.message || "Unable to open imported dataset.");
    }
  };

  return (
    <>
      <style>{styles}</style>
      <section className="import-page">
        <div className="import-head">
          <div>
            <h2>Import Data</h2>
            <p>Bring CSV, JSON and Excel data into the reporting workspace.</p>
          </div>
          <button type="button" className="import-button secondary" onClick={loadItems} disabled={loadingList}>Refresh</button>
        </div>

        <div className="import-card">
          <div className="import-upload">
            <input ref={inputRef} type="file" accept=".csv,.json,.xlsx" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            <button type="button" className="import-button" onClick={handleImport} disabled={!file || loading}>
              {loading ? "Importing…" : "Import Data"}
            </button>
            <span className="import-meta">Maximum file size: 50 MB</span>
          </div>
          {error && <div className="import-error">{error}</div>}
          {success && <div className="import-success">{success}</div>}
        </div>

        <div className="import-grid">
          {loadingList && <div className="import-card">Loading imported datasets…</div>}
          {!loadingList && items.length === 0 && <div className="import-card">No imported datasets yet.</div>}
          {items.map((item) => (
            <article className="import-item" key={item.id}>
              <h3>{item.name}</h3>
              <div className="import-meta">
                {item.format?.toUpperCase()} · {item.row_count ?? 0} rows · {item.columns?.length ?? 0} columns<br />
                Owner: {item.owner_username || "Unknown"}
              </div>
              <div className="import-actions">
                <button type="button" className="import-button secondary" onClick={() => openItem(item.id)}>Preview Data</button>
                <button type="button" className="import-button secondary" onClick={() => renameItem(item)}>Rename</button>
                <button type="button" className="import-button secondary" onClick={() => deleteItem(item)}>Delete</button>
              </div>
            </article>
          ))}
        </div>

        {selected && preview && (
          <div className="import-card" style={{ marginTop: 20 }}>
            <h3 style={{ marginTop: 0 }}>{selected.name} — Preview</h3>
            <div className="import-meta">Saved ingestion asset · {selected.row_count} rows · {selected.format?.toUpperCase()}</div>
            <div className="import-preview">
              <table>
                <thead><tr>{(preview.columns || []).map((column) => <th key={column.name}>{column.name}</th>)}</tr></thead>
                <tbody>
                  {(preview.rows || []).map((row, index) => (
                    <tr key={`${selected.id}-${index}`}>
                      {(preview.columns || []).map((column) => <td key={column.name}>{String(row[column.name] ?? "")}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </>
  );
}

export default ImportData;
