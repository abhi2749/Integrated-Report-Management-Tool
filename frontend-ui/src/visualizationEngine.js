const TYPES = ["kpi", "table", "bar", "line", "pie"];

export const VISUALIZATION_TYPES = Object.freeze({
  KPI: "kpi",
  TABLE: "table",
  BAR: "bar",
  LINE: "line",
  PIE: "pie",
});

export function rowsFromResult(result) {
  return Array.isArray(result?.rows) ? result.rows : [];
}

export function columnsFromResult(result) {
  if (Array.isArray(result?.columns)) {
    return result.columns
      .map((column) => typeof column === "string" ? column : column?.name || column?.field || column?.alias)
      .filter(Boolean);
  }
  const rows = rowsFromResult(result);
  return rows.length ? Object.keys(rows[0]) : [];
}

export function numeric(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function isVisualizationType(type) {
  return TYPES.includes(type);
}

export function visualizationLabel(type) {
  const labels = {
    kpi: "KPI",
    table: "Table",
    bar: "Bar Chart",
    line: "Line Chart",
    pie: "Pie Chart",
  };
  return labels[type] || "Visualization";
}

export function createVisualization(type, columns = []) {
  const safeType = isVisualizationType(type) ? type : VISUALIZATION_TYPES.TABLE;
  const x = columns[0] || "";
  const y = columns.find((column) => column !== x) || columns[0] || "";
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    type: safeType,
    title: safeType === "table" ? "Data Table" : safeType === "kpi" ? "Key Metric" : visualizationLabel(safeType),
    x,
    y,
    span: safeType === "table" ? 12 : 6,
    height: 1,
  };
}

export function normalizeVisualization(widget, index = 0) {
  const type = isVisualizationType(widget?.type) ? widget.type : VISUALIZATION_TYPES.TABLE;
  const span = [12, 6, 4, 3].includes(Number(widget?.span)) ? Number(widget.span) : type === "table" ? 12 : 6;
  const height = Math.max(1, Math.min(3, Number(widget?.height) || 1));
  return {
    ...widget,
    id: String(widget?.id || `${Date.now()}-${index}`),
    type,
    title: String(widget?.title || visualizationLabel(type)),
    span,
    height,
    x: String(widget?.x || ""),
    y: String(widget?.y || ""),
  };
}

export function normalizeVisualizationCollection(value) {
  return Array.isArray(value) ? value.map(normalizeVisualization) : [];
}

export function buildChartPoints(rows, x, y, limit = 30) {
  return rows.slice(0, limit)
    .map((row) => ({ label: String(row?.[x] ?? ""), value: numeric(row?.[y]) }))
    .filter((point) => point.value !== null);
}
