import { useCallback, useEffect, useMemo, useState } from "react";
import { API, apiFetch } from "./authClient";
import { PREVIEW_ROW_OPTIONS, worksheetRowLabel } from "./worksheetLimits";
const COMPONENT_APP_CSS = `
/* ============================================================
 * APP.CSS COMPATIBILITY STYLES
 * Moved into this component during CSS ownership refactor.
 * Existing component styles remain after this block intentionally.
 * ============================================================ */
.primary,
.secondary,
.danger-outline {
  border-radius: 7px;
  padding: 10px 15px;
  font-weight: 700;
  white-space: nowrap;
}
.primary {
  border: 1px solid #175cd3;
  background: #175cd3;
  color: #fff;
}
.primary:disabled {
  opacity: .55;
}
@(max-width: 900px){
.preview-toolbar .primary {
    grid-column: 1 / -1;
    width: 100%;
  }
}
.data-source-manager{
  width:100%;
  min-width:0;
  color:#172033;
}
.data-source-manager .card{
  border-color:#dce4ef;
  border-radius:12px;
  box-shadow:0 2px 8px rgba(15,23,42,.035);
}
.data-source-manager .primary,
.data-source-manager .secondary,
.data-source-manager .danger-outline{
  min-height:36px;
  box-sizing:border-box;
  font-size:10px;
}
.data-source-manager .primary{padding:0 13px}
.data-source-manager .secondary{padding:0 13px}
.data-source-manager .danger-outline{padding:0 13px}
`;



const emptyForm = {
  name: "",
  source_type: "mysql",
  host: "localhost",
  port: 3306,
  username: "root",
  password: "",
};

function sourceLabel(type) {
  const value = String(type || "").toLowerCase();
  if (value === "mongodb" || value === "mongo") return "MongoDB";
  if (value === "mysql") return "MySQL";
  if (value === "clickhouse") return "ClickHouse";
  return String(type || "Database");
}

function objectLabel(type) {
  const value = String(type || "").toLowerCase();
  if (value === "mongodb" || value === "mongo") return "Collection";
  return "Table";
}

