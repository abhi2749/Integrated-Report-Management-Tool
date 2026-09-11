export function normalizePagedTableState(totalRows, pageIndex = 0, pageSize = 500) {
  const total = Math.max(0, Number(totalRows) || 0);
  const size = Math.max(1, Number(pageSize) || 500);
  const pageCount = Math.max(1, Math.ceil(total / size));
  const index = Math.min(pageCount - 1, Math.max(0, Number(pageIndex) || 0));
  const offset = index * size;
  return {
    totalRows: total,
    pageSize: size,
    pageCount,
    pageIndex: index,
    offset,
    endOffset: Math.min(total, offset + size),
  };
}

export function getPagedRows(rows, pageIndex = 0, pageSize = 500) {
  const safeRows = Array.isArray(rows) ? rows : [];
  const state = normalizePagedTableState(safeRows.length, pageIndex, pageSize);
  return { ...state, rows: safeRows.slice(state.offset, state.endOffset) };
}
