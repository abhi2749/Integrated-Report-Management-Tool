export function getVirtualRowRange(totalRows, scrollTop, viewportHeight, rowHeight = 36, overscan = 8) {
  const total = Math.max(0, Number(totalRows) || 0);
  const height = Math.max(1, Number(viewportHeight) || 1);
  const size = Math.max(1, Number(rowHeight) || 1);
  const extra = Math.max(0, Number(overscan) || 0);
  const visibleCount = Math.ceil(height / size) + extra * 2;
  const maxStart = Math.max(0, total - visibleCount);
  const start = Math.min(maxStart, Math.max(0, Math.floor(Math.max(0, Number(scrollTop) || 0) / size) - extra));
  return { start, end: Math.min(total, start + visibleCount), rowHeight: size };
}
