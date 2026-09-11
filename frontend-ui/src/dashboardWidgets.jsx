import { VISUALIZATION_TYPES, buildChartPoints, numeric } from "./visualizationEngine";

import { PagedVirtualizedTable } from "./PagedVirtualizedTable.jsx";

export function TableWidget({ rows, columns }) {
  return <PagedVirtualizedTable className="db-table-wrap" tableClassName="db-table" rows={rows} columns={columns} pageSize={500} viewportHeight={330} rowHeight={31} overscan={12} renderHeader={(column) => column} renderCell={(row, column) => String(row?.[column] ?? "")} />;
}

export function KpiWidget({ rows, column }) {
  const values = rows.map((row) => numeric(row?.[column])).filter((value) => value !== null);
  const total = values.reduce((sum, value) => sum + value, 0);
  return <div className="db-kpi"><div><strong>{values.length ? total.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}</strong><span>{column || "Select a numeric field"}</span></div></div>;
}

export function ChartWidget({ rows, type, x, y }) {
  const points = buildChartPoints(rows, x, y);
  if (!points.length) return <div className="db-empty" style={{ padding: "35px 10px" }}>Select a numeric measure with usable values.</div>;
  const max = Math.max(...points.map((point) => point.value), 1);
  const min = Math.min(...points.map((point) => point.value), 0);
  const range = max - min || 1;
  if (type === VISUALIZATION_TYPES.PIE) {
    const total = points.reduce((sum, point) => sum + Math.max(point.value, 0), 0) || 1;
    const stops = points.reduce((parts, point, index) => {
      const value = Math.max(point.value, 0);
      const start = parts.used;
      const end = start + value;
      return { used: end, items: [...parts.items, `${index % 2 === 0 ? "#175cd3" : "#98a2b3"} ${start / total * 100}% ${end / total * 100}%`] };
    }, { used: 0, items: [] }).items.join(",");
    return <div className="db-chart"><div style={{ width: 150, height: 150, borderRadius: "50%", margin: "15px auto", background: `conic-gradient(${stops})`, border: "1px solid #e4e7ec" }} /></div>;
  }
  const width = 700; const height = 190; const pad = 25; const innerWidth = width - pad * 2; const innerHeight = height - pad * 2;
  if (type === VISUALIZATION_TYPES.LINE) {
    const path = points.map((point, index) => `${pad + (index / Math.max(points.length - 1, 1)) * innerWidth},${pad + innerHeight - ((point.value - min) / range) * innerHeight}`).join(" ");
    return <div className="db-chart"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${y} by ${x}`}><polyline points={path} fill="none" stroke="#175cd3" strokeWidth="3" />{points.map((point, index) => <circle key={index} cx={pad + (index / Math.max(points.length - 1, 1)) * innerWidth} cy={pad + innerHeight - ((point.value - min) / range) * innerHeight} r="3" fill="#175cd3" />)}</svg></div>;
  }
  return <div className="db-chart"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${y} by ${x}`}>{points.map((point, index) => { const barWidth = Math.max(4, innerWidth / points.length * 0.65); const x0 = pad + index * (innerWidth / points.length) + (innerWidth / points.length - barWidth) / 2; const barHeight = ((point.value - min) / range) * innerHeight; return <rect key={index} x={x0} y={pad + innerHeight - barHeight} width={barWidth} height={barHeight} rx="2" fill="#175cd3" />; })}</svg></div>;
}

export function VisualizationRenderer({ widget, rows, columns }) {
  if (widget.type === VISUALIZATION_TYPES.TABLE) return <TableWidget rows={rows} columns={columns} />;
  if (widget.type === VISUALIZATION_TYPES.KPI) return <KpiWidget rows={rows} column={widget.y} />;
  return <ChartWidget rows={rows} type={widget.type} x={widget.x} y={widget.y} />;
}
