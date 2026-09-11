import { useEffect, useRef, useState } from "react";
import { getVirtualRowRange } from "./virtualizedTable";

export function VirtualizedTable({
  rows,
  columns,
  rowKey,
  renderCell,
  renderHeader,
  columnKey,
  className = "",
  tableClassName = "",
  viewportHeight = 360,
  rowHeight = 36,
  overscan = 8,
  headerClassName = "",
  empty,
}) {
  const viewportRef = useRef(null);
  const scrollFrameRef = useRef(null);
  const [scrollState, setScrollState] = useState({ signature: null, top: 0 });
  const safeRows = Array.isArray(rows) ? rows : [];
  const safeColumns = Array.isArray(columns) ? columns : [];
  const dataSignature = `${safeRows.length}:${safeColumns.length}`;
  const effectiveScrollTop = scrollState.signature === dataSignature ? scrollState.top : 0;
  const range = getVirtualRowRange(safeRows.length, effectiveScrollTop, viewportHeight, rowHeight, overscan);
  const visibleRows = safeRows.slice(range.start, range.end);

  useEffect(() => {
    if (viewportRef.current) viewportRef.current.scrollTop = 0;
  }, [dataSignature]);

  useEffect(() => () => {
    if (scrollFrameRef.current != null) {
      cancelAnimationFrame(scrollFrameRef.current);
      scrollFrameRef.current = null;
    }
  }, []);

  const handleScroll = (event) => {
    const nextScrollTop = event.currentTarget.scrollTop;
    if (scrollFrameRef.current != null) return;
    scrollFrameRef.current = requestAnimationFrame(() => {
      scrollFrameRef.current = null;
      setScrollState((current) => (current.signature === dataSignature && current.top === nextScrollTop)
        ? current
        : { signature: dataSignature, top: nextScrollTop });
    });
  };

  if (!safeRows.length && empty) return empty;

  return (
    <div
      ref={viewportRef}
      className={className}
      style={{ maxHeight: viewportHeight, overflow: "auto" }}
      onScroll={handleScroll}
    >
      <table className={tableClassName}>
        <thead className={headerClassName}>
          <tr>{safeColumns.map((column, index) => <th key={columnKey ? columnKey(column, index) : String(column)}>{renderHeader ? renderHeader(column, index) : String(column)}</th>)}</tr>
        </thead>
        <tbody>
          {range.start > 0 && <tr aria-hidden="true" style={{ height: range.start * range.rowHeight }}><td colSpan={Math.max(safeColumns.length, 1)} /></tr>}
          {visibleRows.map((row, index) => {
            const rowIndex = range.start + index;
            return (
              <tr key={rowKey ? rowKey(row, rowIndex) : rowIndex} style={{ height: range.rowHeight }}>
                {safeColumns.map((column, index) => <td key={columnKey ? columnKey(column, index) : String(column)}>{renderCell ? renderCell(row, column, rowIndex) : String(row?.[column] ?? "")}</td>)}
              </tr>
            );
          })}
          {range.end < safeRows.length && <tr aria-hidden="true" style={{ height: (safeRows.length - range.end) * range.rowHeight }}><td colSpan={Math.max(safeColumns.length, 1)} /></tr>}
        </tbody>
      </table>
    </div>
  );
}
