import { API, apiFetch } from "./authClient";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PREVIEW_ROW_OPTIONS, worksheetRowLabel } from "./worksheetLimits";
import { submitExecutionJob, waitForExecutionJob } from "./executionClient";
import { PagedVirtualizedTable } from "./PagedVirtualizedTable.jsx";
import { createRequestCoordinator } from "./requestCoordinator";
import { collectPreviewFilterValues, filterPreviewRows } from "./dataPreviewPerformance";

/*
 * ============================================================
 * COMPONENT CSS OWNERSHIP
 * ============================================================
 * Data Preview owns its presentation styles. The component no longer
 * depends on App.css for its UI styling. This refactor intentionally
 * preserves the existing Data Preview markup, behavior, API calls,
 * dataset handling, preview filtering, and report handoff logic.
 * ============================================================
 */


function formatNumber(value) {
  return new Intl.NumberFormat().format(Number(value || 0));
}

function formatCell(value) {
  if (value === null || value === undefined || value === "") return "—";

  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  return String(value);
}

function getSourceType(dataset) {
  return String(
    dataset?.sourceType ||
      dataset?.source_type ||
      dataset?.platform ||
      dataset?.connection?.source_type ||
      dataset?.connection?.sourceType ||
      ""
  ).toLowerCase();
}

function getDatabase(dataset) {
  return (
    dataset?.database ||
    dataset?.db ||
    dataset?.schema ||
    ""
  );
}

function getObjectName(dataset) {
  return (
    dataset?.table ||
    dataset?.table_name ||
    dataset?.collection ||
    dataset?.collection_name ||
    dataset?.object_name ||
    dataset?.objectName ||
    dataset?.name ||
    ""
  );
}

function getConnectionId(dataset) {
  return (
    dataset?.connectionId ||
    dataset?.connection_id ||
    dataset?.connection?.id ||
    ""
  );
}

function getConnectionName(dataset) {
  return (
    dataset?.connection_name ||
    dataset?.connectionName ||
    dataset?.source_name ||
    dataset?.connection?.name ||
    ""
  );
}

function sourceLabel(sourceType) {
  const value = String(sourceType || "").toLowerCase();

  if (value === "mongodb" || value === "mongo") return "MongoDB";
  if (value === "mysql") return "MySQL";

  return String(sourceType || "Database");
}

function datasetLabel(dataset) {
  if (!dataset) return "";

  const connection =
    getConnectionName(dataset) ||
    sourceLabel(getSourceType(dataset));

  return [
    connection,
    getDatabase(dataset),
    getObjectName(dataset),
  ]
    .filter(Boolean)
    .join(" → ");
}