function valueText(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function normalizeColumns(columns = []) {
  return columns.map((item) => {
    if (typeof item === "string") {
      return { name: item, data_type: "unknown" };
    }
    return {
      name: item.name,
      data_type: item.data_type || item.type || "unknown",
    };
  });
}

function buildProfiles(columns, rows, suppliedProfiles = []) {
  return columns.map((name) => {
    const supplied = suppliedProfiles.find((item) => item?.name === name);
    if (supplied) return supplied;

    const values = rows
      .map((row) => row?.[name])
      .filter(
        (value) =>
          value !== null &&
          value !== undefined &&
          value !== ""
      );

    const distinct = new Set(
      values.map((value) =>
        typeof value === "object"
          ? JSON.stringify(value)
          : String(value)
      )
    );

    return {
      name,
      data_type: values.length
        ? typeof values[0]
        : "unknown",
      total_count: rows.length,
      null_count: rows.length - values.length,
      distinct_count: distinct.size,
      example: values[0] ?? null,
    };
  });
}

export default function DataSourceManager({
  datasets = [],
  setDatasets,
  setReportResult,
}) {
  const [connections, setConnections] = useState([]);
  const [connectors, setConnectors] = useState([]);
  const [connectionForm, setConnectionForm] = useState(emptyForm);
  const [editingConnectionId, setEditingConnectionId] = useState("");
  const [showConnectionForm, setShowConnectionForm] = useState(true);

  const [selectedConnectionId, setSelectedConnectionId] = useState("");
  const [expandedConnections, setExpandedConnections] = useState({});
  const [databasesByConnection, setDatabasesByConnection] = useState({});
  const [selectedDatabase, setSelectedDatabase] = useState("");
  const [objects, setObjects] = useState([]);
  const [selectedObject, setSelectedObject] = useState("");
  const [preview, setPreview] = useState(null);

  const [sampleLimit, setSampleLimit] = useState(25);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const selectedConnection = useMemo(
    () =>
      connections.find((item) => item.id === selectedConnectionId) ||
      null,
    [connections, selectedConnectionId]
  );

  const filteredObjects = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return objects;
    return objects.filter((item) =>
      String(item?.name || item).toLowerCase().includes(needle)
    );
  }, [objects, search]);

  const loadConnections = useCallback(async (selectFirst = false) => {
    try {
      const response = await apiFetch(`${API}/datasource/connections`);
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to load saved connections."
        );
      }

      const list = Array.isArray(data.connections) ? data.connections : [];
      setConnections(list);

      if (selectFirst && list.length) {
        setSelectedConnectionId((currentId) => {
          if (currentId) return currentId;
          setExpandedConnections((current) => ({
            ...current,
            [list[0].id]: true,
          }));
          return list[0].id;
        });
      }

      return list;
    } catch (error) {
      setMessage(`Error: ${error.message}`);
      return [];
    }
  }, []);

  const loadDatasets = useCallback(async () => {
    try {
      const response = await apiFetch(`${API}/datasets`);
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to load reporting datasets."
        );
      }

      const list = Array.isArray(data.datasets) ? data.datasets : [];
      setDatasets(list);
      return list;
    } catch (error) {
      setMessage(`Error: ${error.message}`);
      return [];
    }
  }, [setDatasets]);

  useEffect(() => {
    let active = true;

    const loadConnectors = async () => {
      try {
        const response = await apiFetch(`${API}/datasource/connectors`, {
          headers: { Accept: "application/json" },
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
          throw new Error(data.message || data.detail || "Unable to load datasource connectors.");
        }
        if (active) {
          const list = Array.isArray(data.connectors) ? data.connectors : [];
          setConnectors(list);
        }
      } catch (error) {
        console.warn("Unable to load datasource connectors. Using supported defaults.", error);
        if (active) {
          setConnectors([
            { id: "mysql", name: "MySQL", source_type: "mysql" },
            { id: "mongodb", name: "MongoDB", source_type: "mongodb" },
          ]);
        }
      }
    };

    loadConnectors();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    const init = async () => {
      setBusy(true);
      await Promise.all([
        loadConnections(true),
        loadDatasets(),
      ]);
      if (active) setBusy(false);
    };

    init();

    return () => {
      active = false;
    };
  }, [loadConnections, loadDatasets]);

  const resetExplorer = () => {
    setSelectedDatabase("");
    setObjects([]);
    setSelectedObject("");
    setPreview(null);
    setSearch("");
  };

  const resetConnectionForm = () => {
    setConnectionForm(emptyForm);
    setEditingConnectionId("");
  };

  const handleConnectionField = (field, value) => {
    setConnectionForm((current) => ({
      ...current,
      [field]: field === "port" ? Number(value) || "" : value,
    }));
  };

  const saveConnection = async () => {
    if (
      !connectionForm.name.trim() ||
      !connectionForm.host.trim() ||
      !connectionForm.port
    ) {
      setMessage("Connection name, host and port are required.");
      return;
    }

    setBusy(true);
    setMessage("");

    try {
      const isEditing = Boolean(editingConnectionId);
      const url = isEditing
        ? `${API}/datasource/connections/${editingConnectionId}`
        : `${API}/datasource/connections`;

      const method = isEditing ? "PUT" : "POST";

      const payload = {
        name: connectionForm.name.trim(),
        source_type: connectionForm.source_type,
        host: connectionForm.host.trim(),
        port: Number(connectionForm.port),
        username: connectionForm.username || null,
        password: connectionForm.password || null,
        status: "saved",
      };

      const response = await apiFetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to save connection."
        );
      }

      const saved = data.connection;
      const list = await loadConnections();

      if (saved?.id) {
        setSelectedConnectionId(saved.id);
        setExpandedConnections((current) => ({
          ...current,
          [saved.id]: true,
        }));
      }

      resetExplorer();
      resetConnectionForm();

      if (!isEditing) {
        setConnectionForm({
          ...emptyForm,
          source_type: saved?.source_type || "mysql",
        });
      }

      setMessage(
        isEditing
          ? "Connection updated successfully."
          : "Connection saved successfully. Select it below to browse the database."
      );

      if (!list.length) {
        setMessage("Connection saved, but no saved connections were returned.");
      }
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const testNewConnection = async () => {
    if (!connectionForm.host.trim() || !connectionForm.port) {
      setMessage("Host and port are required.");
      return;
    }

    setBusy(true);
    setMessage("");

    try {
      const response = await apiFetch(`${API}/datasource/test`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          source_type: connectionForm.source_type,
          host: connectionForm.host.trim(),
          port: Number(connectionForm.port),
          username: connectionForm.username || null,
          password: connectionForm.password || null,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Connection test failed."
        );
      }

      setMessage(
        `Connection successful${
          data.server_version
            ? ` · server ${data.server_version}`
            : ""
        }. Click Save Connection to store it.`
      );
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const editConnection = (connection) => {
    setEditingConnectionId(connection.id);
    setConnectionForm({
      name: connection.name || "",
      source_type: connection.source_type || "mysql",
      host: connection.host || "",
      port: Number(connection.port) || "",
      username: connection.username || "",
      password: "",
    });
    setShowConnectionForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const deleteAllConnections = async () => {
    if (!connections.length) {
      setMessage("No saved connections to delete.");
      return;
    }

    const confirmed = window.confirm(
      `Delete all ${connections.length} saved connection(s)? This removes only saved connection records. Existing reporting datasets may no longer be usable.`
    );

    if (!confirmed) return;

    setBusy(true);
    setMessage("");

    try {
      const results = await Promise.all(
        connections.map(async (connection) => {
          const response = await apiFetch(
            `${API}/datasource/connections/${connection.id}`,
            { method: "DELETE" }
          );
          const data = await response.json();

          if (!response.ok || !data.success) {
            throw new Error(
              data.message ||
                data.detail ||
                `Unable to delete connection "${connection.name}".`
            );
          }

          return connection.id;
        })
      );

      const remaining = await loadConnections();

      setDatabasesByConnection({});
      setExpandedConnections({});
      setSelectedConnectionId("");
      resetExplorer();

      setMessage(
        remaining.length === 0
          ? `All ${results.length} saved connection(s) deleted successfully.`
          : `${results.length} connection(s) deleted; ${remaining.length} remain.`
      );
    } catch (error) {
      await loadConnections();
      setMessage(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const deleteConnection = async (connection) => {
    const confirmed = window.confirm(
      `Delete saved connection "${connection.name}"? Datasets already created from it may no longer be usable.`
    );

    if (!confirmed) return;

    setBusy(true);
    setMessage("");

    try {
      const response = await apiFetch(
        `${API}/datasource/connections/${connection.id}`,
        { method: "DELETE" }
      );
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to delete connection."
        );
      }

      const remaining = await loadConnections();

      setDatabasesByConnection((current) => {
        const next = { ...current };
        delete next[connection.id];
        return next;
      });

      if (selectedConnectionId === connection.id) {
        setSelectedConnectionId(remaining[0]?.id || "");
        resetExplorer();
      }

      setMessage("Connection deleted.");
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const loadDatabases = async (connection, force = false) => {
    if (!connection) return [];

    if (
      !force &&
      Array.isArray(databasesByConnection[connection.id])
    ) {
      return databasesByConnection[connection.id];
    }

    setBusy(true);
    setMessage("");

    try {
      const response = await apiFetch(
        `${API}/datasource/connections/${connection.id}/databases`
      );
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to discover databases."
        );
      }

      const list = Array.isArray(data.databases) ? data.databases : [];

      setDatabasesByConnection((current) => ({
        ...current,
        [connection.id]: list,
      }));

      return list;
    } catch (error) {
      setMessage(`Error: ${error.message}`);
      return [];
    } finally {
      setBusy(false);
    }
  };

  const selectConnection = async (connection) => {
    setSelectedConnectionId(connection.id);
    resetExplorer();
    setExpandedConnections((current) => ({
      ...current,
      [connection.id]: true,
    }));

    await loadDatabases(connection);
  };

  const toggleConnection = async (connection) => {
    const isOpen = Boolean(expandedConnections[connection.id]);

    setExpandedConnections((current) => ({
      ...current,
      [connection.id]: !isOpen,
    }));

    if (!isOpen) {
      await selectConnection(connection);
    }
  };

  const selectDatabase = async (connection, databaseName) => {
    setSelectedConnectionId(connection.id);
    setSelectedDatabase(databaseName);
    setSelectedObject("");
    setPreview(null);
    setObjects([]);
    setSearch("");
    setBusy(true);
    setMessage("");

    try {
      const response = await apiFetch(
        `${API}/datasource/connections/${connection.id}/databases/${encodeURIComponent(
          databaseName
        )}/tables`
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to load tables or collections."
        );
      }

      setObjects(Array.isArray(data.tables) ? data.tables : []);
      setMessage(
        `${databaseName}: ${
          Array.isArray(data.tables) ? data.tables.length : 0
        } ${objectLabel(connection.source_type).toLowerCase()}(s) found.`
      );
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const previewObject = async (connection, databaseName, objectName, sampleLimitOverride = null) => {
    setSelectedObject(objectName);
    setPreview(null);
    setBusy(true);
    setMessage("");

    try {
      const response = await apiFetch(
        `${API}/datasource/connections/${connection.id}/preview`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            database: databaseName,
            table: objectName,
            sample_limit: Number(sampleLimitOverride ?? sampleLimit) || 25,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to preview object."
        );
      }

      const rows = Array.isArray(data.rows) ? data.rows : [];
      const columns = Array.isArray(data.columns)
        ? data.columns
        : Object.keys(rows[0] || {});

      const profiles = buildProfiles(
        columns,
        rows,
        Array.isArray(data.column_profiles)
          ? data.column_profiles
          : []
      );

      setPreview({
        ...data,
        rows,
        columns,
        column_profiles: profiles,
        total_rows: Number(
          data.total_rows ??
            data.row_count ??
            data.total_count ??
            rows.length
        ),
      });

      setMessage(
        `${databaseName} → ${objectName} preview loaded.`
      );
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const addToDataset = async () => {
    if (
      !selectedConnection ||
      !selectedDatabase ||
      !selectedObject ||
      !preview
    ) {
      setMessage(
        "Preview a table or collection first, then add it to the reporting dataset."
      );
      return;
    }

    const columns = normalizeColumns(
      preview.column_profiles?.length
        ? preview.column_profiles
        : preview.columns || []
    );

    const existing = datasets.find(
      (item) =>
        item.connection_id === selectedConnection.id &&
        item.database === selectedDatabase &&
        item.object_name === selectedObject
    );

    if (existing) {
      setMessage(
        `${selectedObject} is already in the reporting dataset.`
      );
      return;
    }

    const payload = {
      name: `${selectedDatabase}.${selectedObject}`,
      connection_id: selectedConnection.id,
      database: selectedDatabase,
      object_name: selectedObject,
      object_type:
        selectedConnection.source_type === "mongodb"
          ? "collection"
          : "table",
      columns,
    };

    setBusy(true);
    setMessage("");

    try {
      const response = await apiFetch(`${API}/datasets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to add dataset."
        );
      }

      await loadDatasets();

      if (setReportResult) {
        setReportResult(null);
      }

      setMessage(
        `${selectedObject} has been added to the reporting dataset.`
      );
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const removeDataset = async (datasetId) => {
    setBusy(true);
    setMessage("");

    try {
      const response = await apiFetch(
        `${API}/datasets/${datasetId}`,
        { method: "DELETE" }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || data.detail || "Unable to remove dataset."
        );
      }

      await loadDatasets();

      if (setReportResult) {
        setReportResult(null);
      }

      setMessage("Dataset removed from reporting.");
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };



  const databases =
    selectedConnection
      ? databasesByConnection[selectedConnection.id] || []
      : [];

  return (
    <div className="data-source-manager dsm-pro-dashboard">
      <style>{COMPONENT_APP_CSS + `
        .dsm-pro-dashboard {
          width: 100%;
          max-width: 1480px;
          margin: 0 auto;
          padding: 28px 30px 44px;
          box-sizing: border-box;
          color: #172033;
        }

        .dsm-pro-dashboard *,
        .dsm-pro-dashboard *::before,
        .dsm-pro-dashboard *::after {
          box-sizing: border-box;
        }

        .dsm-pro-eyebrow {
          display: block;
          margin-bottom: 7px;
          color: #6b7a90;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: .13em;
          text-transform: uppercase;
        }

        .dsm-pro-section {
          margin-bottom: 18px;
          overflow: hidden;
          border: 1px solid #dfe5ee;
          border-radius: 14px;
          background: #fff;
          box-shadow: 0 4px 18px rgba(23, 32, 51, .045);
        }

        .dsm-pro-section-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          padding: 19px 22px;
          border-bottom: 1px solid #e8edf4;
          background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
        }

        .dsm-pro-section-head h2,
        .dsm-pro-section-head h3,
        .dsm-pro-panel-head h3,
        .dsm-pro-browser-head h3 {
          margin: 0;
          color: #162238;
          font-weight: 750;
          line-height: 1.2;
        }

        .dsm-pro-section-head h2 { font-size: 20px; }
        .dsm-pro-section-head h3 { font-size: 17px; }

        .dsm-pro-section-head p,
        .dsm-pro-panel-head p,
        .dsm-pro-browser-head p {
          margin: 6px 0 0;
          color: #728198;
          font-size: 12px;
          line-height: 1.5;
        }

        .dsm-pro-section-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-shrink: 0;
        }

        .dsm-pro-btn {
          min-height: 36px;
          padding: 0 14px;
          border: 1px solid #d4dce8;
          border-radius: 8px;
          background: #fff;
          color: #334155;
          font: inherit;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
          transition: .15s ease;
        }

        .dsm-pro-btn:hover:not(:disabled) {
          border-color: #9eb0c8;
          background: #f8fafc;
          transform: translateY(-1px);
        }

        .dsm-pro-btn:disabled {
          cursor: not-allowed;
          opacity: .55;
        }

        .dsm-pro-btn.primary {
          border-color: #2563eb;
          background: #2563eb;
          color: #fff;
          box-shadow: 0 4px 10px rgba(37, 99, 235, .18);
        }

        .dsm-pro-btn.primary:hover:not(:disabled) {
          border-color: #1d4ed8;
          background: #1d4ed8;
        }

        .dsm-pro-btn.danger {
          border-color: #fecaca;
          color: #dc2626;
        }

        /* ROW 1 */
        .dsm-pro-connection {
          border-top: 3px solid #2563eb;
        }

        .dsm-pro-connection-form {
          display: grid;
          grid-template-columns: 1.55fr 1fr 1.35fr .72fr 1.2fr 1.35fr;
          gap: 14px;
          padding: 20px 22px 22px;
          background: #fff;
        }

        .dsm-pro-field {
          min-width: 0;
        }

        .dsm-pro-field label {
          display: block;
          margin-bottom: 7px;
          color: #43526a;
          font-size: 11px;
          font-weight: 750;
        }

        .dsm-pro-field input,
        .dsm-pro-field select {
          width: 100%;
          height: 40px;
          padding: 0 11px;
          border: 1px solid #cfd8e5;
          border-radius: 8px;
          outline: none;
          background: #fff;
          color: #172033;
          font: inherit;
          font-size: 12px;
          transition: .15s ease;
        }

        .dsm-pro-field input:focus,
        .dsm-pro-field select:focus {
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, .09);
        }

        .dsm-pro-connection-actions {
          grid-column: 1 / -1;
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 9px;
          padding-top: 2px;
          border-top: 1px solid #edf1f6;
        }

        .dsm-pro-message {
          margin: 0 22px 18px;
          padding: 10px 12px;
          border: 1px solid #bfdbfe;
          border-radius: 8px;
          background: #eff6ff;
          color: #1d4ed8;
          font-size: 11px;
        }

        .dsm-pro-message.error {
          border-color: #fecaca;
          background: #fef2f2;
          color: #b91c1c;
        }

        /* ROW 2 */
        .dsm-pro-dataset {
          border-top: 3px solid #7c3aed;
        }

        .dsm-pro-count {
          display: inline-flex;
          min-width: 46px;
          height: 38px;
          align-items: center;
          justify-content: center;
          padding: 0 12px;
          border: 1px solid #ddd6fe;
          border-radius: 10px;
          background: #f5f3ff;
          color: #6d28d9;
          font-size: 15px;
          font-weight: 800;
        }

        .dsm-pro-dataset-body {
          padding: 14px 18px 18px;
        }

        .dsm-pro-dataset-list {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 10px;
        }

        .dsm-pro-dataset-item {
          display: flex;
          align-items: center;
          gap: 11px;
          min-width: 0;
          padding: 12px;
          border: 1px solid #e1e7ef;
          border-radius: 10px;
          background: #fbfcfe;
        }

        .dsm-pro-dataset-index {
          display: inline-flex;
          width: 30px;
          height: 30px;
          flex: 0 0 30px;
          align-items: center;
          justify-content: center;
          border-radius: 8px;
          background: #eef2ff;
          color: #4338ca;
          font-size: 11px;
          font-weight: 800;
        }

        .dsm-pro-dataset-info {
          min-width: 0;
          flex: 1;
        }

        .dsm-pro-dataset-info strong,
        .dsm-pro-dataset-info small {
          display: block;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .dsm-pro-dataset-info strong {
          color: #1e293b;
          font-size: 12px;
        }

        .dsm-pro-dataset-info small {
          margin-top: 3px;
          color: #718096;
          font-size: 10px;
        }

        .dsm-pro-empty {
          padding: 25px 16px;
          border: 1px dashed #d4dce8;
          border-radius: 10px;
          background: #fbfcfe;
          color: #7a8799;
          font-size: 11px;
          text-align: center;
        }

        /* ROW 3 */
        .dsm-pro-workspace {
          display: grid;
          grid-template-columns: minmax(275px, 330px) minmax(0, 1fr);
          gap: 18px;
          align-items: stretch;
        }

        .dsm-pro-panel {
          min-width: 0;
          border: 1px solid #dfe5ee;
          border-radius: 14px;
          background: #fff;
          box-shadow: 0 4px 18px rgba(23, 32, 51, .045);
          overflow: hidden;
        }

        .dsm-pro-panel-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          padding: 18px;
          border-bottom: 1px solid #e8edf4;
        }

        .dsm-pro-panel-head h3 {
          font-size: 16px;
        }

        .dsm-pro-panel-head p {
          font-size: 11px;
        }

        .dsm-pro-refresh {
          width: 34px;
          height: 34px;
          border: 1px solid #d4dce8;
          border-radius: 8px;
          background: #fff;
          color: #4b5f78;
          font-size: 16px;
          cursor: pointer;
        }

        .dsm-pro-tree {
          padding: 10px;
        }

        .dsm-pro-connection-node {
          margin-bottom: 6px;
        }

        .dsm-pro-connection-row {
          display: flex;
          align-items: center;
          gap: 5px;
          min-width: 0;
          padding: 5px;
          border-radius: 9px;
        }

        .dsm-pro-connection-row.active {
          background: #eff6ff;
        }

        .dsm-pro-node-main {
          display: flex;
          align-items: center;
          flex: 1;
          min-width: 0;
          gap: 8px;
          padding: 7px;
          border: 0;
          background: transparent;
          color: inherit;
          text-align: left;
          cursor: pointer;
        }

        .dsm-pro-chevron {
          width: 14px;
          color: #718096;
          font-size: 11px;
        }

        .dsm-pro-status {
          width: 7px;
          height: 7px;
          flex: 0 0 7px;
          border-radius: 50%;
          background: #16a34a;
          box-shadow: 0 0 0 3px #dcfce7;
        }

        .dsm-pro-node-main div {
          min-width: 0;
        }

        .dsm-pro-node-main strong,
        .dsm-pro-node-main small {
          display: block;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .dsm-pro-node-main strong {
          color: #263449;
          font-size: 11px;
        }

        .dsm-pro-node-main small {
          margin-top: 2px;
          color: #8995a7;
          font-size: 9px;
        }

        .dsm-pro-node-actions {
          display: flex;
          gap: 2px;
        }

        .dsm-pro-node-actions button {
          border: 0;
          background: transparent;
          color: #6b7a90;
          font-size: 10px;
          cursor: pointer;
        }

        .dsm-pro-node-actions .delete {
          color: #dc2626;
        }

        .dsm-pro-databases {
          margin: 0 0 8px 28px;
          padding-left: 10px;
          border-left: 1px solid #e3e8f0;
        }

        .dsm-pro-db {
          display: flex;
          width: 100%;
          align-items: center;
          gap: 8px;
          padding: 8px 9px;
          border: 0;
          border-radius: 7px;
          background: transparent;
          color: #56657a;
          font: inherit;
          font-size: 10px;
          text-align: left;
          cursor: pointer;
        }

        .dsm-pro-db:hover,
        .dsm-pro-db.active {
          background: #f1f5f9;
          color: #1d4ed8;
        }

        .dsm-pro-db-refresh {
          width: 100%;
          margin-top: 4px;
          padding: 7px 9px;
          border: 0;
          background: transparent;
          color: #64748b;
          font-size: 9px;
          text-align: left;
          cursor: pointer;
        }

        .dsm-pro-registry {
          margin: 10px;
          padding: 10px;
          border: 1px solid #e0e7ff;
          border-radius: 9px;
          background: #f8faff;
        }

        .dsm-pro-registry strong {
          display: block;
          color: #4338ca;
          font-size: 9px;
        }

        .dsm-pro-registry span {
          display: block;
          margin-top: 3px;
          color: #718096;
          font-size: 9px;
          line-height: 1.45;
        }

        .dsm-pro-access-empty {
          display: grid;
          min-height: 360px;
          place-items: center;
          padding: 35px;
          text-align: center;
        }

        .dsm-pro-empty-icon {
          display: grid;
          width: 52px;
          height: 52px;
          margin: 0 auto 13px;
          place-items: center;
          border-radius: 14px;
          background: #eff6ff;
          color: #2563eb;
          font-size: 22px;
        }

        .dsm-pro-access-empty h3 {
          margin: 0;
          color: #172033;
          font-size: 17px;
        }

        .dsm-pro-access-empty p {
          max-width: 470px;
          margin: 7px auto 0;
          color: #7a8799;
          font-size: 11px;
          line-height: 1.55;
        }

        .dsm-pro-browser {
          min-width: 0;
        }

        .dsm-pro-browser-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 18px;
          padding: 18px 20px;
          border-bottom: 1px solid #e8edf4;
        }

        .dsm-pro-breadcrumb {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 5px;
          margin-bottom: 9px;
          color: #8090a5;
          font-size: 9px;
        }

        .dsm-pro-breadcrumb button {
          padding: 0;
          border: 0;
          background: transparent;
          color: #2563eb;
          font: inherit;
          cursor: pointer;
        }

        .dsm-pro-browser-tools {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-shrink: 0;
        }

        .dsm-pro-search {
          width: 190px;
          height: 34px;
          padding: 0 10px;
          border: 1px solid #d4dce8;
          border-radius: 8px;
          outline: none;
          font: inherit;
          font-size: 11px;
        }

        .dsm-pro-search:focus {
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, .08);
        }

        .dsm-pro-database-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
          gap: 10px;
          padding: 16px 18px;
        }

        .dsm-pro-database-card {
          display: flex;
          min-height: 92px;
          flex-direction: column;
          align-items: flex-start;
          justify-content: center;
          gap: 4px;
          padding: 13px;
          border: 1px solid #e0e6ef;
          border-radius: 10px;
          background: #fff;
          text-align: left;
          cursor: pointer;
          transition: .15s ease;
        }

        .dsm-pro-database-card:hover {
          border-color: #93c5fd;
          background: #f8fbff;
          box-shadow: 0 5px 14px rgba(37, 99, 235, .08);
          transform: translateY(-1px);
        }

        .dsm-pro-database-icon {
          color: #2563eb;
          font-size: 17px;
        }

        .dsm-pro-database-card strong {
          color: #263449;
          font-size: 11px;
        }

        .dsm-pro-database-card small {
          color: #8995a7;
          font-size: 9px;
        }

        .dsm-pro-object-list {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
          gap: 9px;
          padding: 16px 18px;
        }

        .dsm-pro-object-card {
          display: flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
          padding: 12px;
          border: 1px solid #e1e7ef;
          border-radius: 9px;
          background: #fff;
          text-align: left;
          cursor: pointer;
        }

        .dsm-pro-object-card:hover {
          border-color: #93c5fd;
          background: #f8fbff;
        }

        .dsm-pro-object-icon {
          color: #475569;
          font-size: 17px;
        }

        .dsm-pro-object-card div {
          min-width: 0;
          flex: 1;
        }

        .dsm-pro-object-card strong,
        .dsm-pro-object-card small {
          display: block;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .dsm-pro-object-card strong {
          color: #263449;
          font-size: 11px;
        }

        .dsm-pro-object-card small {
          margin-top: 3px;
          color: #8a96a8;
          font-size: 9px;
        }

        .dsm-pro-inspector {
          min-width: 0;
        }

        .dsm-pro-inspector-tools {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .dsm-pro-select-label {
          display: flex;
          align-items: center;
          gap: 6px;
          color: #738197;
          font-size: 9px;
          font-weight: 700;
        }

        .dsm-pro-select-label select {
          height: 34px;
          border: 1px solid #d4dce8;
          border-radius: 8px;
          padding: 0 8px;
          background: #fff;
          font: inherit;
          font-size: 10px;
        }

        .dsm-pro-metrics {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px;
          padding: 14px 18px;
        }

        .dsm-pro-metric {
          padding: 11px 12px;
          border: 1px solid #e1e7ef;
          border-radius: 9px;
          background: #fbfcfe;
        }

        .dsm-pro-metric strong,
        .dsm-pro-metric span {
          display: block;
        }

        .dsm-pro-metric strong {
          color: #172033;
          font-size: 15px;
        }

        .dsm-pro-metric span {
          margin-top: 3px;
          color: #7d8a9e;
          font-size: 9px;
        }

        .dsm-pro-subhead {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 13px 18px 9px;
          border-top: 1px solid #edf1f6;
        }

        .dsm-pro-subhead h4 {
          margin: 0;
          color: #263449;
          font-size: 12px;
        }

        .dsm-pro-subhead span {
          color: #8a96a8;
          font-size: 9px;
        }

        .dsm-pro-table-wrap {
          width: 100%;
          max-height: 245px;
          overflow: auto;
          border-top: 1px solid #edf1f6;
        }

        .dsm-pro-table-wrap table {
          width: 100%;
          min-width: 680px;
          border-collapse: collapse;
          font-size: 9px;
        }

        .dsm-pro-table-wrap th,
        .dsm-pro-table-wrap td {
          padding: 8px 10px;
          border-bottom: 1px solid #edf1f6;
          text-align: left;
          white-space: nowrap;
        }

        .dsm-pro-table-wrap th {
          position: sticky;
          top: 0;
          z-index: 1;
          background: #f8fafc;
          color: #64748b;
          font-size: 8px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: .04em;
        }

        .dsm-pro-table-wrap td {
          color: #4b5b71;
        }

        .dsm-pro-type {
          display: inline-block;
          padding: 3px 6px;
          border-radius: 5px;
          background: #eef2ff;
          color: #4338ca;
          font-size: 8px;
        }

        .dsm-pro-footer-note {
          padding: 11px 18px;
          color: #8a96a8;
          font-size: 9px;
          text-align: right;
        }

        @media (max-width: 1050px) {
          .dsm-pro-connection-form {
            grid-template-columns: repeat(3, 1fr);
          }

          .dsm-pro-workspace {
            grid-template-columns: 260px minmax(0, 1fr);
          }
        }

        @media (max-width: 780px) {
          .dsm-pro-dashboard {
            padding: 18px 12px 30px;
          }

          .dsm-pro-connection-form,
          .dsm-pro-workspace {
            grid-template-columns: 1fr;
          }

          .dsm-pro-metrics {
            grid-template-columns: repeat(2, 1fr);
          }

          .dsm-pro-section-head,
          .dsm-pro-browser-head {
            align-items: flex-start;
            flex-direction: column;
          }

          .dsm-pro-browser-tools,
          .dsm-pro-connection-actions {
            width: 100%;
            justify-content: flex-start;
            flex-wrap: wrap;
          }
        }
      `}</style>

      {/* =====================================================
          ROW 1 — NEW DATABASE CONNECTION
          ===================================================== */}
      <section className="dsm-pro-section dsm-pro-connection">
        <div className="dsm-pro-section-head">
          <div>
            <span className="dsm-pro-eyebrow">ROW 1 · CONNECTION MANAGER</span>
            <h2>
              {editingConnectionId
                ? "Edit Saved Connection"
                : "New Database Connection"}
            </h2>
            <p>
              Create a reusable connection once. Saved connections can
              be browsed from the database panel without re-entering
              credentials.
            </p>
          </div>

          <div className="dsm-pro-section-actions">
            {editingConnectionId && (
              <button
                className="dsm-pro-btn"
                onClick={() => {
                  resetConnectionForm();
                  setMessage("");
                }}
              >
                Cancel Edit
              </button>
            )}

            <button
              className="dsm-pro-btn danger"
              disabled={busy || connections.length === 0}
              onClick={deleteAllConnections}
            >
              Delete All Connections
            </button>

            <button
              className="dsm-pro-btn"
              onClick={() =>
                setShowConnectionForm((value) => !value)
              }
            >
              {showConnectionForm ? "Collapse" : "+ New Connection"}
            </button>
          </div>
        </div>

        {showConnectionForm && (
          <div className="dsm-pro-connection-form">
            <div className="dsm-pro-field">
              <label>Connection Name</label>
              <input
                value={connectionForm.name}
                onChange={(e) =>
                  handleConnectionField("name", e.target.value)
                }
                placeholder="e.g. PSPCL MySQL"
              />
            </div>

            <div className="dsm-pro-field">
              <label>Database Platform</label>
              <select
                value={connectionForm.source_type}
                onChange={(e) =>
                  handleConnectionField(
                    "source_type",
                    e.target.value
                  )
                }
              >
                {(connectors.length ? connectors : [
                  { id: "mysql", name: "MySQL", source_type: "mysql" },
                  { id: "mongodb", name: "MongoDB", source_type: "mongodb" },
                ]).map((connector) => (
                  <option
                    key={connector.id || connector.source_type}
                    value={connector.source_type || connector.type || connector.id}
                  >
                    {connector.name || connector.label || sourceLabel(connector.source_type || connector.type || connector.id)}
                  </option>
                ))}
              </select>
            </div>

            <div className="dsm-pro-field">
              <label>Host</label>
              <input
                value={connectionForm.host}
                onChange={(e) =>
                  handleConnectionField("host", e.target.value)
                }
                placeholder="localhost"
              />
            </div>

            <div className="dsm-pro-field">
              <label>Port</label>
              <input
                type="number"
                value={connectionForm.port}
                onChange={(e) =>
                  handleConnectionField("port", e.target.value)
                }
                placeholder="3306"
              />
            </div>

            <div className="dsm-pro-field">
              <label>Username</label>
              <input
                value={connectionForm.username}
                onChange={(e) =>
                  handleConnectionField(
                    "username",
                    e.target.value
                  )
                }
                placeholder="root"
              />
            </div>

            <div className="dsm-pro-field">
              <label>Password</label>
              <input
                type="password"
                value={connectionForm.password}
                onChange={(e) =>
                  handleConnectionField(
                    "password",
                    e.target.value
                  )
                }
                placeholder={
                  editingConnectionId
                    ? "Leave blank to keep existing"
                    : "Database password"
                }
              />
            </div>

            <div className="dsm-pro-connection-actions">
              <button
                className="dsm-pro-btn"
                disabled={busy}
                onClick={testNewConnection}
              >
                Test Connection
              </button>

              <button
                className="dsm-pro-btn primary"
                disabled={busy}
                onClick={saveConnection}
              >
                {editingConnectionId
                  ? "Save Changes"
                  : "Test & Save Connection"}
              </button>
            </div>
          </div>
        )}

        {message && (
          <div
            className={
              message.startsWith("Error:")
                ? "dsm-pro-message error"
                : "dsm-pro-message"
            }
          >
            {message}
          </div>
        )}
      </section>

      {/* =====================================================
          ROW 2 — TABLES ADDED FOR REPORTING
          ===================================================== */}
      <section className="dsm-pro-section dsm-pro-dataset">
        <div className="dsm-pro-section-head">
          <div>
            <span className="dsm-pro-eyebrow">ROW 2 · CURRENT REPORTING DATASET</span>
            <h3>Tables Added for Reporting</h3>
            <p>
              Your selected tables and collections are persisted and
              will be available to Data Preview, Join Designer and
              Report Builder.
            </p>
          </div>

          <span className="dsm-pro-count">{datasets.length}</span>
        </div>

        <div className="dsm-pro-dataset-body">
          {datasets.length === 0 ? (
            <div className="dsm-pro-empty">
              No reporting tables have been added yet. Use
              <strong> Access Database </strong>
              below to select a saved connection, database and table,
              then preview it before adding it to the reporting dataset.
            </div>
          ) : (
            <div className="dsm-pro-dataset-list">
              {datasets.map((dataset, index) => (
                <div className="dsm-pro-dataset-item" key={dataset.id}>
                  <span className="dsm-pro-dataset-index">
                    {String.fromCharCode(65 + index)}
                  </span>

                  <div className="dsm-pro-dataset-info">
                    <strong>
                      {dataset.object_name || dataset.name}
                    </strong>
                    <small>
                      {dataset.connection_name ||
                        connections.find(
                          (item) =>
                            item.id === dataset.connection_id
                        )?.name ||
                        "Saved Connection"}{" "}
                      · {dataset.database} ·{" "}
                      {dataset.columns?.length || 0} columns
                    </small>
                  </div>

                  <button
                    className="dsm-pro-btn danger"
                    disabled={busy}
                    onClick={() => removeDataset(dataset.id)}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* =====================================================
          ROW 3 — ACCESS DATABASE / TABLES & PREVIEW
          ===================================================== */}
      <div className="dsm-pro-workspace">
        {/* LEFT — ACCESS DATABASE */}
        <aside className="dsm-pro-panel">
          <div className="dsm-pro-panel-head">
            <div>
              <span className="dsm-pro-eyebrow">ROW 3 · COLUMN 1</span>
              <h3>Access Database</h3>
              <p>
                Choose a saved connection and navigate its databases.
              </p>
            </div>

            <button
              className="dsm-pro-refresh"
              title="Refresh saved connections"
              disabled={busy}
              onClick={() => loadConnections()}
            >
              ↻
            </button>
          </div>

          {connections.length === 0 ? (
            <div className="dsm-pro-access-empty">
              <div>
                <div className="dsm-pro-empty-icon">⌁</div>
                <h3>No Saved Connections</h3>
                <p>
                  Create your MySQL or MongoDB connection in Row 1.
                  Once saved, it will appear here and can be browsed
                  independently.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="dsm-pro-tree">
                {connections.map((connection) => {
                  const isOpen =
                    !!expandedConnections[connection.id];
                  const isSelected =
                    selectedConnectionId === connection.id;
                  const dbs =
                    databasesByConnection[connection.id] || [];

                  return (
                    <div
                      className="dsm-pro-connection-node"
                      key={connection.id}
                    >
                      <div
                        className={
                          isSelected
                            ? "dsm-pro-connection-row active"
                            : "dsm-pro-connection-row"
                        }
                      >
                        <button
                          className="dsm-pro-node-main"
                          onClick={() =>
                            toggleConnection(connection)
                          }
                        >
                          <span className="dsm-pro-chevron">
                            {isOpen ? "▾" : "▸"}
                          </span>

                          <span className="dsm-pro-status" />

                          <div>
                            <strong>{connection.name}</strong>
                            <small>
                              {sourceLabel(connection.source_type)}{" "}
                              · {connection.host}:{connection.port}
                            </small>
                          </div>
                        </button>

                        <div className="dsm-pro-node-actions">
                          <button
                            title="Edit connection"
                            onClick={() =>
                              editConnection(connection)
                            }
                          >
                            Edit
                          </button>

                          <button
                            className="delete"
                            title="Delete connection"
                            onClick={() =>
                              deleteConnection(connection)
                            }
                          >
                            ×
                          </button>
                        </div>
                      </div>

                      {isOpen && (
                        <div className="dsm-pro-databases">
                          {dbs.length === 0 ? (
                            <div className="dsm-pro-tree-muted">
                              {busy
                                ? "Loading databases..."
                                : "No databases loaded yet."}
                            </div>
                          ) : (
                            dbs.map((db) => (
                              <button
                                key={db}
                                className={
                                  isSelected &&
                                  selectedDatabase === db
                                    ? "dsm-pro-db active"
                                    : "dsm-pro-db"
                                }
                                onClick={() =>
                                  selectDatabase(
                                    connection,
                                    db
                                  )
                                }
                              >
                                <span>◈</span>
                                <span>{db}</span>
                              </button>
                            ))
                          )}

                          <button
                            className="dsm-pro-db-refresh"
                            disabled={busy}
                            onClick={() =>
                              loadDatabases(connection, true)
                            }
                          >
                            ↻ Refresh databases
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="dsm-pro-registry">
                <strong>Saved Connection Registry</strong>
                <span>
                  Credentials remain attached to the saved connection.
                  Reporting datasets reference the connection ID.
                </span>
              </div>
            </>
          )}
        </aside>

        {/* RIGHT — TABLES / PREVIEW */}
        <main className="dsm-pro-panel dsm-pro-browser">
          {!selectedConnection ? (
            <div className="dsm-pro-access-empty">
              <div>
                <div className="dsm-pro-empty-icon">◫</div>
                <span className="dsm-pro-eyebrow">
                  ROW 3 · COLUMN 2
                </span>
                <h3>Tables & Data Preview</h3>
                <p>
                  Select a saved connection from Access Database.
                  Its databases will appear here, followed by its
                  tables or collections.
                </p>
              </div>
            </div>
          ) : !selectedDatabase ? (
            <div>
              <div className="dsm-pro-browser-head">
                <div>
                  <span className="dsm-pro-eyebrow">SAVED CONNECTION</span>
                  <h3>{selectedConnection.name}</h3>
                  <p>
                    {sourceLabel(selectedConnection.source_type)} ·{" "}
                    {selectedConnection.host}:{selectedConnection.port}
                  </p>
                </div>

                <button
                  className="dsm-pro-btn"
                  disabled={busy}
                  onClick={() =>
                    loadDatabases(selectedConnection, true)
                  }
                >
                  ↻ Refresh
                </button>
              </div>

              <div className="dsm-pro-database-grid">
                {databases.map((db) => (
                  <button
                    key={db}
                    className="dsm-pro-database-card"
                    onClick={() =>
                      selectDatabase(
                        selectedConnection,
                        db
                      )
                    }
                  >
                    <span className="dsm-pro-database-icon">◈</span>
                    <strong>{db}</strong>
                    <small>
                      {selectedConnection.source_type === "mysql"
                        ? "Database / Schema"
                        : "MongoDB Database"}
                    </small>
                  </button>
                ))}
              </div>

              {databases.length === 0 && (
                <div style={{ padding: "18px" }}>
                  <div className="dsm-pro-empty">
                    No databases found for this connection.
                  </div>
                </div>
              )}
            </div>
          ) : !selectedObject ? (
            <div>
              <div className="dsm-pro-browser-head">
                <div>
                  <div className="dsm-pro-breadcrumb">
                    <button
                      onClick={() => {
                        setSelectedDatabase("");
                        setObjects([]);
                        setSelectedObject("");
                        setPreview(null);
                      }}
                    >
                      {selectedConnection.name}
                    </button>
                    <span>›</span>
                    <strong>{selectedDatabase}</strong>
                  </div>

                  <span className="dsm-pro-eyebrow">
                    AVAILABLE {objectLabel(selectedConnection.source_type).toUpperCase()}S
                  </span>
                  <h3>
                    {objectLabel(selectedConnection.source_type)}s in{" "}
                    {selectedDatabase}
                  </h3>
                  <p>
                    Choose a table or collection to inspect before
                    adding it to the reporting dataset.
                  </p>
                </div>

                <div className="dsm-pro-browser-tools">
                  <input
                    className="dsm-pro-search"
                    value={search}
                    onChange={(e) =>
                      setSearch(e.target.value)
                    }
                    placeholder={`Search ${objectLabel(
                      selectedConnection.source_type
                    ).toLowerCase()}s...`}
                  />

                  <button
                    className="dsm-pro-btn"
                    disabled={busy}
                    onClick={() =>
                      loadDatabases(
                        selectedConnection,
                        true
                      )
                    }
                  >
                    ↻
                  </button>
                </div>
              </div>

              <div className="dsm-pro-object-list">
                {filteredObjects.map((item) => {
                  const name = item?.name || item;

                  return (
                    <button
                      key={name}
                      className="dsm-pro-object-card"
                      onClick={() =>
                        previewObject(
                          selectedConnection,
                          selectedDatabase,
                          name
                        )
                      }
                    >
                      <span className="dsm-pro-object-icon">▦</span>

                      <div>
                        <strong>{name}</strong>
                        <small>
                          {item?.type ||
                            objectLabel(
                              selectedConnection.source_type
                            )}
                        </small>
                      </div>

                      <span>›</span>
                    </button>
                  );
                })}
              </div>

              {filteredObjects.length === 0 && (
                <div style={{ padding: "0 18px 18px" }}>
                  <div className="dsm-pro-empty">
                    No{" "}
                    {objectLabel(
                      selectedConnection.source_type
                    ).toLowerCase()}
                    s found in {selectedDatabase}.
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="dsm-pro-inspector">
              <div className="dsm-pro-browser-head">
                <div>
                  <div className="dsm-pro-breadcrumb">
                    <button
                      onClick={() => {
                        setSelectedDatabase("");
                        setObjects([]);
                        setSelectedObject("");
                        setPreview(null);
                      }}
                    >
                      {selectedConnection.name}
                    </button>
                    <span>›</span>
                    <button
                      onClick={() => {
                        setSelectedObject("");
                        setPreview(null);
                      }}
                    >
                      {selectedDatabase}
                    </button>
                    <span>›</span>
                    <strong>{selectedObject}</strong>
                  </div>

                  <span className="dsm-pro-eyebrow">
                    TABLE / COLLECTION INSPECTOR
                  </span>
                  <h3>{selectedObject}</h3>
                  <p>
                    {sourceLabel(selectedConnection.source_type)} ·{" "}
                    {selectedDatabase} · saved connection
                  </p>
                </div>

                <div className="dsm-pro-inspector-tools">
                  <label className="dsm-pro-select-label">
                    Preview
                    <select
                      value={sampleLimit}
                      onChange={(e) => {
                        const value = Number(e.target.value);
                        setSampleLimit(value);
                        previewObject(
                          selectedConnection,
                          selectedDatabase,
                          selectedObject,
                          value
                        );
                      }}
                    >
                      {PREVIEW_ROW_OPTIONS.map((option) => (
                        <option key={option} value={option}>{worksheetRowLabel(option)}</option>
                      ))}
                    </select>
                  </label>

                  <button
                    className="dsm-pro-btn"
                    disabled={busy}
                    onClick={() =>
                      previewObject(
                        selectedConnection,
                        selectedDatabase,
                        selectedObject
                      )
                    }
                  >
                    ↻
                  </button>

                  <button
                    className="dsm-pro-btn primary"
                    disabled={!preview || busy}
                    onClick={addToDataset}
                  >
                    + Add to Reporting
                  </button>
                </div>
              </div>

              {preview && (
                <>
                  <div className="dsm-pro-metrics">
                    <div className="dsm-pro-metric">
                      <strong>
                        {Number(
                          preview.total_rows || 0
                        ).toLocaleString()}
                      </strong>
                      <span>Total Rows</span>
                    </div>

                    <div className="dsm-pro-metric">
                      <strong>
                        {preview.columns?.length || 0}
                      </strong>
                      <span>Columns</span>
                    </div>

                    <div className="dsm-pro-metric">
                      <strong>
                        {preview.rows?.length || 0}
                      </strong>
                      <span>Preview Rows</span>
                    </div>

                    <div className="dsm-pro-metric">
                      <strong>
                        {objectLabel(
                          selectedConnection.source_type
                        )}
                      </strong>
                      <span>Object Type</span>
                    </div>
                  </div>

                  <div className="dsm-pro-subhead">
                    <h4>Column Overview</h4>
                    <span>
                      {preview.columns?.length || 0} fields
                    </span>
                  </div>

                  <div className="dsm-pro-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Column</th>
                          <th>Data Type</th>
                          <th>Rows</th>
                          <th>Non-Null</th>
                          <th>Nulls</th>
                          <th>Distinct</th>
                          <th>Example</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(preview.column_profiles || []).map(
                          (column) => {
                            const total = Number(
                              column.total_count ??
                                preview.total_rows ??
                                preview.rows?.length ??
                                0
                            );
                            const nulls = Number(
                              column.null_count || 0
                            );

                            return (
                              <tr key={column.name}>
                                <td>
                                  <strong>{column.name}</strong>
                                </td>
                                <td>
                                  <span className="dsm-pro-type">
                                    {column.data_type || "unknown"}
                                  </span>
                                </td>
                                <td>{total.toLocaleString()}</td>
                                <td>
                                  {Math.max(
                                    total - nulls,
                                    0
                                  ).toLocaleString()}
                                </td>
                                <td>{nulls.toLocaleString()}</td>
                                <td>
                                  {Number(
                                    column.distinct_count || 0
                                  ).toLocaleString()}
                                </td>
                                <td
                                  title={valueText(
                                    column.example
                                  )}
                                >
                                  {valueText(column.example)}
                                </td>
                              </tr>
                            );
                          }
                        )}
                      </tbody>
                    </table>
                  </div>

                  <div className="dsm-pro-subhead">
                    <h4>Sample Records</h4>
                    <span>
                      {preview.rows?.length || 0} rows shown
                    </span>
                  </div>

                  <div className="dsm-pro-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          {(preview.columns || []).map(
                            (column) => (
                              <th key={column}>{column}</th>
                            )
                          )}
                        </tr>
                      </thead>

                      <tbody>
                        {(preview.rows || []).map(
                          (row, index) => (
                            <tr key={index}>
                              {(preview.columns || []).map(
                                (column) => (
                                  <td
                                    key={column}
                                    title={valueText(
                                      row[column]
                                    )}
                                  >
                                    {valueText(row[column])}
                                  </td>
                                )
                              )}
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                  </div>

                  <div className="dsm-pro-footer-note">
                    Previewing {selectedObject}. Add this object to
                    the reporting dataset only after confirming its
                    structure and row profile.
                  </div>
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
