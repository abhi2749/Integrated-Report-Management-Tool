import { useMemo, useState } from "react";
import { getPagedRows } from "./pagedTable";
import { VirtualizedTable } from "./VirtualizedTable.jsx";

export function PagedVirtualizedTable({
  rows,
  columns,
  pageSize = 500,
  onPageChange,
  loading = false,
  ...tableProps
}) {
  const [pageIndex, setPageIndex] = useState(0);
  const safeRows = useMemo(() => (Array.isArray(rows) ? rows : []), [rows]);
  const page = useMemo(
    () => getPagedRows(safeRows, pageIndex, pageSize),
    [safeRows, pageIndex, pageSize]
  );

  const changePage = (nextIndex) => {
    const next = Math.min(page.pageCount - 1, Math.max(0, Number(nextIndex) || 0));
    if (next === page.pageIndex) return;
    setPageIndex(next);
    onPageChange?.(next, { offset: next * page.pageSize, pageSize: page.pageSize });
  };

  const status = page.totalRows
    ? `Showing ${(page.offset + 1).toLocaleString()}–${page.endOffset.toLocaleString()} of ${page.totalRows.toLocaleString()}`
    : "No rows";

  return (
    <div className="paged-virtualized-table">
      <VirtualizedTable {...tableProps} rows={page.rows} columns={columns} />
      <div className="paged-virtualized-table__footer" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "7px 8px", fontSize: 10 }}>
        <span>{loading ? "Loading page…" : status}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button type="button" onClick={() => changePage(page.pageIndex - 1)} disabled={loading || page.pageIndex === 0}>Previous</button>
          <span>Page {page.pageIndex + 1} of {page.pageCount}</span>
          <button type="button" onClick={() => changePage(page.pageIndex + 1)} disabled={loading || page.pageIndex >= page.pageCount - 1}>Next</button>
        </div>
      </div>
    </div>
  );
}