function getHierarchy(dataset) {
  const hierarchy =
    dataset?.hierarchy ||
    dataset?.hierarchy_details ||
    dataset?.hierarchyDetails ||
    dataset?.location_hierarchy;

  if (typeof hierarchy === "string" && hierarchy.trim()) {
    return hierarchy;
  }

  if (hierarchy && typeof hierarchy === "object") {
    return Object.entries(hierarchy)
      .filter(
        ([, value]) =>
          value !== null &&
          value !== undefined &&
          value !== ""
      )
      .map(([key, value]) => `${key}: ${formatCell(value)}`)
      .join("  •  ");
  }

  const parts = [
    ["Zone", dataset?.zone || dataset?.ZONE],
    ["Circle", dataset?.circle || dataset?.CIRCLE],
    ["Division", dataset?.division || dataset?.DIVISION],
    ["Sub Division", dataset?.subDivision || dataset?.["SUB DIVISION"]],
    ["Sub Station", dataset?.subStation || dataset?.["SUB STATION"]],
    ["Feeder", dataset?.feeder || dataset?.FEEDER],
  ]
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key}: ${value}`);

  return parts.length
    ? parts.join("  •  ")
    : "Hierarchy information not available";
}

function inferColumnProfile(columnName, rows, existing) {
  if (existing) return existing;

  const values = rows
    .map((row) => row?.[columnName])
    .filter(
      (value) =>
        value !== null &&
        value !== undefined &&
        value !== ""
    );

  const nullCount = rows.length - values.length;

  const distinctValues = new Set(
    values.map((value) =>
      typeof value === "object"
        ? JSON.stringify(value)
        : String(value)
    )
  );

  let dataType = "unknown";

  if (values.length) {
    const sample = values[0];

    if (typeof sample === "number") {
      dataType = Number.isInteger(sample)
        ? "integer"
        : "number";
    } else if (typeof sample === "boolean") {
      dataType = "boolean";
    } else if (typeof sample === "object") {
      dataType = "object";
    } else {
      dataType = "string";
    }
  }

  return {
    name: columnName,
    data_type: dataType,
    null_count: nullCount,
    null_percent: rows.length
      ? (nullCount / rows.length) * 100
      : 0,
    distinct_count: distinctValues.size,
    example: values.length ? values[0] : null,
  };
}

function normalisePreview(data, selectedDataset) {
  const rows = Array.isArray(data?.rows) ? data.rows : [];
  const columns = Array.isArray(data?.columns)
    ? data.columns
    : rows.length
    ? Object.keys(rows[0])
    : [];

  const existingProfiles = Array.isArray(data?.column_profiles)
    ? data.column_profiles
    : [];

  const columnProfiles = columns.map((columnName) => {
    const existing = existingProfiles.find(
      (item) => item && item.name === columnName
    );

    return inferColumnProfile(
      columnName,
      rows,
      existing
    );
  });

  return {
    ...data,
    rows,
    columns,
    column_profiles: columnProfiles,
    total_rows:
      data?.total_rows ??
      data?.row_count ??
      selectedDataset?.total_rows ??
      selectedDataset?.row_count ??
      rows.length,
    sample_rows:
      data?.sample_rows ??
      rows.length,
    column_count:
      data?.column_count ??
      columns.length,
  };
}

export default function DataPreview({
  datasets = [],
  onBack,
  onSendToReportBuilder,
  onSendToDashboard,
}) {
  /*
   * MULTI DATASET PREVIEW
   *
   * A dataset is only a reference to the saved connection.
   * Preview therefore continues to use:
   *
   * dataset -> connection_id -> saved connection -> object
   *
   * No credentials are required here.
   */

  const [selectedIds, setSelectedIds] = useState(
    () => datasets.slice(0, 2).map((item) => item.id)
  );

  const [previewMap, setPreviewMap] = useState({});
  const [selectedColumnsMap, setSelectedColumnsMap] = useState({});
  const [columnSearchMap, setColumnSearchMap] = useState({});
  const [sampleLimit, setSampleLimit] = useState(25);
  const [loadingMap, setLoadingMap] = useState({});
  const [errorMap, setErrorMap] = useState({});
  const [lastRefreshMap, setLastRefreshMap] = useState({});
  const previousSampleLimitRef = useRef(sampleLimit);
  const previewRequestCoordinatorRef = useRef(null);
  const previewRequestTokenRef = useRef(new Map());
  const previewRequestSequenceRef = useRef(0);

  if (previewRequestCoordinatorRef.current == null) {
    previewRequestCoordinatorRef.current = createRequestCoordinator();
  }

  // Identification filter for each dataset's loaded preview.
  // This is UI-only and does not alter the source database or dataset definition.
  const [previewFilterMap, setPreviewFilterMap] = useState({});

  useEffect(() => {
    const validIds = new Set(datasets.map((item) => item.id));

    // Intentional state reconciliation when the dataset list changes.
    setSelectedIds((current) => {
      const valid = current.filter((id) => validIds.has(id));

      if (valid.length) return valid;

      return datasets.slice(0, 2).map((item) => item.id);
    });
  }, [datasets]);

  const selectedDatasets = useMemo(
    () =>
      selectedIds
        .map((id) => datasets.find((dataset) => dataset.id === id))
        .filter(Boolean),
    [datasets, selectedIds]
  );

  const fetchPreview = useCallback(async (
    dataset,
    {
      silent = false,
      preserveColumns = true,
      sampleLimitOverride,
    } = {}
  ) => {
    if (!dataset?.id) return;

    const datasetId = dataset.id;
    const connectionId = getConnectionId(dataset);
    const sourceType = getSourceType(dataset);
    const database = getDatabase(dataset);
    const objectName = getObjectName(dataset);
    const sampleLimitValue = Number(sampleLimitOverride ?? 25) || 25;
    const requestToken = ++previewRequestSequenceRef.current;

    previewRequestTokenRef.current.set(datasetId, requestToken);
    previewRequestCoordinatorRef.current.cancel(`preview:${datasetId}`);

    setLoadingMap((current) => ({
      ...current,
      [datasetId]: true,
    }));

    if (!silent) {
      setErrorMap((current) => ({
        ...current,
        [datasetId]: "",
      }));
    }

    const isCurrent = () =>
      previewRequestTokenRef.current.get(datasetId) === requestToken;

    try {
      const result = await previewRequestCoordinatorRef.current.request(
        `preview:${datasetId}`,
        async ({ signal }) => {
          const endpoint = connectionId
            ? `${API}/datasource/connections/${encodeURIComponent(connectionId)}/preview`
            : `${API}/datasource/preview`;

          const body = connectionId
            ? {
                database,
                table: objectName,
                sample_limit: sampleLimitValue,
              }
            : {
                source_type: sourceType,
                host: dataset?.host,
                port: Number(dataset?.port),
                username: dataset?.username || null,
                password: dataset?.password || null,
                database,
                table: objectName,
                sample_limit: sampleLimitValue,
              };

          const response = await apiFetch(endpoint, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            body: JSON.stringify(body),
            signal,
          });

          const data = await response.json();

          if (!response.ok || !data.success) {
            const detail = Array.isArray(data?.detail)
              ? data.detail
                  .map((item) =>
                    typeof item === "object"
                      ? item?.msg || item?.message || JSON.stringify(item)
                      : String(item)
                  )
                  .join("; ")
              : typeof data?.detail === "object"
              ? data.detail?.msg || data.detail?.message || JSON.stringify(data.detail)
              : data?.detail;

            throw new Error(
              data?.message ||
                detail ||
                `Preview failed with HTTP ${response.status}.`
            );
          }

          return normalisePreview(data, dataset);
        }
      );

      if (!isCurrent()) return;

      setPreviewMap((current) => ({
        ...current,
        [datasetId]: result,
      }));

      setLastRefreshMap((current) => ({
        ...current,
        [datasetId]: new Date(),
      }));

      if (!preserveColumns) {
        setSelectedColumnsMap((current) => ({
          ...current,
          [datasetId]: result.columns,
        }));
      } else {
        setSelectedColumnsMap((current) => {
          const existing = current[datasetId];

          if (!existing?.length) {
            return {
              ...current,
              [datasetId]: result.columns,
            };
          }

          const valid = existing.filter((column) =>
            result.columns.includes(column)
          );

          return {
            ...current,
            [datasetId]: valid.length ? valid : result.columns,
          };
        });
      }

      setErrorMap((current) => ({
        ...current,
        [datasetId]: "",
      }));
    } catch (error) {
      if (!isCurrent() || error?.name === "AbortError") return;

      console.error(
        `Preview failed for ${datasetLabel(dataset)}`,
        error
      );

      const errorText =
        typeof error?.message === "string"
          ? error.message
          : typeof error === "string"
          ? error
          : JSON.stringify(error);

      setErrorMap((current) => ({
        ...current,
        [datasetId]: errorText || "Unable to load dataset preview.",
      }));
    } finally {
      if (isCurrent()) {
        setLoadingMap((current) => ({
          ...current,
          [datasetId]: false,
        }));
      }
    }
  }, []);

  useEffect(() => {
    if (!selectedDatasets.length) return;

    selectedDatasets.forEach((dataset) => {
      fetchPreview(dataset, {
        silent: true,
        preserveColumns: false,
      });
    });
  }, [selectedDatasets, fetchPreview]);

  useEffect(() => {
    if (previousSampleLimitRef.current === sampleLimit) return;
    previousSampleLimitRef.current = sampleLimit;

    if (!selectedDatasets.length) return;

    selectedDatasets.forEach((dataset) => {
      fetchPreview(dataset, {
        silent: true,
        preserveColumns: true,
        sampleLimitOverride: sampleLimit,
      });
    });
  }, [sampleLimit, selectedDatasets, fetchPreview]);

  const toggleDataset = (datasetId) => {
    setSelectedIds((current) => {
      if (current.includes(datasetId)) {
        return current.filter((id) => id !== datasetId);
      }

      return [...current, datasetId];
    });
  };

  const selectAllDatasets = () => {
    setSelectedIds(datasets.map((dataset) => dataset.id));
  };

  const clearDatasets = () => {
    setSelectedIds([]);
  };

  const refreshAll = () => {
    selectedDatasets.forEach((dataset) => {
      fetchPreview(dataset, {
        silent: false,
        preserveColumns: true,
      });
    });
  };

  const refreshDataset = (dataset) => {
    fetchPreview(dataset, {
      silent: false,
      preserveColumns: true,
    });
  };

  /*
   * COMPLETE REPORT HANDOFF
   *
   * The preview is intentionally sampled for interactive inspection. Sending
   * a dataset to Report Builder must not silently send only those sample rows.
   * Re-fetch the selected saved dataset at the worksheet ceiling before the
   * handoff, then Report Builder receives the complete available result.
   */
  const sendDatasetToReportBuilder = async (dataset, destination = "report") => {
    const datasetId = dataset?.id;
    const connectionId = getConnectionId(dataset);

    if (!datasetId || !connectionId) {
      setErrorMap((current) => ({
        ...current,
        [datasetId || "unknown"]:
          "A saved connection is required to execute this dataset.",
      }));
      return;
    }

    const selectedColumns =
      selectedColumnsMap[datasetId]?.length
        ? selectedColumnsMap[datasetId]
        : previewMap[datasetId]?.columns || [];

    if (!selectedColumns.length) {
      setErrorMap((current) => ({
        ...current,
        [datasetId]:
          "Select at least one column before sending the dataset to Report Builder.",
      }));
      return;
    }

    setLoadingMap((current) => ({ ...current, [datasetId]: true }));
    setErrorMap((current) => ({ ...current, [datasetId]: "" }));

    try {
      // Handoff is an execution boundary, not a preview-row copy. The preview
      // endpoint intentionally returns a small interactive sample, so create a
      // real execution job from the saved-connection reference and only fetch
      // the first result page for the receiving workspace.
      const executionPayload = {
        datasets: [
          {
            id: dataset.id,
            connection_id: connectionId,
            source_type: getSourceType(dataset),
            database: getDatabase(dataset),
            table: getObjectName(dataset),
          },
        ],
        joins: [],
        columns: selectedColumns.map((field) => ({
          field: `${dataset.id}.${field}`,
          alias: `${dataset.id}.${field}`,
        })),
        filters: [],
        sorts: [],
        group_by: [],
        aggregations: [],
        calculated_columns: [],
        // This is the execution window, not the logical result size. The
        // receiver uses execution_job_id + total_rows for server pagination.
        limit: 0,
      };

      const jobId = await submitExecutionJob(executionPayload);
      const firstResult = await waitForExecutionJob(jobId, {
        pageSize: 5000,
        returnOnFirstPage: true,
      });
      const page = firstResult;
      const pageRows = Array.isArray(page?.rows) ? page.rows : [];
      const pageColumns = Array.isArray(page?.columns) && page.columns.length
        ? page.columns
        : selectedColumns;
      const totalRows = Math.max(
        0,
        Number(page?.total_rows ?? 0) || 0,
      );

      const result = {
        success: true,
        source: "execution_job",
        preview_only: false,
        execution_job_id: jobId,
        dataset_id: dataset.id,
        dataset_name: datasetLabel(dataset),
        dataset: {
          id: dataset.id,
          sourceType: getSourceType(dataset),
          source_type: getSourceType(dataset),
          connectionId,
          connection_id: connectionId,
          connectionName: getConnectionName(dataset),
          database: getDatabase(dataset),
          table: getObjectName(dataset),
        },
        columns: pageColumns,
        rows: pageRows,
        total_rows: totalRows,
        returned_rows: pageRows.length,
        source_total_rows: totalRows,
        page_offset: 0,
        page_size: pageRows.length,
        has_more: Boolean(page?.has_more),
        execution_status: firstResult.execution_status || "completed",
        execution_in_progress: Boolean(firstResult.execution_in_progress),
        applied_joins: [],
        applied_columns: selectedColumns.map((field) => ({
          field: `${dataset.id}.${field}`,
          alias: `${dataset.id}.${field}`,
        })),
        applied_filters: [],
        applied_sorts: [],
        applied_group_by: [],
        applied_aggregations: [],
        applied_calculated_columns: [],
        applied_limit: 0,
      };

      if (destination === "dashboard" && typeof onSendToDashboard === "function") {
        onSendToDashboard(result, dataset);
        return;
      }

      if (typeof onSendToReportBuilder === "function") {
        onSendToReportBuilder(result, dataset);
      }
    } catch (error) {
      setErrorMap((current) => ({
        ...current,
        [datasetId]: `Unable to execute dataset: ${error.message}`,
      }));
    } finally {
      setLoadingMap((current) => ({ ...current, [datasetId]: false }));
    }
  };

  const sendSelectedToReportBuilder = () => {
    if (selectedDatasets.length !== 1) {
      return;
    }

    sendDatasetToReportBuilder(
      selectedDatasets[0]
    );
  };

  const setColumnsForDataset = (datasetId, columns) => {
    setSelectedColumnsMap((current) => ({
      ...current,
      [datasetId]: columns,
    }));
  };

  const toggleColumn = (datasetId, columnName) => {
    setSelectedColumnsMap((current) => {
      const existing = current[datasetId] || [];

      return {
        ...current,
        [datasetId]: existing.includes(columnName)
          ? existing.filter((column) => column !== columnName)
          : [...existing, columnName],
      };
    });
  };

  const selectVisibleColumns = (
    datasetId,
    visibleColumns
  ) => {
    setSelectedColumnsMap((current) => {
      const existing = new Set(current[datasetId] || []);

      visibleColumns.forEach((column) =>
        existing.add(column)
      );

      return {
        ...current,
        [datasetId]: Array.from(existing),
      };
    });
  };

  const clearDatasetColumns = (datasetId) => {
    setColumnsForDataset(datasetId, []);
  };

  /*
   * ------------------------------------------------------------
   * PREVIEW IDENTIFICATION FILTER
   * ------------------------------------------------------------
   *
   * Used to quickly identify a particular value in the loaded
   * preview when two similarly named tables/collections contain
   * different values.
   *
   * This never changes the source data, dataset definition or
   * Join Designer configuration.
   */
  const updatePreviewFilter = (datasetId, key, value) => {
    setPreviewFilterMap((current) => ({
      ...current,
      [datasetId]: {
        column: current[datasetId]?.column || "",
        operator: current[datasetId]?.operator || "contains",
        value: current[datasetId]?.value || "",
        [key]: value,
      },
    }));
  };

  const clearPreviewFilter = (datasetId) => {
    setPreviewFilterMap((current) => ({
      ...current,
      [datasetId]: {
        column: "",
        operator: "contains",
        value: "",
      },
    }));
  };

  const selectPreviewFilterColumn = (datasetId, column) => {
    setPreviewFilterMap((current) => ({
      ...current,
      [datasetId]: {
        column,
        operator: current[datasetId]?.operator || "contains",
        value: current[datasetId]?.value || "",
      },
    }));
  };

  const selectAllDatasetColumns = (datasetId) => {
    const preview = previewMap[datasetId];

    setColumnsForDataset(
      datasetId,
      preview?.columns || []
    );
  };

  const previewViewMap = useMemo(() => {
    const next = {};

    selectedDatasets.forEach((dataset) => {
      const datasetId = dataset.id;
      const preview = previewMap[datasetId];
      const filter = previewFilterMap[datasetId];

      next[datasetId] = {
        filteredRows: filterPreviewRows(preview?.rows, filter),
        filterValues: collectPreviewFilterValues(
          preview?.rows,
          filter?.column,
          200
        ),
      };
    });

    return next;
  }, [previewFilterMap, previewMap, selectedDatasets]);

  return (
    <>
      <style>{`
        .dp-page {
          width: 100%;
          max-width: 1540px;
          margin: 0 auto;
          padding: 26px 28px 45px;
          color: #172033;
        }

        .dp-page *,
        .dp-page *::before,
        .dp-page *::after {
          box-sizing: border-box;
        }

        .dp-eyebrow {
          display: block;
          margin-bottom: 5px;
          color: #718096;
          font-size: 9px;
          font-weight: 800;
          letter-spacing: .14em;
          text-transform: uppercase;
        }

        .dp-heading {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 18px;
          margin-bottom: 18px;
        }

        .dp-heading h2 {
          margin: 0;
          color: #172033;
          font-size: 25px;
          font-weight: 780;
          line-height: 1.15;
        }

        .dp-heading p {
          margin: 6px 0 0;
          color: #718096;
          font-size: 11px;
          line-height: 1.5;
        }

        .dp-card {
          overflow: hidden;
          margin-bottom: 16px;
          border: 1px solid #dce4ee;
          border-radius: 14px;
          background: #fff;
          box-shadow: 0 5px 20px rgba(23, 32, 51, .045);
        }

        .dp-card-blue {
          border-top: 3px solid #2563eb;
        }

        .dp-card-purple {
          border-top: 3px solid #7c3aed;
        }

        .dp-status {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 7px 10px;
          border: 1px solid #bbf7d0;
          border-radius: 999px;
          background: #f0fdf4;
          color: #15803d;
          font-size: 9px;
          font-weight: 800;
          white-space: nowrap;
        }

        .dp-status-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #16a34a;
        }

        /* DATASET SELECTOR */

        .dp-selector-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          padding: 17px 20px;
          border-bottom: 1px solid #e8edf4;
        }

        .dp-selector-head h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 750;
        }

        .dp-selector-head p {
          margin: 5px 0 0;
          color: #7a8799;
          font-size: 10px;
        }

        .dp-selector-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-shrink: 0;
        }

        .dp-select-all {
          height: 36px;
          padding: 0 11px;
          border: 1px solid #d1dbe8;
          border-radius: 8px;
          background: #fff;
          color: #52637b;
          font: inherit;
          font-size: 9px;
          font-weight: 750;
          cursor: pointer;
        }

        .dp-select-all:hover {
          background: #f8fafc;
          border-color: #aebbd0;
        }

        .dp-refresh-all {
          display: inline-flex;
          height: 36px;
          align-items: center;
          gap: 7px;
          padding: 0 12px;
          border: 1px solid #2563eb;
          border-radius: 8px;
          background: #2563eb;
          color: #fff;
          font: inherit;
          font-size: 9px;
          font-weight: 750;
          cursor: pointer;
        }

        .dp-refresh-all:hover {
          background: #1d4ed8;
        }

        .dp-dataset-list {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 9px;
          padding: 14px 20px 18px;
        }

        .dp-dataset-option {
          display: flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
          padding: 11px 12px;
          border: 1px solid #dfe6ef;
          border-radius: 9px;
          background: #fff;
          cursor: pointer;
          transition: .15s ease;
        }

        .dp-dataset-option:hover {
          border-color: #b8c7da;
          background: #fbfdff;
        }

        .dp-dataset-option.selected {
          border-color: #93c5fd;
          background: #eff6ff;
        }

        .dp-dataset-option input {
          width: 15px;
          height: 15px;
          flex: 0 0 15px;
          accent-color: #2563eb;
        }

        .dp-dataset-option-info {
          min-width: 0;
          flex: 1;
        }

        .dp-dataset-option-name {
          display: block;
          overflow: hidden;
          color: #334155;
          font-size: 10px;
          font-weight: 750;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .dp-dataset-option-meta {
          display: flex;
          gap: 6px;
          margin-top: 4px;
          color: #8290a3;
          font-size: 8px;
        }

        .dp-dataset-count {
          padding: 3px 7px;
          border-radius: 999px;
          background: #eef2ff;
          color: #4338ca;
          font-size: 8px;
          font-weight: 800;
        }

        /* DATASET PREVIEW */

        .dp-multi-heading {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin: 21px 0 11px;
        }

        .dp-multi-heading h3 {
          margin: 0;
          color: #172033;
          font-size: 15px;
          font-weight: 760;
        }

        .dp-multi-heading span {
          color: #7a8799;
          font-size: 9px;
        }

        .dp-dataset-card {
          overflow: hidden;
          margin-bottom: 16px;
          border: 1px solid #dce4ee;
          border-radius: 14px;
          background: #fff;
          box-shadow: 0 5px 20px rgba(23, 32, 51, .045);
        }

        .dp-dataset-card-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 18px;
          padding: 17px 19px;
          border-top: 3px solid #7c3aed;
          border-bottom: 1px solid #e8edf4;
        }

        .dp-card-identity {
          min-width: 0;
        }

        .dp-breadcrumb {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 5px;
          margin-bottom: 8px;
          color: #7a8799;
          font-size: 9px;
        }

        .dp-breadcrumb strong {
          color: #475569;
        }

        .dp-card-title-line {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .dp-card-title-line h2 {
          min-width: 0;
          margin: 0;
          color: #182238;
          font-size: 19px;
          font-weight: 780;
          line-height: 1.25;
          word-break: break-word;
        }

        .dp-source-pill {
          padding: 5px 8px;
          border: 1px solid #dbe4f0;
          border-radius: 7px;
          background: #f8fafc;
          color: #52637b;
          font-size: 8px;
          font-weight: 800;
          letter-spacing: .05em;
          white-space: nowrap;
        }

        .dp-card-subtitle {
          margin: 5px 0 0;
          color: #718096;
          font-size: 10px;
        }

        .dp-card-head-actions {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 8px;
          flex-wrap: wrap;
          flex-shrink: 0;
        }

        .dp-row-select {
          height: 35px;
          padding: 0 9px;
          border: 1px solid #d3dce8;
          border-radius: 7px;
          background: #fff;
          color: #475569;
          font: inherit;
          font-size: 9px;
          font-weight: 700;
        }

        .dp-send-report,
        .dp-send-dataset {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          border: 1px solid #2563eb;
          border-radius: 7px;
          background: #2563eb;
          color: #fff;
          font: inherit;
          font-size: 9px;
          font-weight: 750;
          cursor: pointer;
          white-space: nowrap;
        }

        .dp-send-report {
          height: 36px;
          padding: 0 12px;
        }

        .dp-send-dataset {
          height: 35px;
          padding: 0 10px;
        }

        .dp-send-report:hover:not(:disabled),
        .dp-send-dataset:hover:not(:disabled) {
          background: #1d4ed8;
          border-color: #1d4ed8;
        }

        .dp-send-report:disabled,
        .dp-send-dataset:disabled {
          opacity: .45;
          cursor: not-allowed;
        }

        .dp-refresh {
          display: inline-flex;
          width: 35px;
          height: 35px;
          align-items: center;
          justify-content: center;
          border: 1px solid #d3dce8;
          border-radius: 7px;
          background: #fff;
          color: #52637b;
          font-size: 15px;
          cursor: pointer;
        }

        .dp-refresh:hover:not(:disabled) {
          border-color: #93c5fd;
          background: #f8fbff;
          color: #2563eb;
        }

        .dp-refresh:disabled {
          cursor: not-allowed;
          opacity: .5;
        }

        .dp-summary {
          display: grid;
          grid-template-columns: repeat(6, minmax(0, 1fr));
          gap: 9px;
          padding: 13px 19px;
          border-bottom: 1px solid #edf1f6;
        }

        .dp-summary-item {
          min-width: 0;
          padding: 9px 10px;
          border: 1px solid #e1e7ef;
          border-radius: 8px;
          background: #fbfcfe;
        }

        .dp-summary-item span {
          display: block;
          margin-bottom: 4px;
          color: #7a8799;
          font-size: 8px;
          font-weight: 750;
          letter-spacing: .03em;
          text-transform: uppercase;
        }

        .dp-summary-item strong {
          display: block;
          overflow: hidden;
          color: #263449;
          font-size: 11px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .dp-hierarchy {
          padding: 11px 19px 14px;
          border-bottom: 1px solid #edf1f6;
        }

        .dp-hierarchy-label {
          margin-bottom: 5px;
          color: #7a8799;
          font-size: 8px;
          font-weight: 800;
          letter-spacing: .06em;
          text-transform: uppercase;
        }

        .dp-hierarchy-value {
          padding: 8px 10px;
          border: 1px solid #e1e7ef;
          border-radius: 7px;
          background: #f8fafc;
          color: #52637b;
          font-size: 9px;
          line-height: 1.5;
          word-break: break-word;
        }

        /* WORKSPACE */

        .dp-workspace {
          display: grid;
          grid-template-columns: 285px minmax(0, 1fr);
          min-width: 0;
        }

        .dp-column-panel {
          min-width: 0;
          border-right: 1px solid #e8edf4;
        }

        .dp-preview-panel {
          min-width: 0;
        }

        .dp-panel-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 10px;
          padding: 14px 15px;
          border-bottom: 1px solid #e8edf4;
        }

        .dp-panel-head h3 {
          margin: 0;
          color: #172033;
          font-size: 13px;
          font-weight: 750;
        }

        .dp-panel-head p {
          margin: 4px 0 0;
          color: #7a8799;
          font-size: 9px;
          line-height: 1.45;
        }

        .dp-column-tools {
          display: flex;
          gap: 6px;
          padding: 10px;
          border-bottom: 1px solid #edf1f6;
        }

        .dp-column-search {
          min-width: 0;
          width: 100%;
          height: 32px;
          padding: 0 8px;
          border: 1px solid #d4dce8;
          border-radius: 7px;
          outline: none;
          font: inherit;
          font-size: 9px;
        }

        .dp-column-search:focus {
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, .07);
        }

        .dp-selection-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
          padding: 8px 10px;
          background: #f8fafc;
          color: #7a8799;
          font-size: 8px;
        }

        .dp-selection-bar strong {
          color: #334155;
        }

        .dp-selection-actions {
          display: flex;
          gap: 5px;
        }

        .dp-selection-actions button {
          padding: 0;
          border: 0;
          background: transparent;
          color: #2563eb;
          font: inherit;
          font-size: 8px;
          font-weight: 750;
          cursor: pointer;
        }

        .dp-column-list {
          max-height: 430px;
          overflow-y: auto;
          padding: 7px;
        }

        .dp-column-row {
          display: flex;
          align-items: center;
          gap: 8px;
          min-height: 39px;
          margin-bottom: 3px;
          padding: 7px 8px;
          border: 1px solid transparent;
          border-radius: 7px;
          cursor: pointer;
        }

        .dp-column-row:hover {
          border-color: #dbe5f0;
          background: #f8fafc;
        }

        .dp-column-row.selected {
          border-color: #bfdbfe;
          background: #eff6ff;
        }

        .dp-column-row input {
          width: 14px;
          height: 14px;
          flex: 0 0 14px;
          accent-color: #2563eb;
          cursor: pointer;
        }

        .dp-column-info {
          min-width: 0;
          flex: 1;
        }

        .dp-column-name {
          display: block;
          overflow: hidden;
          color: #334155;
          font-size: 9px;
          font-weight: 700;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .dp-column-meta {
          display: flex;
          align-items: center;
          gap: 5px;
          margin-top: 3px;
          color: #8794a7;
          font-size: 7px;
        }

        .dp-type {
          padding: 2px 5px;
          border-radius: 4px;
          background: #eef2ff;
          color: #4338ca;
          font-size: 7px;
        }

        .dp-empty-small {
          padding: 25px 10px;
          color: #8995a7;
          font-size: 9px;
          text-align: center;
        }

        /* TABLE */

        .dp-preview-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 14px 15px;
          border-bottom: 1px solid #e8edf4;
        }

        .dp-preview-head h3 {
          margin: 0;
          color: #172033;
          font-size: 13px;
          font-weight: 750;
        }

        .dp-preview-head p {
          margin: 4px 0 0;
          color: #7a8799;
          font-size: 9px;
        }

        .dp-table-wrap {
          width: 100%;
          max-height: 430px;
          overflow: auto;
        }

        .dp-table {
          width: 100%;
          min-width: 650px;
          border-collapse: collapse;
          font-size: 9px;
        }

        .dp-table th,
        .dp-table td {
          padding: 8px 9px;
          border-bottom: 1px solid #edf1f6;
          text-align: left;
          white-space: nowrap;
        }

        .dp-table th {
          position: sticky;
          top: 0;
          z-index: 2;
          background: #f8fafc;
          color: #64748b;
          font-size: 7px;
          font-weight: 800;
          letter-spacing: .05em;
          text-transform: uppercase;
        }

        .dp-table td {
          max-width: 280px;
          overflow: hidden;
          color: #52637b;
          text-overflow: ellipsis;
        }

        .dp-table tbody tr:hover {
          background: #fbfdff;
        }

        .dp-preview-filter {
          padding: 12px 15px;
          border-bottom: 1px solid #e8edf4;
          background: #fbfcfe;
        }

        .dp-preview-filter-title {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 9px;
        }

        .dp-preview-filter-title .dp-eyebrow {
          margin-bottom: 3px;
        }

        .dp-preview-filter-title strong {
          display: block;
          color: #334155;
          font-size: 10px;
          font-weight: 750;
        }

        .dp-filter-result {
          color: #64748b;
          font-size: 8px;
          white-space: nowrap;
        }

        .dp-preview-filter-controls {
          display: grid;
          grid-template-columns:
            minmax(145px, 1fr)
            125px
            minmax(180px, 1.4fr)
            auto;
          gap: 7px;
          align-items: center;
        }

        .dp-filter-select,
        .dp-filter-operator,
        .dp-filter-value {
          width: 100%;
          height: 33px;
          min-width: 0;
          padding: 0 9px;
          border: 1px solid #d4dce8;
          border-radius: 7px;
          outline: none;
          background: #fff;
          color: #334155;
          font: inherit;
          font-size: 9px;
        }

        .dp-filter-select:focus,
        .dp-filter-operator:focus,
        .dp-filter-value:focus {
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, .07);
        }

        .dp-filter-select:disabled,
        .dp-filter-operator:disabled,
        .dp-filter-value:disabled {
          background: #f1f5f9;
          color: #94a3b8;
          cursor: not-allowed;
        }

        .dp-filter-clear {
          height: 33px;
          padding: 0 11px;
          border: 1px solid #cbd5e1;
          border-radius: 7px;
          background: #fff;
          color: #64748b;
          font: inherit;
          font-size: 9px;
          font-weight: 750;
          cursor: pointer;
        }

        .dp-filter-clear:hover:not(:disabled) {
          border-color: #94a3b8;
          background: #f8fafc;
        }

        .dp-filter-clear:disabled {
          opacity: .45;
          cursor: not-allowed;
        }

        .dp-preview-filter-help {
          margin: 7px 0 0;
          color: #94a3b8;
          font-size: 8px;
          line-height: 1.4;
        }

        .dp-preview-footer {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          padding: 8px 12px;
          border-top: 1px solid #edf1f6;
          background: #fbfcfe;
          color: #8794a7;
          font-size: 8px;
        }

        .dp-preview-footer strong {
          color: #52637b;
        }

        .dp-loading {
          display: grid;
          min-height: 270px;
          place-items: center;
          padding: 30px;
          color: #718096;
          font-size: 10px;
        }

        .dp-error {
          margin: 12px;
          padding: 10px 11px;
          border: 1px solid #fecaca;
          border-radius: 7px;
          background: #fef2f2;
          color: #b91c1c;
          font-size: 9px;
          line-height: 1.45;
        }

        .dp-empty {
          display: grid;
          min-height: 290px;
          place-items: center;
          padding: 35px;
          text-align: center;
        }

        .dp-empty-icon {
          display: grid;
          width: 52px;
          height: 52px;
          margin: 0 auto 11px;
          place-items: center;
          border-radius: 13px;
          background: #eff6ff;
          color: #2563eb;
          font-size: 21px;
        }

        .dp-empty h3 {
          margin: 0;
          color: #172033;
          font-size: 16px;
        }

        .dp-empty p {
          max-width: 470px;
          margin: 6px auto 14px;
          color: #7a8799;
          font-size: 10px;
          line-height: 1.5;
        }

        .dp-primary {
          height: 35px;
          padding: 0 13px;
          border: 1px solid #2563eb;
          border-radius: 8px;
          background: #2563eb;
          color: #fff;
          font: inherit;
          font-size: 9px;
          font-weight: 750;
          cursor: pointer;
        }

        .dp-message {
          margin-bottom: 15px;
          padding: 10px 12px;
          border: 1px solid #fecaca;
          border-radius: 8px;
          background: #fef2f2;
          color: #b91c1c;
          font-size: 9px;
        }

        @media (max-width: 1100px) {
          .dp-dataset-list {
            grid-template-columns: 1fr;
          }

          .dp-summary {
            grid-template-columns: repeat(3, 1fr);
          }
        }

        @media (max-width: 800px) {
          .dp-page {
            padding: 18px 12px 30px;
          }

          .dp-heading,
          .dp-selector-head,
          .dp-dataset-card-head,
          .dp-preview-head {
            align-items: flex-start;
            flex-direction: column;
          }

          .dp-selector-actions,
          .dp-card-head-actions {
            width: 100%;
            justify-content: flex-start;
          }

          .dp-send-report {
            flex: 1;
          }

          .dp-refresh-all {
            flex: 1;
            justify-content: center;
          }

          .dp-summary {
            grid-template-columns: repeat(2, 1fr);
          }

          .dp-workspace {
            grid-template-columns: 1fr;
          }

          .dp-column-panel {
            border-right: 0;
            border-bottom: 1px solid #e8edf4;
          }

          .dp-column-list {
            max-height: 300px;
          }
        }
      `}</style>

      <div className="dp-page">
        <div className="dp-heading">
          <div>
            <span className="dp-eyebrow">DATA INSPECTION</span>
            <h2>Data Preview</h2>
            <p>
              Preview multiple reporting datasets at the same time,
              inspect their columns and understand the source data
              before moving to Join Designer.
            </p>
          </div>

          {selectedDatasets.length > 0 && (
            <div className="dp-status">
              <span className="dp-status-dot" />
              {selectedDatasets.length} dataset
              {selectedDatasets.length === 1 ? "" : "s"} selected
            </div>
          )}
        </div>

        {/* =====================================================
            ROW 1 — MULTI DATASET SELECTOR
            ===================================================== */}
        <section className="dp-card dp-card-blue">
          <div className="dp-selector-head">
            <div>
              <span className="dp-eyebrow">
                ROW 1 · DATASET SELECTION
              </span>
              <h3>Select Data Sets</h3>
              <p>
                Select one or multiple datasets. All selected
                datasets remain visible together below.
              </p>
            </div>

            <div className="dp-selector-actions">
              <button
                className="dp-select-all"
                onClick={selectAllDatasets}
                disabled={!datasets.length}
              >
                Select All
              </button>

              <button
                className="dp-select-all"
                onClick={clearDatasets}
                disabled={!selectedIds.length}
              >
                Clear
              </button>

              <button
                className="dp-refresh-all"
                onClick={refreshAll}
                disabled={
                  !selectedDatasets.length ||
                  Object.values(loadingMap).some(Boolean)
                }
              >
                ↻ Refresh All
              </button>

              <button
                className="dp-send-report"
                onClick={sendSelectedToReportBuilder}
                disabled={
                  selectedDatasets.length !== 1 ||
                  !previewMap[selectedDatasets[0]?.id]?.rows?.length
                }
                title={
                  selectedDatasets.length !== 1
                    ? "Select exactly one dataset for quick Report Builder handoff."
                    : "Send the selected dataset preview to Report Builder."
                }
              >
                ⇥ Report Builder
              </button>
            </div>
          </div>

          {!datasets.length ? (
            <div className="dp-empty">
              <div>
                <div className="dp-empty-icon">◫</div>
                <h3>No reporting datasets</h3>
                <p>
                  Add MySQL tables or MongoDB collections from
                  Data Sources first.
                </p>

                <button
                  className="dp-primary"
                  onClick={onBack}
                >
                  Open Data Sources
                </button>
              </div>
            </div>
          ) : (
            <div className="dp-dataset-list">
              {datasets.map((dataset) => {
                const selected = selectedIds.includes(
                  dataset.id
                );

                return (
                  <label
                    className={
                      selected
                        ? "dp-dataset-option selected"
                        : "dp-dataset-option"
                    }
                    key={dataset.id}
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() =>
                        toggleDataset(dataset.id)
                      }
                    />

                    <div className="dp-dataset-option-info">
                      <span
                        className="dp-dataset-option-name"
                        title={datasetLabel(dataset)}
                      >
                        {datasetLabel(dataset)}
                      </span>

                      <span className="dp-dataset-option-meta">
                        <span>
                          {sourceLabel(
                            getSourceType(dataset)
                          )}
                        </span>

                        {getConnectionId(dataset) && (
                          <span>Saved connection</span>
                        )}
                      </span>
                    </div>

                    {previewMap[dataset.id] && (
                      <span className="dp-dataset-count">
                        {formatNumber(
                          previewMap[dataset.id]
                            ?.total_rows || 0
                        )}{" "}
                        rows
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          )}
        </section>

        {/* =====================================================
            SELECTED DATASET PREVIEWS
            ===================================================== */}
        {selectedDatasets.length > 0 && (
          <div className="dp-multi-heading">
            <h3>Selected Dataset Previews</h3>
            <span>
              {selectedDatasets.length} dataset
              {selectedDatasets.length === 1 ? "" : "s"} loaded
              independently
            </span>
          </div>
        )}

        {selectedDatasets.map((dataset) => {
          const datasetId = dataset.id;
          const preview = previewMap[datasetId];
          const loading = Boolean(loadingMap[datasetId]);
          const error = errorMap[datasetId];
          const search =
            columnSearchMap[datasetId] || "";

          const allColumns = preview?.columns || [];
          const selectedColumns =
            selectedColumnsMap[datasetId] || [];

          const filteredProfiles = (
            preview?.column_profiles || []
          ).filter((column) =>
            String(column.name)
              .toLowerCase()
              .includes(search.toLowerCase())
          );

          const selectedSet = new Set(selectedColumns);

          const visibleColumns = allColumns.filter(
            (column) => selectedSet.has(column)
          );

          const filteredPreviewRows =
            previewViewMap[datasetId]?.filteredRows ||
            preview?.rows || [];

          const previewFilter =
            previewFilterMap[datasetId] || {
              column: "",
              operator: "contains",
              value: "",
            };

          const filterValues =
            previewViewMap[datasetId]?.filterValues || [];

          return (
            <section
              className="dp-dataset-card"
              key={datasetId}
            >
              {/* DATASET HEADER */}
              <div className="dp-dataset-card-head">
                <div className="dp-card-identity">
                  <div className="dp-breadcrumb">
                    <span>
                      {getConnectionName(dataset) ||
                        "Saved Connection"}
                    </span>
                    <span>›</span>
                    <span>{getDatabase(dataset)}</span>
                    <span>›</span>
                    <strong>
                      {getObjectName(dataset)}
                    </strong>
                  </div>

                  <div className="dp-card-title-line">
                    <h2>
                      {getObjectName(dataset)}
                    </h2>

                    <span className="dp-source-pill">
                      {sourceLabel(
                        getSourceType(dataset)
                      )}
                    </span>
                  </div>

                  <p className="dp-card-subtitle">
                    {sourceLabel(
                      getSourceType(dataset)
                    )}{" "}
                    · {getDatabase(dataset)} ·{" "}
                    {getConnectionName(dataset) ||
                      "Saved connection"}
                  </p>
                </div>

                <div className="dp-card-head-actions">
                  <select
                    className="dp-row-select"
                    value={sampleLimit}
                    onChange={(event) =>
                      setSampleLimit(
                        Number(event.target.value)
                      )
                    }
                    disabled={loading}
                  >
                    {PREVIEW_ROW_OPTIONS.map((option) => (
                      <option key={option} value={option}>{worksheetRowLabel(option)}</option>
                    ))}
                  </select>

                  <button
                    className="dp-send-dataset"
                    title="Send this preview to Report Builder"
                    onClick={() =>
                      sendDatasetToReportBuilder(dataset)
                    }
                    disabled={
                      loading ||
                      !preview?.rows?.length
                    }
                  >
                    ⇥ Report
                  </button>

                  <button
                    className="dp-send-dataset"
                    title="Open this preview in Dashboard View"
                    onClick={() =>
                      sendDatasetToReportBuilder(dataset, "dashboard")
                    }
                    disabled={
                      loading ||
                      !preview?.rows?.length
                    }
                  >
                    ▦ Dashboard
                  </button>

                  <button
                    className="dp-refresh"
                    title="Refresh this dataset"
                    onClick={() =>
                      refreshDataset(dataset)
                    }
                    disabled={loading}
                  >
                    ↻
                  </button>
                </div>
              </div>

              {/* BASIC DETAILS */}
              <div className="dp-summary">
                <div className="dp-summary-item">
                  <span>Object Type</span>
                  <strong>
                    {getSourceType(dataset) ===
                      "mongodb" ||
                    getSourceType(dataset) === "mongo"
                      ? "Collection"
                      : "Table"}
                  </strong>
                </div>

                <div className="dp-summary-item">
                  <span>Total Rows</span>
                  <strong>
                    {formatNumber(
                      preview?.total_rows ??
                        dataset.total_rows ??
                        dataset.row_count ??
                        0
                    )}
                  </strong>
                </div>

                <div className="dp-summary-item">
                  <span>Total Columns</span>
                  <strong>
                    {formatNumber(
                      preview?.column_count ??
                        allColumns.length
                    )}
                  </strong>
                </div>

                <div className="dp-summary-item">
                  <span>Preview Rows</span>
                  <strong>
                    {formatNumber(
                      preview?.sample_rows ??
                        preview?.rows?.length ??
                        0
                    )}
                  </strong>
                </div>

                <div className="dp-summary-item">
                  <span>Selected Fields</span>
                  <strong>
                    {selectedColumns.length}
                  </strong>
                </div>

                <div className="dp-summary-item">
                  <span>Last Refresh</span>
                  <strong>
                    {lastRefreshMap[datasetId]
                      ? lastRefreshMap[
                          datasetId
                        ].toLocaleTimeString()
                      : "—"}
                  </strong>
                </div>
              </div>

              <div className="dp-hierarchy">
                <div className="dp-hierarchy-label">
                  Hierarchy Details
                </div>

                <div className="dp-hierarchy-value">
                  {getHierarchy(dataset)}
                </div>
              </div>

              {error && (
                <div className="dp-error">
                  <strong>Preview error:</strong>{" "}
                  {error}
                </div>
              )}

              {/* =================================================
                  DATASET-SPECIFIC COLUMN + PREVIEW WORKSPACE
                  ================================================= */}
              <div className="dp-workspace">
                {/* LEFT — COLUMN DETAILS */}
                <section className="dp-column-panel">
                  <div className="dp-panel-head">
                    <div>
                      <span className="dp-eyebrow">
                        TABLE DETAILS
                      </span>
                      <h3>Columns</h3>
                      <p>
                        Select exactly which columns should
                        appear in this dataset preview.
                      </p>
                    </div>
                  </div>

                  <div className="dp-column-tools">
                    <input
                      className="dp-column-search"
                      placeholder="Search columns..."
                      value={search}
                      onChange={(event) =>
                        setColumnSearchMap(
                          (current) => ({
                            ...current,
                            [datasetId]:
                              event.target.value,
                          })
                        )
                      }
                    />
                  </div>

                  <div className="dp-selection-bar">
                    <span>
                      <strong>
                        {selectedColumns.length}
                      </strong>{" "}
                      of{" "}
                      <strong>
                        {allColumns.length}
                      </strong>{" "}
                      selected
                    </span>

                    <div className="dp-selection-actions">
                      <button
                        onClick={() =>
                          selectVisibleColumns(
                            datasetId,
                            filteredProfiles.map(
                              (column) =>
                                column.name
                            )
                          )
                        }
                      >
                        Visible
                      </button>

                      <button
                        onClick={() =>
                          selectAllDatasetColumns(
                            datasetId
                          )
                        }
                      >
                        All
                      </button>

                      <button
                        onClick={() =>
                          clearDatasetColumns(
                            datasetId
                          )
                        }
                      >
                        Clear
                      </button>
                    </div>
                  </div>

                  <div className="dp-column-list">
                    {!preview ? (
                      <div className="dp-empty-small">
                        {loading
                          ? "Loading columns..."
                          : "Preview has not loaded yet."}
                      </div>
                    ) : !filteredProfiles.length ? (
                      <div className="dp-empty-small">
                        No matching columns found.
                      </div>
                    ) : (
                      filteredProfiles.map(
                        (column) => {
                          const checked =
                            selectedColumns.includes(
                              column.name
                            );

                          return (
                            <label
                              key={column.name}
                              className={
                                checked
                                  ? "dp-column-row selected"
                                  : "dp-column-row"
                              }
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() =>
                                  toggleColumn(
                                    datasetId,
                                    column.name
                                  )
                                }
                              />

                              <div className="dp-column-info">
                                <span
                                  className="dp-column-name"
                                  title={column.name}
                                >
                                  {column.name}
                                </span>

                                <span className="dp-column-meta">
                                  <span className="dp-type">
                                    {column.data_type ||
                                      "unknown"}
                                  </span>

                                  <span>
                                    {formatNumber(
                                      column.distinct_count ||
                                        0
                                    )}{" "}
                                    distinct
                                  </span>

                                  <span>
                                    {formatNumber(
                                      column.null_count ||
                                        0
                                    )}{" "}
                                    null
                                  </span>
                                </span>
                              </div>
                            </label>
                          );
                        }
                      )
                    )}
                  </div>
                </section>

                {/* RIGHT — ACTUAL PREVIEW */}
                <section className="dp-preview-panel">
                  <div className="dp-preview-head">
                    <div>
                      <span className="dp-eyebrow">
                        ACTUAL DATA
                      </span>
                      <h3>Table Preview</h3>
                      <p>
                        Actual records returned from the
                        selected saved database connection.
                      </p>
                    </div>
                  </div>

                  {preview && (
                    <div className="dp-preview-filter">
                      <div className="dp-preview-filter-title">
                        <div>
                          <span className="dp-eyebrow">
                            FIND IN PREVIEW
                          </span>
                          <strong>
                            Filter rows by value
                          </strong>
                        </div>

                        <span className="dp-filter-result">
                          {formatNumber(
                            filteredPreviewRows.length
                          )}{" "}
                          of{" "}
                          {formatNumber(
                            preview.rows?.length || 0
                          )}{" "}
                          preview rows
                        </span>
                      </div>

                      <div className="dp-preview-filter-controls">
                        <select
                          className="dp-filter-select"
                          value={previewFilter.column}
                          onChange={(event) =>
                            selectPreviewFilterColumn(
                              datasetId,
                              event.target.value
                            )
                          }
                        >
                          <option value="">
                            Select column
                          </option>

                          {allColumns.map((column) => (
                            <option
                              key={column}
                              value={column}
                            >
                              {column}
                            </option>
                          ))}
                        </select>

                        <select
                          className="dp-filter-operator"
                          value={previewFilter.operator}
                          onChange={(event) =>
                            updatePreviewFilter(
                              datasetId,
                              "operator",
                              event.target.value
                            )
                          }
                          disabled={!previewFilter.column}
                        >
                          <option value="contains">
                            Contains
                          </option>
                          <option value="equals">
                            Equals
                          </option>
                          <option value="not_equals">
                            Not equals
                          </option>
                          <option value="starts_with">
                            Starts with
                          </option>
                          <option value="ends_with">
                            Ends with
                          </option>
                        </select>

                        <input
                          className="dp-filter-value"
                          list={`preview-values-${datasetId}`}
                          value={previewFilter.value}
                          disabled={!previewFilter.column}
                          placeholder={
                            previewFilter.column
                              ? "Type or select a value..."
                              : "Select a column first"
                          }
                          onChange={(event) =>
                            updatePreviewFilter(
                              datasetId,
                              "value",
                              event.target.value
                            )
                          }
                        />

                        <datalist
                          id={`preview-values-${datasetId}`}
                        >
                          {filterValues
                            .slice(0, 200)
                            .map((value) => (
                              <option
                                key={value}
                                value={value}
                              />
                            ))}
                        </datalist>

                        <button
                          type="button"
                          className="dp-filter-clear"
                          onClick={() =>
                            clearPreviewFilter(
                              datasetId
                            )
                          }
                          disabled={
                            !previewFilter.column &&
                            !previewFilter.value
                          }
                        >
                          Clear
                        </button>
                      </div>

                      <p className="dp-preview-filter-help">
                        Search the loaded preview to identify a
                        particular value. This does not modify the
                        source data or reporting dataset.
                      </p>
                    </div>
                  )}

                  {loading && !preview ? (
                    <div className="dp-loading">
                      Loading actual data from{" "}
                      <strong>
                        {getObjectName(dataset)}
                      </strong>
                      ...
                    </div>
                  ) : !preview ? (
                    <div className="dp-empty">
                      <div>
                        <div className="dp-empty-icon">
                          ▦
                        </div>

                        <h3>Preview Not Loaded</h3>

                        <p>
                          Select this dataset and load the
                          actual records.
                        </p>

                        <button
                          className="dp-primary"
                          onClick={() =>
                            refreshDataset(dataset)
                          }
                        >
                          Load Preview
                        </button>
                      </div>
                    </div>
                  ) : !visibleColumns.length ? (
                    <div className="dp-empty">
                      <div>
                        <div className="dp-empty-icon">
                          ☷
                        </div>

                        <h3>No Columns Selected</h3>

                        <p>
                          Select one or more columns from
                          the left panel to display the
                          actual records.
                        </p>

                        <button
                          className="dp-primary"
                          onClick={() =>
                            selectAllDatasetColumns(
                              datasetId
                            )
                          }
                        >
                          Select All Columns
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <PagedVirtualizedTable className="dp-table-wrap" tableClassName="dp-table" rows={filteredPreviewRows} columns={visibleColumns} pageSize={500} viewportHeight={420} rowHeight={34} renderHeader={(column) => column} renderCell={(row, column) => { const value = formatCell(row?.[column]); return <span title={value}>{value}</span>; }} />

                      <div className="dp-preview-footer">
                        <span>
                          Showing{" "}
                          <strong>
                            {formatNumber(
                              filteredPreviewRows.length
                            )}
                          </strong>{" "}
                          matching preview rows
                        </span>

                        <span>
                          <strong>
                            {formatNumber(
                              visibleColumns.length
                            )}
                          </strong>{" "}
                          columns displayed
                        </span>
                      </div>
                    </>
                  )}
                </section>
              </div>
            </section>
          );
        })}

        {!selectedDatasets.length &&
          datasets.length > 0 && (
            <section className="dp-card">
              <div className="dp-empty">
                <div>
                  <div className="dp-empty-icon">▦</div>
                  <h3>Select datasets to preview</h3>
                  <p>
                    Select one or more datasets from the panel
                    above. Each selected dataset will be loaded
                    independently and remain visible at the same
                    time.
                  </p>

                  <button
                    className="dp-primary"
                    onClick={selectAllDatasets}
                  >
                    Select All Datasets
                  </button>
                </div>
              </div>
            </section>
          )}
      </div>
    </>
  );
}
