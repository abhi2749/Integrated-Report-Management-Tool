export const EXCEL_MAX_ROWS = 1048576;
export const EXCEL_MAX_COLUMNS = 16384;
export const DEFAULT_QUERY_ROWS = 0;
export const PREVIEW_PAGE_SIZE = 500;

// Preview is a browser window, not an application dataset ceiling.
// The backend accepts larger requested samples; the interactive UI keeps
// default choices bounded so it does not materialize an entire large dataset.
export const PREVIEW_ROW_OPTIONS = [25, 100, 500, 1000, 5000];

export function worksheetRowLabel(value) {
  return Number(value) >= EXCEL_MAX_ROWS
    ? "1,048,576 rows (Excel format maximum)"
    : `${Number(value).toLocaleString()} rows`;
}

export function worksheetColumnLabel(value) {
  return Number(value) >= EXCEL_MAX_COLUMNS
    ? "16,384 columns (Excel format maximum)"
    : `${Number(value).toLocaleString()} columns`;
}
