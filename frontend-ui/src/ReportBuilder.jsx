import { API, apiFetch } from "./authClient";
import { fetchExecutionJobResultPage, runExecutionExportJob, transformExecutionJob } from "./executionClient";
import { PagedVirtualizedTable } from "./PagedVirtualizedTable.jsx";
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
@media (max-width: 900px){
.preview-toolbar .primary {
    grid-column: 1 / -1;
    width: 100%;
  }
}
.rb-query-result-card,
.rb-saved-card,
.rb-output-card,
.rb-identity-card,
.rb-columns-card,
.rb-preview-card {
  width: 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
  box-sizing: border-box !important;
  overflow: hidden !important;
}
.rb-card-heading,
.rb-preview-header {
  display: flex !important;
  align-items: flex-start !important;
  justify-content: space-between !important;
  gap: 18px !important;
  min-width: 0 !important;
}
.rb-card-heading > div:first-child,
.rb-preview-header > div:first-child {
  min-width: 0 !important;
}
.rb-eyebrow {
  display: block !important;
  margin-bottom: 5px !important;
  font-size: 10px !important;
  font-weight: 800 !important;
  letter-spacing: .12em !important;
  color: #64748b !important;
}
.rb-card-heading h3,
.rb-preview-header h3,
.rb-output-card h3 {
  margin: 0 !important;
  color: #0f172a !important;
}
.rb-card-heading p,
.rb-preview-header p,
.rb-output-card p {
  margin: 5px 0 0 !important;
  color: #64748b !important;
  font-size: 12px !important;
  line-height: 1.5 !important;
}
.rb-column-list {
  display: flex !important;
  flex-direction: column !important;
  gap: 4px !important;
  max-height: 520px !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  margin-top: 14px !important;
  padding-right: 3px !important;
}
.rb-preview-card {
  border-top: 3px solid #0891b2 !important;
  min-height: 620px !important;
}
.rb-preview-header {
  align-items: center !important;
}
.rb-preview-footer {
  display: flex !important;
  justify-content: space-between !important;
  gap: 12px !important;
  margin-top: 10px !important;
  padding-top: 10px !important;
  border-top: 1px solid #e2e8f0 !important;
  color: #64748b !important;
  font-size: 11px !important;
}
.rb-preview-footer strong {
  color: #0f172a !important;
}
@media (max-width: 800px){
.rb-preview-card {
    min-height: auto !important;
  }
}
@media (max-width: 560px){
.rb-card-heading,
  .rb-preview-header {
    flex-direction: column !important;
    align-items: stretch !important;
  }
}
.report-eyebrow,.rb-eyebrow{display:block;font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;opacity:.58}
.rb-card-heading,.rb-preview-header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.rb-card-heading h3,.rb-preview-header h3{margin:3px 0 4px}
.rb-card-heading p,.rb-preview-header p{margin:0;font-size:12px;line-height:1.45;opacity:.62}
.rb-column-list{display:flex;flex-direction:column;gap:3px;max-height:440px;overflow-y:auto;overflow-x:hidden;margin-top:7px}
.rb-preview-card{min-width:0}
.rb-preview-header{align-items:center;padding-bottom:15px;border-bottom:1px solid var(--border-color,#e5e7eb)}
.rb-preview-footer{display:flex;justify-content:space-between;gap:12px;padding-top:10px;margin-top:9px;border-top:1px solid var(--border-color,#e5e7eb);font-size:10px;opacity:.65}
.rb-preview-footer strong{opacity:1}
@media (max-width:560px){
.rb-card-heading,.rb-preview-header{flex-direction:column}
}
.data-source-manager .primary,
.data-source-manager .secondary,
.data-source-manager .danger-outline{
  min-height:36px;
  box-sizing:border-box;
  font-size:10px;
}
.data-source-manager .primary{padding:0 13px}
`;

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

/*
 * ============================================================
 * REPORT BUILDER
 * ============================================================
 *
 * This component deliberately does NOT open database connections.
 *
 * Input:
 *   - datasets: current reporting dataset definitions
 *   - initialResult: result produced by JoinDesigner/DataPreview
 *
 * Responsibilities:
 *   - Report identity
 *   - Save / Load / Save Changes / Delete
 *   - Column selection
 *   - Column ordering
 *   - Hide / Show
 *   - Column display-name changes
 *   - Formatting
 *   - Conditional formatting
 *   - Single-field preview filtering
 *   - CSV / JSON / HTML export
 *   - Print / PDF
 *
 * Source database tables are never modified by presentation changes.
 */

const EMPTY_RESULT = {
  success: false,
  columns: [],
  rows: [],
  total_rows: 0,
  returned_rows: 0,
  applied_joins: [],
  applied_columns: [],
  applied_filters: [],
  applied_sorts: [],
  applied_group_by: [],
  applied_aggregations: [],
  applied_calculated_columns: [],
  applied_limit: 0,
};

const REPORT_BUILDER_CSS = COMPONENT_APP_CSS + `
.rb-root {
  --rb-blue: #2563eb;
  --rb-blue-dark: #1d4ed8;
  --rb-blue-soft: #eff6ff;
  --rb-border: #d8e1ec;
  --rb-border-soft: #e8edf4;
  --rb-text: #172033;
  --rb-muted: #64748b;
  --rb-bg: #f6f8fb;
  --rb-card: #ffffff;
  min-height: calc(100vh - 112px);
  padding: 22px 28px 40px;
  background: var(--rb-bg);
  color: var(--rb-text);
}

.rb-root *,
.rb-root *::before,
.rb-root *::after {
  box-sizing: border-box;
}

.rb-eyebrow {
  display: block;
  margin-bottom: 4px;
  color: #718096;
  font-size: 8px;
  line-height: 1;
  font-weight: 850;
  letter-spacing: .14em;
  text-transform: uppercase;
}

.rb-page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
}

.rb-page-heading h2 {
  margin: 0 0 4px;
  color: #12213a;
  font-size: 25px;
  line-height: 1.15;
  letter-spacing: -.02em;
}

.rb-page-heading p {
  margin: 0;
  max-width: 800px;
  color: var(--rb-muted);
  font-size: 11px;
  line-height: 1.5;
}

.rb-card {
  margin-bottom: 14px;
  border: 1px solid var(--rb-border);
  border-radius: 11px;
  background: var(--rb-card);
  box-shadow: 0 3px 12px rgba(15, 23, 42, .045);
  overflow: hidden;
}

.rb-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 15px;
  padding: 14px 17px;
  border-bottom: 1px solid var(--rb-border-soft);
}

.rb-card-header h3 {
  margin: 3px 0 4px;
  color: #172033;
  font-size: 15px;
}

.rb-card-header p {
  margin: 0;
  color: var(--rb-muted);
  font-size: 10px;
  line-height: 1.45;
}

.rb-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border: 1px solid #bbf7d0;
  border-radius: 999px;
  background: #f0fdf4;
  color: #15803d;
  font-size: 9px;
  font-weight: 800;
  white-space: nowrap;
}

.rb-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
}

.rb-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
  padding: 13px 17px 16px;
}

.rb-stat {
  padding: 10px 11px;
  border: 1px solid var(--rb-border-soft);
  border-radius: 8px;
  background: #fbfcfe;
}

.rb-stat strong {
  display: block;
  color: #172033;
  font-size: 17px;
}

.rb-stat span {
  display: block;
  margin-top: 2px;
  color: #77849a;
  font-size: 8px;
  font-weight: 750;
  letter-spacing: .07em;
  text-transform: uppercase;
}

.rb-management {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.rb-management .rb-panel {
  height: 100%;
}

.rb-panel {
  min-width: 0;
  border: 1px solid var(--rb-border);
  border-radius: 9px;
  overflow: visible;
  background: #fff;
}

.rb-panel-header {
  min-height: 69px;
  padding: 12px 13px;
  border-bottom: 1px solid var(--rb-border-soft);
  background: #fbfcfe;
}

.rb-panel-header h3 {
  margin: 3px 0 3px;
  color: #172033;
  font-size: 13px;
}

.rb-panel-header p {
  margin: 0;
  color: var(--rb-muted);
  font-size: 9px;
  line-height: 1.4;
}

.rb-panel-body {
  padding: 12px 13px;
}

.rb-field {
  min-width: 0;
}

.rb-field label {
  display: block;
  margin-bottom: 4px;
  color: #526078;
  font-size: 8px;
  font-weight: 850;
  letter-spacing: .05em;
  text-transform: uppercase;
}

.rb-field input,
.rb-field select {
  width: 100%;
  min-height: 32px;
  border: 1px solid #cbd7e5;
  border-radius: 6px;
  background: #fff;
  color: #172033;
  padding: 6px 8px;
  font: inherit;
  font-size: 10px;
  outline: none;
}

.rb-field input:focus,
.rb-field select:focus {
  border-color: #7aa2f7;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, .08);
}

.rb-field-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(120px, .7fr);
  gap: 8px;
}

.rb-button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.rb-button-row.end {
  justify-content: flex-end;
}

.rb-btn {
  min-height: 32px;
  border: 1px solid #cbd7e5;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  padding: 6px 10px;
  font: inherit;
  font-size: 9px;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
}

.rb-btn:hover:not(:disabled) {
  border-color: #9fb2ca;
  background: #f8fafc;
}

.rb-btn:disabled {
  opacity: .45;
  cursor: not-allowed;
}

.rb-btn.primary {
  border-color: var(--rb-blue);
  background: var(--rb-blue);
  color: #fff;
}

.rb-btn.primary:hover:not(:disabled) {
  border-color: var(--rb-blue-dark);
  background: var(--rb-blue-dark);
}

.rb-btn.danger {
  border-color: #fecaca;
  color: #b91c1c;
}

.rb-btn.danger:hover:not(:disabled) {
  background: #fef2f2;
}

.rb-btn.subtle {
  border-color: #dbe5f0;
  background: #f8fafc;
  color: #475569;
}

.rb-saved-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 7px;
  align-items: end;
}

.rb-output-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.rb-export {
  position: relative;
}

.rb-export-menu {
  position: absolute;
  z-index: 80;
  top: calc(100% + 5px);
  right: 0;
  width: 150px;
  padding: 5px;
  border: 1px solid var(--rb-border);
  border-radius: 7px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, .15);
}

.rb-export-menu button {
  display: block;
  width: 100%;
  border: 0;
  border-radius: 5px;
  background: transparent;
  padding: 8px;
  color: #334155;
  text-align: left;
  font: inherit;
  font-size: 9px;
  cursor: pointer;
}

.rb-export-menu button:hover {
  background: #f1f5f9;
}

.rb-info {
  margin-top: 9px;
  padding: 7px 9px;
  border: 1px solid #dbeafe;
  border-radius: 6px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 9px;
  line-height: 1.4;
}

.rb-workspace {
  display: grid;
  grid-template-columns: minmax(275px, 325px) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.rb-sidebar {
  position: sticky;
  top: 14px;
  max-height: calc(100vh - 28px);
  min-width: 0;
  overflow-y: auto;
  scrollbar-width: thin;
}

.rb-side-card {
  margin-bottom: 12px;
  border: 1px solid var(--rb-border);
  border-radius: 9px;
  background: #fff;
  box-shadow: 0 3px 12px rgba(15, 23, 42, .04);
  overflow: hidden;
}

.rb-side-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 13px;
  border-bottom: 1px solid var(--rb-border-soft);
  background: #fbfcfe;
}

.rb-side-header h3 {
  margin: 3px 0 2px;
  color: #172033;
  font-size: 13px;
}

.rb-side-header p {
  margin: 0;
  color: var(--rb-muted);
  font-size: 9px;
  line-height: 1.4;
}

.rb-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 25px;
  padding: 0 6px;
  border: 1px solid #bfdbfe;
  border-radius: 7px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 9px;
  font-weight: 850;
}

.rb-side-body {
  padding: 10px;
}

.rb-column-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.rb-column-item {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) 18px 27px 27px;
  gap: 6px;
  align-items: center;
  min-width: 0;
  padding: 7px;
  border: 1px solid #e0e7ef;
  border-radius: 7px;
  background: #fff;
}

.rb-column-item.dragging {
  opacity: .45;
}

.rb-column-item.drag-over {
  border-color: #60a5fa;
  background: #eff6ff;
}

.rb-grip {
  color: #94a3b8;
  font-size: 12px;
  text-align: center;
  cursor: grab;
}

.rb-column-text {
  min-width: 0;
}

.rb-column-text strong {
  display: block;
  overflow: hidden;
  color: #334155;
  font-size: 9px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rb-column-text small {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  color: #94a3b8;
  font-size: 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rb-checkbox {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: var(--rb-blue);
}

.rb-icon {
  width: 27px;
  height: 27px;
  padding: 0;
  border: 1px solid #d5deea;
  border-radius: 6px;
  background: #fff;
  color: #64748b;
  font: inherit;
  font-size: 10px;
  font-weight: 800;
  cursor: pointer;
}

.rb-icon:hover {
  border-color: #a8b9ce;
  background: #f8fafc;
}

.rb-icon.active {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #2563eb;
}

.rb-settings {
  grid-column: 1 / -1;
  margin-top: 2px;
  padding: 10px;
  border: 1px solid #cbdcf7;
  border-radius: 8px;
  background: #f8fbff;
}

.rb-settings-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 9px;
}

.rb-settings-title strong {
  color: #1e3a8a;
  font-size: 9px;
}

.rb-settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.rb-full {
  grid-column: 1 / -1;
}

.rb-check-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.rb-check-label {
  display: inline-flex !important;
  align-items: center;
  gap: 5px;
  margin: 0 !important;
  color: #475569 !important;
  font-size: 8px !important;
  font-weight: 750 !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
}

.rb-color {
  width: 30px !important;
  height: 26px !important;
  min-height: 26px !important;
  padding: 2px !important;
}

.rb-rules {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #dbe6f3;
}

.rb-rules-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.rb-rules-heading strong {
  color: #475569;
  font-size: 8px;
  letter-spacing: .04em;
  text-transform: uppercase;
}

.rb-rule {
  margin-bottom: 6px;
  padding: 7px;
  border: 1px solid #dce5f1;
  border-radius: 6px;
  background: #fff;
}

.rb-rule-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 27px;
  gap: 6px;
  align-items: end;
}

.rb-rule-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  align-items: center;
}

.rb-preview-card {
  min-width: 0;
  border: 1px solid var(--rb-border);
  border-radius: 9px;
  background: #fff;
  box-shadow: 0 3px 12px rgba(15, 23, 42, .04);
  overflow: hidden;
}

.rb-preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 13px 15px;
  border-bottom: 1px solid var(--rb-border-soft);
}

.rb-preview-header h3 {
  margin: 3px 0 3px;
  color: #172033;
  font-size: 14px;
}

.rb-preview-header p {
  margin: 0;
  color: var(--rb-muted);
  font-size: 9px;
}

.rb-preview-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.rb-sortbar { display:grid; grid-template-columns:minmax(145px,1fr) 150px auto auto; gap:7px; align-items:end; padding:10px 14px; border-bottom:1px solid var(--rb-border-soft); background:#fff; }
.rb-filter {
  display: grid;
  grid-template-columns: minmax(145px, 1fr) 120px minmax(130px, 1fr) auto auto;
  gap: 7px;
  align-items: end;
  padding: 10px 14px;
  border-bottom: 1px solid var(--rb-border-soft);
  background: #fbfcfe;
}

.rb-table-wrap {
  width: 100%;
  max-height: 600px;
  overflow: auto;
}

.rb-table {
  width: 100%;
  min-width: 700px;
  border-collapse: separate;
  border-spacing: 0;
}

.rb-table th {
  position: sticky;
  top: 0;
  z-index: 3;
  padding: 8px 9px;
  border-bottom: 1px solid #d8e0eb;
  background: #f8fafc;
  color: #475569;
  font-size: 8px;
  font-weight: 850;
  text-align: left;
  white-space: nowrap;
}

.rb-table td {
  padding: 7px 9px;
  border-bottom: 1px solid #edf1f5;
  color: #475569;
  font-size: 8px;
  vertical-align: top;
  max-width: 360px;
}

.rb-table tbody tr:hover {
  background: #fbfdff;
}

.rb-preview-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 13px;
  border-top: 1px solid var(--rb-border-soft);
  color: #7b8799;
  font-size: 8px;
}

.rb-message {
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid #bfdbfe;
  border-radius: 7px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 9px;
  line-height: 1.4;
}

.rb-empty {
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px;
  text-align: center;
}

.rb-empty-icon {
  width: 43px;
  height: 43px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 9px;
  border-radius: 11px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 19px;
}

.rb-empty strong {
  color: #334155;
  font-size: 12px;
}

.rb-empty span {
  max-width: 430px;
  margin-top: 5px;
  color: var(--rb-muted);
  font-size: 9px;
  line-height: 1.5;
}

.rb-print-document {
  display: none;
}

.rb-warning {
  margin: 0 0 12px;
  padding: 9px 11px;
  border: 1px solid #fed7aa;
  border-radius: 7px;
  background: #fff7ed;
  color: #9a3412;
  font-size: 9px;
}

.rb-source-note {
  padding: 7px 9px;
  margin-top: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #64748b;
  font-size: 8px;
  line-height: 1.45;
}

.rb-source-note strong {
  color: #334155;
}

/* ============================================================
 * REPORT BUILDER PAGE ROWS
 * ============================================================ */
.rb-management-row {
  width: 100%;
}

.rb-formatting-row {
  width: 100%;
  margin-bottom: 14px;
}

.rb-formatting-card {
  margin-bottom: 0;
}

.rb-workspace-row {
  width: 100%;
}

.rb-output-warning {
  margin-top: 10px;
}

.rb-output-warning .rb-button-row {
  flex-wrap: wrap;
}

.rb-output-warning.saved {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #64748b;
}

.rb-output-warning.saved strong {
  color: #15803d;
}

.rb-export-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--rb-border-soft);
}

.rb-save-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 8px;
  color: #64748b;
}

@media (max-width: 1150px) {
  .rb-management {
    grid-template-columns: 1fr;
  }

  .rb-workspace {
    grid-template-columns: 1fr;
  }

  .rb-sidebar {
    position: static;
    max-height: none;
    overflow: visible;
  }
}

@media (max-width: 760px) {
  .rb-root {
    padding: 14px;
  }

  .rb-page-heading {
    align-items: flex-start;
  }

  .rb-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rb-field-grid,
  .rb-settings-grid {
    grid-template-columns: 1fr;
  }

  .rb-full {
    grid-column: auto;
  }

  .rb-filter {
    grid-template-columns: 1fr;
  }

  .rb-preview-header {
    flex-direction: column;
  }

  .rb-preview-actions {
    justify-content: flex-start;
  }

  .rb-saved-grid {
    grid-template-columns: 1fr;
  }
}

@media print {
  body * {
    visibility: hidden !important;
  }

  .rb-print-document,
  .rb-print-document * {
    visibility: visible !important;
  }

  .rb-print-document {
    display: block;
    position: absolute;
    inset: 0;
    padding: 20px;
    background: #fff;
  }
}


/* ============================================================
 * REPORT BUILDER EXTENSIONS — presentation and interaction
 * ============================================================ */
.rb-dirty-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid #fed7aa;border-radius:999px;background:#fff7ed;color:#c2410c;font-size:9px;font-weight:800;white-space:nowrap}
.rb-saved-actions,.rb-identity-actions{margin-top:10px}
.rb-export-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;padding-top:8px;border-top:1px solid var(--rb-border-soft)}
.rb-output-warning{display:flex;flex-direction:column;gap:5px;margin-top:10px;padding:8px 9px;border:1px solid #dbeafe;border-radius:7px;background:#f8fbff;color:#64748b;font-size:8px;line-height:1.45}
.rb-output-warning strong{color:#1d4ed8;font-size:9px}.rb-output-warning .rb-button-row{margin-top:3px}
.rb-formatting-card{margin-bottom:14px}.rb-format-body{padding:12px 17px 14px}.rb-format-types{display:flex;flex-wrap:wrap;gap:7px}
.rb-view-button{min-height:34px;padding:7px 12px;border:1px solid #cbd7e5;border-radius:7px;background:#fff;color:#475569;font:inherit;font-size:9px;font-weight:800;cursor:pointer}.rb-view-button:hover{background:#f8fafc}.rb-view-button.active{border-color:#2563eb;background:#eff6ff;color:#2563eb}
.rb-format-state{padding:5px 9px;border:1px solid #bfdbfe;border-radius:999px;background:#eff6ff;color:#2563eb;font-size:8px;font-weight:850}
.rb-chart-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:10px;padding-top:10px;border-top:1px solid var(--rb-border-soft)}
.rb-conditional-summary,.rb-conditional-empty{margin:8px 0;padding:7px 9px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc;color:#64748b;font-size:8px;line-height:1.4}
.rb-report-content{min-height:430px}.rb-filter-note{padding:7px 14px;border-bottom:1px solid #e8edf4;background:#f8fbff;color:#2563eb;font-size:8px}
.rb-chart-empty{min-height:390px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px;text-align:center}.rb-chart-empty strong{color:#334155;font-size:12px}.rb-chart-empty span{max-width:430px;margin-top:5px;color:var(--rb-muted);font-size:9px;line-height:1.5}
.rb-chart-shell{width:100%;padding:20px 20px 10px;overflow-x:auto}.rb-chart-svg{display:block;width:100%;min-width:650px;height:auto}
.rb-chart-pie-layout{display:grid;grid-template-columns:minmax(260px,1fr) minmax(220px,.9fr);gap:20px;align-items:center;min-height:390px;padding:25px}.rb-pie{width:min(280px,100%);aspect-ratio:1;margin:0 auto;border-radius:50%;display:grid;place-items:center;box-shadow:inset 0 0 0 1px rgba(15,23,42,.05)}
.rb-pie-hole{width:42%;aspect-ratio:1;display:grid;place-items:center;border-radius:50%;background:#fff;color:#475569;font-size:12px;font-weight:850;box-shadow:0 2px 8px rgba(15,23,42,.08)}
.rb-chart-legend{display:flex;flex-direction:column;gap:7px;max-height:330px;overflow:auto}.rb-legend-item{display:grid;grid-template-columns:10px minmax(0,1fr) auto;gap:7px;align-items:center;padding:6px 8px;border:1px solid #e5eaf1;border-radius:6px;background:#fbfcfe;color:#475569;font-size:8px}.rb-legend-item span:nth-child(2){overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rb-legend-item strong{color:#172033}.rb-legend-dot{width:9px;height:9px;border-radius:50%}
.rb-column-item{grid-template-columns:20px minmax(0,1fr) 18px 27px 27px 27px}
.rb-remove-icon{color:#b91c1c;border-color:#fecaca}.rb-remove-icon:hover{background:#fef2f2;border-color:#fca5a5}
.rb-chart-backend-note{grid-column:1 / -1;padding:7px 9px;border:1px solid #dbe7ff;border-radius:6px;background:#f6f9ff;color:#315b9d;font-size:8px}.rb-chart-fields input{width:100%;min-height:38px;border:1px solid #d5dde8;border-radius:6px;padding:0 9px;font:inherit;font-size:9px;color:#344054}
@media (max-width:900px){.rb-chart-fields,.rb-chart-pie-layout{grid-template-columns:1fr}}

`;


function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function safeText(value) {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  return String(value);
}

function displayName(value) {
  const text = safeText(value);

  return text
    .replace(/^[^.]+\./, "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase()
    );
}

function getColumnName(column) {
  if (typeof column === "string") {
    return column;
  }

  return (
    column?.name ||
    column?.field ||
    column?.column_name ||
    column?.key ||
    ""
  );
}

function getColumnType(column, rows) {
  const sample = rows.find((row) => {
    const value = row?.[column];

    return (
      value !== null &&
      value !== undefined &&
      value !== ""
    );
  })?.[column];

  if (typeof sample === "number") {
    return "number";
  }

  if (typeof sample === "boolean") {
    return "boolean";
  }

  return "string";
}

function makeId(prefix = "id") {
  return `${prefix}_${Date.now()}_${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

function slug(value) {
  return (
    safeText(value)
      .trim()
      .replace(/[^a-z0-9]+/gi, "_")
      .replace(/^_+|_+$/g, "")
      .toLowerCase() || "report"
  );
}

function readSavedReports() {
  return [];
}

async function fetchSavedReports() {
  const response = await apiFetch(`${API}/reports`, {
    headers: { Accept: "application/json" },
  });
  const data = await response.json();
  if (!response.ok || !data.success) {
    throw new Error(data.message || data.detail || `Unable to load saved reports (HTTP ${response.status}).`);
  }
  return Array.isArray(data.reports) ? data.reports : [];
}


function normalizeResult(value) {
  const source = value || EMPTY_RESULT;

  return {
    ...EMPTY_RESULT,
    ...source,
    columns: safeArray(source.columns),
    rows: safeArray(source.rows),
    applied_joins: safeArray(
      source.applied_joins
    ),
  };
}

function normalizeColumn(column, rows, saved = {}) {
  const sourceName =
    saved.sourceName ||
    saved.source_name ||
    getColumnName(column);

  const type =
    saved.dataType ||
    saved.data_type ||
    getColumnType(sourceName, rows);

  return {
    id: saved.id || makeId("column"),
    sourceName,
    displayName:
      saved.displayName ||
      saved.display_name ||
      displayName(sourceName),
    dataType: type,
    selected:
      saved.selected !== undefined
        ? Boolean(saved.selected)
        : true,
    visible:
      saved.visible !== undefined
        ? Boolean(saved.visible)
        : true,
    align:
      saved.align ||
      (type === "number" ? "right" : "left"),
    width: saved.width || "auto",
    numberFormat:
      saved.numberFormat ||
      saved.number_format ||
      "automatic",
    decimals:
      Number.isFinite(
        Number(saved.decimals)
      )
        ? Number(saved.decimals)
        : 2,
    nullDisplay:
      saved.nullDisplay ??
      saved.null_display ??
      "—",
    bold: Boolean(saved.bold),
    italic: Boolean(saved.italic),
    wrap: Boolean(saved.wrap),
    textColor:
      saved.textColor ||
      saved.text_color ||
      "#475569",
    backgroundColor:
      saved.backgroundColor ||
      saved.background_color ||
      "#ffffff",
    conditionalRules: safeArray(
      saved.conditionalRules ||
        saved.conditional_rules
    ),
  };
}

function compareValues(actual, expected, operator) {
  const a = safeText(actual);
  const b = safeText(expected);

  const an = Number(a);
  const bn = Number(b);

  const numeric =
    a !== "" &&
    b !== "" &&
    Number.isFinite(an) &&
    Number.isFinite(bn);

  switch (operator) {
    case "equals":
      return a === b;

    case "not_equals":
      return a !== b;

    case "contains":
      return a
        .toLowerCase()
        .includes(b.toLowerCase());

    case "starts_with":
      return a
        .toLowerCase()
        .startsWith(b.toLowerCase());

    case "ends_with":
      return a
        .toLowerCase()
        .endsWith(b.toLowerCase());

    case "greater_than":
      return numeric && an > bn;

    case "less_than":
      return numeric && an < bn;

    case "greater_equal":
      return numeric && an >= bn;

    case "less_equal":
      return numeric && an <= bn;

    default:
      return false;
  }
}

function filterRows(rows, filter) {
  if (
    !filter?.column ||
    safeText(filter.value).trim() === ""
  ) {
    return rows;
  }

  return rows.filter((row) =>
    compareValues(
      row?.[filter.column],
      filter.value,
      filter.operator
    )
  );
}

function formatCell(value, column) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return column?.nullDisplay ?? "—";
  }

  const number = Number(value);

  if (
    Number.isFinite(number) &&
    column?.numberFormat !== "automatic"
  ) {
    const decimals = Number(
      column.decimals ?? 2
    );

    if (column.numberFormat === "integer") {
      return Math.round(number).toLocaleString(
        "en-IN"
      );
    }

    if (column.numberFormat === "decimal") {
      return number.toLocaleString("en-IN", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    }

    if (
      column.numberFormat === "percentage"
    ) {
      return `${(
        number * 100
      ).toFixed(decimals)}%`;
    }

    if (column.numberFormat === "currency") {
      return `₹${number.toLocaleString(
        "en-IN",
        {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        }
      )}`;
    }
  }

  return safeText(value);
}

function conditionalStyle(value, column) {
  const rules = safeArray(
    column?.conditionalRules
  );

  for (const rule of rules) {
    if (
      compareValues(
        value,
        rule.value,
        rule.operator
      )
    ) {
      return {
        color: rule.textColor || undefined,
        backgroundColor:
          rule.backgroundColor || undefined,
        fontWeight: rule.bold
          ? 800
          : undefined,
      };
    }
  }

  return {};
}

function downloadFile(
  content,
  mimeType,
  filename
) {
  const blob = new Blob(
    [content],
    { type: mimeType }
  );

  const url =
    URL.createObjectURL(blob);

  const anchor =
    document.createElement("a");

  anchor.href = url;
  anchor.download = filename;

  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  setTimeout(
    () => URL.revokeObjectURL(url),
    0
  );
}

function csvEscape(value) {
  return `"${safeText(value).replace(
    /"/g,
    '""'
  )}"`;
}


function reportSignature(report) {
  if (!report) return "";
  const normalized = {
    name: report.name || "", visualization: report.visualization || "table",
    columns: safeArray(report.columns), filters: report.filters || { column: "", operator: "contains", value: "" },
    filter_active: Boolean(report.filter_active), preview_sort: report.preview_sort || { column: "", direction: "asc" }, datasets: safeArray(report.datasets), joins: safeArray(report.joins),
    applied_columns: safeArray(report.applied_columns), applied_filters: safeArray(report.applied_filters),
    applied_sorts: safeArray(report.applied_sorts), applied_group_by: safeArray(report.applied_group_by),
    applied_aggregations: safeArray(report.applied_aggregations), applied_calculated_columns: safeArray(report.applied_calculated_columns),
    applied_limit: Number(report.applied_limit ?? 0),
  };
  return JSON.stringify(normalized);
}

function chartNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function buildChartData(rows, categoryField, valueField, type) {
  const safeRows = safeArray(rows);
  if (type === "histogram") {
    const numbers = safeRows.map((row) => chartNumber(row?.[valueField])).filter((item) => item !== null);
    if (!numbers.length) return [];
    const min = Math.min(...numbers); const max = Math.max(...numbers); const bins = 6;
    const span = max - min; const step = span === 0 ? 1 : span / bins;
    const counts = Array.from({ length: bins }, (_, index) => ({
      label: span === 0 ? safeText(min) : `${Number(min + index * step).toPrecision(4)}–${Number(min + (index + 1) * step).toPrecision(4)}`, value: 0,
    }));
    numbers.forEach((number) => { let index = span === 0 ? 0 : Math.floor((number - min) / step); if (index >= bins) index = bins - 1; counts[index].value += 1; });
    return counts;
  }
  if (!categoryField || !valueField) return [];
  const grouped = new Map();
  safeRows.forEach((row) => {
    const label = safeText(row?.[categoryField]) || "(Blank)"; const number = chartNumber(row?.[valueField]);
    if (number === null) return; grouped.set(label, (grouped.get(label) || 0) + number);
  });
  return Array.from(grouped.entries()).slice(0, 20).map(([label, number]) => ({ label, value: number }));
}

export default function ReportBuilder({
  datasets = [],
  initialResult,
  onBack,
  onOpenDataSources,
  onOpenDashboard,
}) {
  const [result, setResult] =
    useState(() =>
      normalizeResult(initialResult)
    );

  const [columnConfigs, setColumnConfigs] =
    useState([]);

  const [reportName, setReportName] =
    useState("Custom Report");

  const [visualization, setVisualization] =
    useState("table");

  const [chartCategoryField, setChartCategoryField] = useState("");
  const [chartValueField, setChartValueField] = useState("");
  const [committedSignature, setCommittedSignature] = useState("");

  const [savedReports, setSavedReports] =
    useState(readSavedReports);

  const [, setReportLoading] = useState(false);
  const [visualizationLoading, setVisualizationLoading] = useState(false);
  const [visualizationData, setVisualizationData] = useState(null);
  const [chartAggregation, setChartAggregation] = useState("SUM");
  const [chartLimit, setChartLimit] = useState(20);
  const [chartBins, setChartBins] = useState(6);
  const [chartSortDirection, setChartSortDirection] = useState("DESC");
  const [, setVisualizationFields] = useState(null);

  const [
    selectedSavedReport,
    setSelectedSavedReport,
  ] = useState("");

  const [formatColumnId, setFormatColumnId] =
    useState("");

  const [filter, setFilter] = useState({
    column: "",
    operator: "contains",
    value: "",
  });

  const [filterActive, setFilterActive] =
    useState(false);

  const [sort, setSort] = useState({
    column: "",
    direction: "asc",
  });

  const [sortActive, setSortActive] =
    useState(false);

  const [previewRows, setPreviewRows] =
    useState([]);

  const [serverBaseFilters] = useState(() => safeArray(initialResult?.applied_filters));
  const [serverBaseSorts] = useState(() => safeArray(initialResult?.applied_sorts));
  const [operationLoading, setOperationLoading] = useState(false);
  const operationControllerRef = useRef(null);

  const [message, setMessage] =
    useState("");

  const [exportOpen, setExportOpen] =
    useState(false);

  const [draggingId, setDraggingId] =
    useState("");

  const [dragOverId, setDragOverId] =
    useState("");

  const sourceColumns = useMemo(
    () =>
      safeArray(result.columns)
        .map(getColumnName)
        .filter(Boolean),
    [result.columns]
  );

  const sourceRows = useMemo(
    () => safeArray(result.rows),
    [result.rows]
  );

  useEffect(() => {
    // Intentional synchronization of externally supplied initial result.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setResult(
      normalizeResult(initialResult)
    );
  }, [initialResult]);

  useEffect(() => {
    let active = true;
    const loadReports = async () => {
      setReportLoading(true);
      try {
        const reports = await fetchSavedReports();
        if (active) setSavedReports(reports);
      } catch (error) {
        console.warn("Unable to load backend saved reports.", error);
        if (active) setMessage(`Saved reports unavailable: ${error.message}`);
      } finally {
        if (active) setReportLoading(false);
      }
    };
    loadReports();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    // Reorder the local column configuration without changing source data.
    // This is intentional state synchronization: columnConfigs contains user-editable
    // presentation settings that must be reconciled when source columns change.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setColumnConfigs((current) => {
      const byName = new Map(
        current.map((column) => [
          column.sourceName,
          column,
        ])
      );

      return sourceColumns.map((name) =>
        normalizeColumn(
          name,
          sourceRows,
          byName.get(name) || {}
        )
      );
    });
  }, [sourceColumns, sourceRows]);

  useEffect(() => {
    if (!sourceColumns.length) {
      // Intentional reset when no source columns exist.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFilter({
        column: "",
        operator: "contains",
        value: "",
      });

      setPreviewRows([]);
      setFilterActive(false);
      setSort({ column: "", direction: "asc" });
      setSortActive(false);
      return;
    }

    setFilter((current) => ({
      ...current,
      column: sourceColumns.includes(
        current.column
      )
        ? current.column
        : sourceColumns[0],
    }));

    setPreviewRows(sourceRows);
  }, [sourceColumns, sourceRows]);


  const selectedColumns = useMemo(
    () =>
      columnConfigs.filter(
        (column) => column.selected
      ),
    [columnConfigs]
  );

  const visibleColumns = useMemo(
    () =>
      columnConfigs.filter(
        (column) =>
          column.selected &&
          column.visible
      ),
    [columnConfigs]
  );

  const selectedFormatColumn =
    columnConfigs.find(
      (column) =>
        column.id === formatColumnId
    ) || null;

  // Sorting/filtering is executed server-side. Keep the FE result window intact
  // so ReportBuilder never clones or re-sorts a potentially large result page.
  const displayedRows = useMemo(
    () => (filterActive ? previewRows : sourceRows),
    [filterActive, previewRows, sourceRows]
  );

  const updateColumn = (
    id,
    changes
  ) => {
    setColumnConfigs((current) =>
      current.map((column) =>
        column.id === id
          ? { ...column, ...changes }
          : column
      )
    );
  };

  const moveColumn = (
    sourceId,
    targetId
  ) => {
    if (
      !sourceId ||
      !targetId ||
      sourceId === targetId
    ) {
      return;
    }

    // Reorder the local column configuration without changing source data.
    setColumnConfigs((current) => {
      const from =
        current.findIndex(
          (item) =>
            item.id === sourceId
        );

      const to =
        current.findIndex(
          (item) =>
            item.id === targetId
        );

      if (from < 0 || to < 0) {
        return current;
      }

      const next = [...current];
      const [item] =
        next.splice(from, 1);

      next.splice(to, 0, item);

      return next;
    });
  };

  const runServerOperation = async (operations, successMessage) => {
    const sourceJobId = result?.execution_job_id;
    if (!sourceJobId) {
      setMessage("This result has no execution job. Re-run the query before using server-side operations.");
      return null;
    }

    operationControllerRef.current?.abort();
    const controller = new AbortController();
    operationControllerRef.current = controller;
    setOperationLoading(true);
    try {
      const { jobId, result: nextResult } = await transformExecutionJob(sourceJobId, operations, {
        loadAll: false,
        pageSize: 5000,
        returnOnFirstPage: true,
        signal: controller.signal,
      });
      const merged = normalizeResult({
        ...nextResult,
        execution_job_id: jobId,
        applied_filters: operations.filters || [],
        applied_sorts: operations.sorts || [],
        applied_group_by: operations.group_by || [],
        applied_aggregations: operations.aggregations || [],
      });
      setResult(merged);
      setPreviewRows(safeArray(merged.rows));
      setMessage(successMessage);
      return merged;
    } catch (error) {
      if (error?.name === "AbortError") return null;
      setMessage(`Operation failed: ${error.message}`);
      return null;
    } finally {
      if (operationControllerRef.current === controller) {
        operationControllerRef.current = null;
        setOperationLoading(false);
      }
    }
  };

  const applyFilter = async () => {
    if (!filter.column) {
      setMessage("Select a field before applying the filter.");
      return;
    }
    if (safeText(filter.value).trim() === "") {
      setMessage("Enter a value before applying the filter.");
      return;
    }

    const serverFilter = {
      field: filter.column.includes(".") ? filter.column : filter.column,
      operator: ({ contains: "CONTAINS", equals: "=", not_equals: "!=", starts_with: "STARTS_WITH", ends_with: "ENDS_WITH", greater_than: ">", less_than: "<", greater_equal: ">=", less_equal: "<=" })[filter.operator] || "CONTAINS",
      value: filter.value,
      logic: "AND",
    };
    await runServerOperation(
      { filters: [...serverBaseFilters, serverFilter], sorts: serverBaseSorts },
      "Filter executed server-side. Only the result page is loaded into the browser.",
    );
    setFilterActive(true);
  };

  const clearFilter = async () => {
    const cleared = await runServerOperation(
      { filters: serverBaseFilters, sorts: serverBaseSorts },
      "Filter cleared server-side. Only the result page is loaded into the browser.",
    );
    if (cleared) {
      setFilterActive(false);
      setFilter((current) => ({ ...current, value: "" }));
    }
  };

  const applySort = async () => {
    if (!sort.column) {
      setMessage("Select a field before applying the sort.");
      return;
    }
    await runServerOperation(
      { filters: serverBaseFilters, sorts: [{ field: sort.column, direction: sort.direction === "desc" ? "DESC" : "ASC" }] },
      `Sort executed server-side: ${displayName(sort.column)} ${sort.direction === "desc" ? "descending" : "ascending"}.`,
    );
    setSortActive(true);
  };

  const clearSort = async () => {
    const cleared = await runServerOperation(
      { filters: serverBaseFilters, sorts: [] },
      "Sort cleared server-side. Only the result page is loaded into the browser.",
    );
    if (cleared) {
      setSortActive(false);
      setSort({ column: sourceColumns[0] || "", direction: "asc" });
    }
  };

  const buildReportDefinition =
    () => ({
      id:
        selectedSavedReport ||
        makeId("report"),
      name:
        reportName.trim() ||
        "Untitled Report",
      saved_at:
        new Date().toISOString(),
      visualization,
      columns: columnConfigs,
      filters: filterActive
        ? filter
        : {
            column: "",
            operator: "contains",
            value: "",
          },
      filter_active: filterActive,
      preview_sort: sortActive ? sort : { column: "", direction: "asc" },
      datasets: safeArray(datasets).map(
        (dataset) => ({
          id: dataset.id,
          connectionId:
            dataset.connectionId ||
            dataset.connection_id ||
            null,
          sourceType:
            dataset.sourceType ||
            dataset.source_type ||
            null,
          connectionName:
            dataset.connectionName ||
            null,
          database:
            dataset.database ||
            dataset.schema ||
            null,
          table:
            dataset.table ||
            dataset.object_name ||
            dataset.collection ||
            null,
          columns: safeArray(
            dataset.columns
          ).map(getColumnName),
        })
      ),
      joins: safeArray(
        result.applied_joins
      ),
      applied_columns: safeArray(
        result.applied_columns
      ),
      applied_filters: safeArray(
        result.applied_filters
      ),
      applied_sorts: safeArray(
        result.applied_sorts
      ),
      applied_group_by: safeArray(
        result.applied_group_by
      ),
      applied_aggregations: safeArray(
        result.applied_aggregations
      ),
      applied_calculated_columns:
        safeArray(
          result.applied_calculated_columns
        ),
      applied_limit:
        Number(
          result.applied_limit ??
            0
        ),
        execution_job_id: result?.execution_job_id || null,
    });

  const currentReportSignature = reportSignature(buildReportDefinition());
  const hasUnsavedChanges = !selectedSavedReport || committedSignature !== currentReportSignature;

  const effectiveChartCategoryField =
    chartCategoryField && sourceColumns.includes(chartCategoryField)
      ? chartCategoryField
      : sourceColumns[0] || "";

  const effectiveChartValueField =
    chartValueField && sourceColumns.includes(chartValueField)
      ? chartValueField
      : sourceColumns.find((column) => getColumnType(column, sourceRows) === "number") || sourceColumns[0] || "";

  useEffect(() => {
    if (!sourceColumns.length) {
      // These are intentional cleanup transitions for derived visualization state.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVisualizationFields(null);
      setVisualizationData(null);
      return;
    }

    let active = true;
    const loadVisualizationFields = async () => {
      try {
        const response = await apiFetch(`${API}/report/visualization/fields`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({
            columns: sourceColumns,
            rows: sourceRows,
          }),
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to determine visualization fields.");
        if (active) setVisualizationFields(data);
      } catch (error) {
        console.warn("Visualization field discovery failed; local field inference remains available.", error);
      }
    };
    loadVisualizationFields();
    return () => { active = false; };
  }, [sourceColumns, sourceRows]);

  useEffect(() => {
    if (visualization === "table" || visualization === "data-grid" || !sourceRows.length) {
      // Intentional cleanup of derived visualization data when charting is inactive.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVisualizationData(null);
      return undefined;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setVisualizationLoading(true);
      try {
        const body = {
          visualization,
          category_field: visualization === "histogram" ? null : effectiveChartCategoryField,
          value_field: effectiveChartValueField,
          aggregation: chartAggregation,
          limit: Number(chartLimit) || 20,
          bins: Number(chartBins) || 6,
          sort_direction: chartSortDirection,
          columns: sourceColumns,
          rows: displayedRows,
        };
        const response = await apiFetch(`${API}/report/visualization/preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Visualization preview failed.");
        setVisualizationData(data);
      } catch (error) {
        if (error?.name !== "AbortError") {
          console.warn("Backend visualization preview failed; using local chart fallback.", error);
          setVisualizationData(null);
        }
      } finally {
        if (!controller.signal.aborted) setVisualizationLoading(false);
      }
    }, 150);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [visualization, effectiveChartCategoryField, effectiveChartValueField, chartAggregation, chartLimit, chartBins, chartSortDirection, sourceColumns, displayedRows, sourceRows.length]);

  const saveNewReport = async () => {
    const name = reportName.trim();
    if (!name) { setMessage("Enter a report name before saving."); return false; }
    setReportLoading(true);
    try {
      const reportId = makeId("report");
      const definition = {
        ...buildReportDefinition(),
        id: reportId,
        name,
        saved_at: new Date().toISOString(),
      };
      const payload = {
        id: reportId,
        name,
        definition,
      };
      const response = await apiFetch(`${API}/reports`, {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to save report.");
      const savedRecord = data.report || payload;
      const saved = savedRecord.definition || savedRecord;
      const reports = await fetchSavedReports();
      setSavedReports(reports);
      setSelectedSavedReport(savedRecord.id || reportId);
      setCommittedSignature(reportSignature(saved));
      setMessage(`Report "${savedRecord.name || name}" saved successfully.`);
      return true;
    } catch (error) {
      setMessage(`Error: ${error.message}`);
      return false;
    } finally {
      setReportLoading(false);
    }
  };

  const saveChanges = async () => {
    if (!selectedSavedReport) { setMessage("Select an existing saved report before saving changes."); return false; }
    setReportLoading(true);
    try {
      const name = reportName.trim() || "Untitled Report";
      const definition = {
        ...buildReportDefinition(),
        id: selectedSavedReport,
        name,
        saved_at: new Date().toISOString(),
      };
      const payload = {
        id: selectedSavedReport,
        name,
        definition,
      };
      const response = await apiFetch(`${API}/reports`, {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to save report changes.");
      const savedRecord = data.report || payload;
      const saved = savedRecord.definition || savedRecord;
      const reports = await fetchSavedReports();
      setSavedReports(reports);
      setCommittedSignature(reportSignature(saved));
      setMessage(`Changes saved to "${savedRecord.name || name}".`);
      return true;
    } catch (error) {
      setMessage(`Error: ${error.message}`);
      return false;
    } finally {
      setReportLoading(false);
    }
  };

  const loadReport = async () => {
    if (!selectedSavedReport) { setMessage("Select a saved report first."); return; }
    setReportLoading(true);
    try {
      const response = await apiFetch(`${API}/reports/${encodeURIComponent(selectedSavedReport)}`, { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to load saved report.");
      const storedReport = data.report || data;
      const report = storedReport.definition || storedReport;

      const savedExecutionJobId = report.execution_job_id || null;
      let loadedResult = normalizeResult(result);

      if (savedExecutionJobId) {
        try {
          const page = await fetchExecutionJobResultPage(savedExecutionJobId, {
            offset: 0,
            limit: 5000,
          });
          if (!page?.success) {
            throw new Error(page?.message || "Unable to load the saved report result.");
          }
          loadedResult = normalizeResult({
            ...page,
            execution_job_id: savedExecutionJobId,
          });
          setMessage("Saved report configuration and its latest result loaded.");
        } catch (resultError) {
          setMessage(`Saved report loaded, but its execution result could not be restored: ${resultError.message}`);
          loadedResult = normalizeResult({ ...result, execution_job_id: savedExecutionJobId });
        }
      } else {
        loadedResult = normalizeResult({ ...result, execution_job_id: null });
      }

      setResult(loadedResult);

    const loadedSourceColumns = safeArray(loadedResult.columns).map(getColumnName).filter(Boolean);
    const loadedSourceRows = safeArray(loadedResult.rows);

    setReportName(
      report.name ||
        "Custom Report"
    );

    setVisualization(
      report.visualization ||
        "table"
    );

    const savedColumns =
      safeArray(report.columns);

    const normalized =
      loadedSourceColumns.map(
        (name) => {
          const saved =
            savedColumns.find(
              (item) =>
                item.sourceName ===
                name
            );

          return normalizeColumn(
            name,
            loadedSourceRows,
            saved || {}
          );
        }
      );

    const savedOrder =
      savedColumns
        .map(
          (item) =>
            item.sourceName
        )
        .filter((name) =>
          loadedSourceColumns.includes(name)
        );

    const ordered = [
      ...savedOrder
        .map((name) =>
          normalized.find(
            (column) =>
              column.sourceName ===
              name
          )
        )
        .filter(Boolean),

      ...normalized.filter(
        (column) =>
          !savedOrder.includes(
            column.sourceName
          )
      ),
    ];

    setColumnConfigs(ordered);

    const savedFilter =
      report.filters || {
        column:
          loadedSourceColumns[0] || "",
        operator: "contains",
        value: "",
      };

    setFilter({
      column:
        loadedSourceColumns.includes(
          savedFilter.column
        )
          ? savedFilter.column
          : loadedSourceColumns[0] || "",
      operator:
        savedFilter.operator ||
        "contains",
      value:
        savedFilter.value || "",
    });

    setFilterActive(
      Boolean(report.filter_active)
    );

    const savedSort = report.preview_sort || { column: "", direction: "asc" };
    setSort({
      column: loadedSourceColumns.includes(savedSort.column) ? savedSort.column : loadedSourceColumns[0] || "",
      direction: savedSort.direction === "desc" ? "desc" : "asc",
    });
    setSortActive(Boolean(savedSort.column && loadedSourceColumns.includes(savedSort.column)));

    setPreviewRows(
      report.filter_active
        ? filterRows(
            loadedSourceRows,
            savedFilter
          )
        : loadedSourceRows
    );

    setFormatColumnId("");
    setCommittedSignature(reportSignature(report));

    setMessage(
      `Report "${report.name}" loaded.`
    );
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setReportLoading(false);
    }
  };

  const deleteReport = async () => {
    if (!selectedSavedReport) { setMessage("Select a saved report first."); return; }
    const report = savedReports.find((item) => item.id === selectedSavedReport);
    if (!window.confirm(`Delete saved report "${report?.name || "this report"}"? This cannot be undone.`)) return;
    setReportLoading(true);
    try {
      const response = await apiFetch(`${API}/reports/${encodeURIComponent(selectedSavedReport)}`, { method: "DELETE", headers: { Accept: "application/json" } });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || data.detail || "Unable to delete saved report.");
      const reports = await fetchSavedReports();
      setSavedReports(reports);
      setSelectedSavedReport("");
      setCommittedSignature("");
      setMessage(report ? `Report "${report.name}" deleted.` : "Saved report deleted.");
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally { setReportLoading(false); }
  };

  const removeColumn = (columnId) => {
    const column = columnConfigs.find((item) => item.id === columnId);
    if (!column) return;
    if (!window.confirm(`Remove "${column.displayName}" from this report? The source database column will not be changed.`)) return;
    setColumnConfigs((current) => current.filter((item) => item.id !== columnId));
    if (formatColumnId === columnId) setFormatColumnId("");
    setMessage(`"${column.displayName}" removed from the report.`);
  };

  const addConditionalRule =
    () => {
      if (!selectedFormatColumn) {
        setMessage(
          "Open column settings first."
        );
        return;
      }

      const rule = {
        id: makeId("rule"),
        operator: "equals",
        value: "",
        textColor: "#991b1b",
        backgroundColor:
          "#fee2e2",
        bold: true,
      };

      updateColumn(
        selectedFormatColumn.id,
        {
          conditionalRules: [
            ...safeArray(
              selectedFormatColumn.conditionalRules
            ),
            rule,
          ],
        }
      );
    };

  const updateRule = (
    columnId,
    ruleId,
    changes
  ) => {
    const column =
      columnConfigs.find(
        (item) =>
          item.id === columnId
      );

    if (!column) return;

    updateColumn(columnId, {
      conditionalRules:
        safeArray(
          column.conditionalRules
        ).map((rule) =>
          rule.id === ruleId
            ? {
                ...rule,
                ...changes,
              }
            : rule
        ),
    });
  };

  const removeRule = (
    columnId,
    ruleId
  ) => {
    const column =
      columnConfigs.find(
        (item) =>
          item.id === columnId
      );

    if (!column) return;

    updateColumn(columnId, {
      conditionalRules:
        safeArray(
          column.conditionalRules
        ).filter(
          (rule) =>
            rule.id !== ruleId
        ),
    });
  };

  const resetColumnFormatting =
    () => {
      if (!selectedFormatColumn) {
        return;
      }

      updateColumn(
        selectedFormatColumn.id,
        normalizeColumn(
          selectedFormatColumn.sourceName,
          sourceRows
        )
      );

      setMessage(
        `Formatting reset for "${selectedFormatColumn.displayName}".`
      );
    };

  const exportAdvanced = async (format) => {
    if (hasUnsavedChanges) {
      resolveBeforeOutput(`export ${format.toUpperCase()}`, () => exportAdvancedNow(format));
      return;
    }
    await exportAdvancedNow(format);
  };

  const exportAdvancedNow = async (format) => {
    const jobId = result?.execution_job_id;
    if (!jobId) { setMessage("Re-run the report before exporting from the completed execution job."); return; }
    try {
      await runExecutionExportJob(jobId, format, slug(reportName), { onProgress: (job) => { if (job.progress != null) setMessage(`Preparing ${format.toUpperCase()} export: ${job.progress}% (${job.processed_rows || 0} rows)`); } });
      setExportOpen(false);
      setMessage(`${format.toUpperCase()} exported from the completed execution job.`);
    } catch (error) { setMessage(`${format.toUpperCase()} export failed: ${error.message}`); }
  };

  const exportCsv = () => {
    if (hasUnsavedChanges) {
      resolveBeforeOutput("export CSV", () => exportCsvNow());
      return;
    }
    exportCsvNow();
  };

  const exportCsvNow = async () => {
    const jobId = result?.execution_job_id;
    if (jobId) {
      try {
        await runExecutionExportJob(jobId, "csv", slug(reportName), { onProgress: (job) => { if (job.progress != null) setMessage(`Preparing CSV export: ${job.progress}% (${job.processed_rows || 0} rows)`); } });
        setExportOpen(false);
        setMessage("CSV exported from the completed execution job.");
      } catch (error) {
        setMessage(`CSV export failed: ${error.message}`);
      }
      return;
    }

    if (!displayedRows.length) {
      setMessage("There is no report data to export.");
      return;
    }

    const header = visibleColumns.map((column) => csvEscape(column.displayName)).join(",");
    const body = displayedRows.map((row) => visibleColumns.map((column) => csvEscape(formatCell(row?.[column.sourceName], column))).join(","));
    downloadFile(`\uFEFF${[header, ...body].join("\n")}`, "text/csv;charset=utf-8;", `${slug(reportName)}.csv`);
    setExportOpen(false);
    setMessage("CSV exported.");
  };

  const exportJson = () => {
    if (hasUnsavedChanges) {
      resolveBeforeOutput("export JSON", () => exportJsonNow());
      return;
    }
    exportJsonNow();
  };

  const exportJsonNow = async () => {
    const jobId = result?.execution_job_id;
    if (jobId) {
      try {
        await runExecutionExportJob(jobId, "json", slug(reportName), { onProgress: (job) => { if (job.progress != null) setMessage(`Preparing JSON export: ${job.progress}% (${job.processed_rows || 0} rows)`); } });
        setExportOpen(false);
        setMessage("JSON exported from the completed execution job.");
      } catch (error) {
        setMessage(`JSON export failed: ${error.message}`);
      }
      return;
    }

    if (!displayedRows.length) {
      setMessage("There is no report data to export.");
      return;
    }

    const output = {
      report_name: reportName || "Custom Report",
      exported_at: new Date().toISOString(),
      columns: visibleColumns.map((column) => ({ field: column.sourceName, name: column.displayName })),
      rows: displayedRows.map((row) => {
        const item = {};
        visibleColumns.forEach((column) => { item[column.displayName] = row?.[column.sourceName]; });
        return item;
      }),
    };
    downloadFile(JSON.stringify(output, null, 2), "application/json", `${slug(reportName)}.json`);
    setExportOpen(false);
    setMessage("JSON exported.");
  };

  const printReport = () => {
    resolveBeforeOutput("print the report", () => {
      setExportOpen(false);
      window.print();
    });
  };

  if (!initialResult || !sourceColumns.length) {
    return (
      <div className="rb-root">
        <style>{REPORT_BUILDER_CSS}</style>
        <div className="rb-page-heading"><div><span className="rb-eyebrow">REPORT BUILDER</span><h2>Build Your Report</h2><p>Configure the presentation and downloadable output of an executed reporting query.</p></div></div>
        <section className="rb-card"><div className="rb-empty"><div className="rb-empty-icon">▦</div><strong>No query result available</strong><span>First build a query in Join Designer and choose "Apply & Build Report". Report Builder does not create a new database connection.</span><div className="rb-button-row" style={{marginTop:14}}><button type="button" className="rb-btn primary" onClick={onBack}>Open Join Designer</button>{onOpenDataSources && <button type="button" className="rb-btn" onClick={onOpenDataSources}>Open Data Sources</button>}</div></div></section>
      </div>
    );
  }

  const chartData = safeArray(visualizationData?.data || visualizationData?.rows || visualizationData?.chart_data).length
    ? safeArray(visualizationData?.data || visualizationData?.rows || visualizationData?.chart_data).map((item) => ({
        label: item.label ?? item.category ?? item.name ?? item.x ?? "(Blank)",
        value: item.value ?? item.y ?? item.count ?? 0,
      }))
    : buildChartData(displayedRows, effectiveChartCategoryField, effectiveChartValueField, visualization);
  const chartMax = Math.max(1, ...chartData.map((item) => Math.abs(Number(item.value) || 0)));

  const renderChart = () => {
    if (visualization === "table" || visualization === "data-grid") {
      return <div className="rb-table-wrap">
        {visibleColumns.length === 0 ? <div className="rb-empty"><div className="rb-empty-icon">▦</div><strong>No visible columns</strong><span>Select a field in Report Columns to populate the report.</span></div> : displayedRows.length === 0 ? <div className="rb-empty"><div className="rb-empty-icon">⌕</div><strong>No matching rows</strong><span>Clear or change the current filter to see available records.</span></div> : <PagedVirtualizedTable className="rb-table-wrap" tableClassName="rb-table" rows={displayedRows} columns={visibleColumns} pageSize={500} viewportHeight={520} rowHeight={34} columnKey={(column) => column.id} rowKey={(_row, rowIndex) => `report_row_${rowIndex}`} renderHeader={(column) => <span style={{display:"block",width:column.width === "auto" ? undefined : column.width,textAlign:column.align}}>{column.displayName}</span>} renderCell={(row, column) => { const value=row?.[column.sourceName]; const conditional=conditionalStyle(value,column); return <span style={{display:"block",width:column.width === "auto" ? undefined : column.width,textAlign:column.align,color:conditional.color || column.textColor,backgroundColor:conditional.backgroundColor || column.backgroundColor,fontWeight:conditional.fontWeight || (column.bold ? 800 : 400),fontStyle:column.italic ? "italic" : "normal",whiteSpace:column.wrap ? "normal" : "nowrap",overflowWrap:column.wrap ? "anywhere" : undefined}}>{formatCell(value,column)}</span>; }} />}
      </div>;
    }

    if (!chartData.length) return <div className="rb-chart-empty"><div className="rb-empty-icon">▥</div><strong>No chart data available</strong><span>Choose a category field and a numeric value field with usable values.</span></div>;

    if (visualization === "pie") {
      const total=chartData.reduce((sum,item)=>sum+Math.abs(Number(item.value)||0),0)||1; let cursor=0;
      const stops=chartData.map((item,index)=>{const start=cursor;cursor+=(Math.abs(Number(item.value)||0)/total)*100;return `hsl(${(index*47)%360} 78% 55%) ${start}% ${cursor}%`;});
      return <div className="rb-chart-pie-layout"><div className="rb-pie" style={{background:`conic-gradient(${stops.join(",")})`}}><div className="rb-pie-hole">100%</div></div><div className="rb-chart-legend">{chartData.map((item,index)=><div className="rb-legend-item" key={`${item.label}_${index}`}><span className="rb-legend-dot" style={{background:`hsl(${(index*47)%360} 78% 55%)`}}/><span title={item.label}>{item.label}</span><strong>{safeText(item.value)}</strong></div>)}</div></div>;
    }

    const width=760,height=330,left=46,right=18,top=20,bottom=58,innerWidth=width-left-right,innerHeight=height-top-bottom,slot=innerWidth/Math.max(chartData.length,1);
    const points=chartData.map((item,index)=>{const x=left+slot*index+slot/2;const value=Number(item.value)||0;const y=top+innerHeight-(Math.abs(value)/chartMax)*innerHeight;return {...item,x,y,value};});
    return <div className="rb-chart-shell"><svg className="rb-chart-svg" viewBox={`0 0 ${width} ${height}`} role="img">{[0,.25,.5,.75,1].map((ratio)=>{const y=top+innerHeight-ratio*innerHeight;return <line key={ratio} x1={left} x2={width-right} y1={y} y2={y} stroke="#e2e8f0" strokeWidth="1"/>;})}{visualization === "line" && <polyline points={points.map((point)=>`${point.x},${point.y}`).join(" ")} fill="none" stroke="#2563eb" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round"/>}{points.map((point,index)=><g key={`${point.label}_${index}`}>{visualization === "bar" || visualization === "histogram" ? <rect x={point.x-Math.max(5,slot*.32)} y={point.y} width={Math.max(10,slot*.64)} height={Math.max(0,top+innerHeight-point.y)} rx="4" fill="#3b82f6"/> : <circle cx={point.x} cy={point.y} r="4.5" fill="#2563eb"/>}<text x={point.x} y={height-30} textAnchor="middle" fontSize="9" fill="#64748b">{safeText(point.label).slice(0,14)}</text><text x={point.x} y={Math.max(13,point.y-8)} textAnchor="middle" fontSize="9" fontWeight="700" fill="#334155">{Number(point.value).toLocaleString("en-IN",{maximumFractionDigits:2})}</text></g>)}</svg></div>;
  };

  const handleEditQuery = () => {
    if (!hasUnsavedChanges) {
      onBack?.();
      return;
    }

    const save = window.confirm(
      "You have unsaved report changes.\n\nPress OK to save the changes and return to Query Designer. Press Cancel to choose whether to discard them."
    );

    if (save) {
      if (selectedSavedReport) saveChanges();
      else saveNewReport();
      onBack?.();
      return;
    }

    if (window.confirm("Discard the unsaved report changes and return to Query Designer?")) {
      discardUnsavedChanges();
      onBack?.();
    }
  };

  const handleLoadReport = () => {
    if (hasUnsavedChanges && selectedSavedReport && !window.confirm("You have unsaved changes. Load the selected saved report and discard the current changes?")) return;
    loadReport();
  };

  const handleSavedReportSelectionChange = (nextId) => {
    if (nextId === selectedSavedReport) return;

    if (!hasUnsavedChanges) {
      setSelectedSavedReport(nextId);
      return;
    }

    const save = window.confirm(
      "You have unsaved report changes.\n\nPress OK to save the changes before changing the saved report selection. Press Cancel to choose whether to discard them."
    );

    if (save) {
      if (selectedSavedReport) saveChanges();
      else saveNewReport();
      setSelectedSavedReport(nextId);
      return;
    }

    if (window.confirm("Discard the unsaved report changes and change the saved report selection?")) {
      discardUnsavedChanges();
      setSelectedSavedReport(nextId);
    }
  };

  const resetUnsavedNewReport = () => {
    setReportName("Custom Report");
    setVisualization("table");
    setChartCategoryField("");
    setChartValueField("");
    setFilter({
      column: sourceColumns[0] || "",
      operator: "contains",
      value: "",
    });
    setFilterActive(false);
    setSort({
      column: sourceColumns[0] || "",
      direction: "asc",
    });
    setSortActive(false);
    setPreviewRows(sourceRows);
    setColumnConfigs(sourceColumns.map((name) => normalizeColumn(name, sourceRows)));
    setFormatColumnId("");
    setExportOpen(false);
  };

  const discardUnsavedChanges = () => {
    if (selectedSavedReport) {
      loadReport();
      return;
    }

    resetUnsavedNewReport();
    setMessage("Unsaved changes discarded.");
  };

  const resolveBeforeOutput = async (actionLabel, continueAction) => {
    if (!hasUnsavedChanges) {
      await continueAction();
      return;
    }

    const save = window.confirm(
      `You have unsaved report changes.\n\nPress OK to save the changes and continue to ${actionLabel}. Press Cancel to choose whether to discard them.`
    );

    if (save) {
      const saved = selectedSavedReport ? await saveChanges() : await saveNewReport();
      if (saved) await continueAction();
      return;
    }

    const discard = window.confirm(
      `Discard the unsaved report changes and continue to ${actionLabel}?`
    );

    if (discard) {
      discardUnsavedChanges();
      setMessage(`Unsaved changes discarded. Click ${actionLabel} again to continue.`);
    }
  };

  const saveReportAndOpenExports = async () => {
    const saved = selectedSavedReport ? await saveChanges() : await saveNewReport();
    if (saved) {
      setExportOpen(true);
      setMessage("Report saved. Choose CSV or JSON export.");
    }
  };

  const handleVisualizationChange = (value) => {
    setVisualization(value);
    setMessage(`View changed to ${value === "table" ? "Table" : value.replace("-"," ")}. Save the report to keep this change.`);
  };

  return (
    <div className="rb-root">
      <style>{REPORT_BUILDER_CSS}</style>
      <div className="rb-no-print">
        <header className="rb-page-heading"><div><span className="rb-eyebrow">REPORT BUILDER</span><h2>Build Your Report</h2><p>Configure the report identity, presentation, selected fields, formatting and final output from the executed query.</p></div>{hasUnsavedChanges && <span className="rb-dirty-badge">● Unsaved changes</span>}</header>

        <section className="rb-card">
          <div className="rb-card-header"><div><span className="rb-eyebrow">QUERY RESULT</span><h3>Reporting Dataset</h3><p>Result received from the Visual Query Designer. Report Builder only changes presentation; it does not modify the source database.</p></div><span className="rb-status-badge"><span className="rb-status-dot"/>Ready</span></div>
          <div className="rb-stats"><div className="rb-stat"><strong>{Number(result.total_rows ?? sourceRows.length).toLocaleString()}</strong><span>Matching Rows</span></div><div className="rb-stat"><strong>{Number(result.returned_rows ?? sourceRows.length).toLocaleString()}</strong><span>Rows Available</span></div><div className="rb-stat"><strong>{sourceColumns.length}</strong><span>Available Columns</span></div><div className="rb-stat"><strong>{safeArray(result.applied_joins).length}</strong><span>JOINs Applied</span></div></div>
        </section>

        <section className="rb-management rb-management-row">
          <section className="rb-panel"><div className="rb-panel-header"><span className="rb-eyebrow">SAVED REPORT CONFIG.</span><h3>Saved Report Config.</h3><p>Load or delete a stored report configuration.</p></div><div className="rb-panel-body"><div className="rb-field"><label>Saved Report</label><select value={selectedSavedReport} onChange={(event)=>handleSavedReportSelectionChange(event.target.value)}><option value="">Select saved report</option>{savedReports.map((report)=><option key={report.id} value={report.id}>{report.name}</option>)}</select></div><div className="rb-button-row rb-saved-actions"><button type="button" className="rb-btn" disabled={!selectedSavedReport} onClick={handleLoadReport}>Load</button><button type="button" className="rb-btn danger" disabled={!selectedSavedReport} onClick={deleteReport}>Delete</button></div></div></section>
          <section className="rb-panel"><div className="rb-panel-header"><span className="rb-eyebrow">REPORT IDENTITY</span><h3>Report Identity</h3><p>Name the report configuration before saving it.</p></div><div className="rb-panel-body"><div className="rb-field"><label>Report Name</label><input value={reportName} onChange={(event)=>setReportName(event.target.value)} placeholder="Enter report name"/></div><div className="rb-button-row rb-identity-actions"><button type="button" className="rb-btn primary" onClick={saveNewReport}>Save</button><button type="button" className="rb-btn" disabled={!selectedSavedReport} onClick={saveChanges}>Save Changes</button></div></div></section>
          <section className="rb-panel"><div className="rb-panel-header"><span className="rb-eyebrow">REPORT OUTPUT</span><h3>Report Output</h3><p>Save, print and export the current report.</p></div><div className="rb-panel-body"><div className="rb-output-buttons"><button type="button" className="rb-btn" onClick={handleEditQuery}>← Edit Query</button><button type="button" className="rb-btn" onClick={() => onOpenDashboard?.(result)}>Dashboard View</button><button type="button" className="rb-btn" onClick={printReport}>Print Report</button><button type="button" className="rb-btn primary" onClick={saveReportAndOpenExports}>Save Report</button></div>{exportOpen && <div className="rb-export-row"><button type="button" className="rb-btn" onClick={exportCsv}>Export CSV</button><button type="button" className="rb-btn" onClick={exportJson}>Export JSON</button><button type="button" className="rb-btn" onClick={() => exportAdvanced("xlsx")}>Export Excel</button><button type="button" className="rb-btn" onClick={() => exportAdvanced("pdf")}>Export PDF</button><button type="button" className="rb-btn" onClick={() => exportAdvanced("package")}>Download Package</button></div>}<div className={hasUnsavedChanges ? "rb-output-warning" : "rb-output-warning saved"}><strong>{hasUnsavedChanges ? "Unsaved changes" : "All changes saved"}</strong><span>{hasUnsavedChanges ? "To protect your work, save the changes or discard them before leaving, loading another configuration, printing or exporting this report." : "Your current report configuration is saved. You can continue editing; save again when you want to keep new changes."}</span>{hasUnsavedChanges && <div className="rb-button-row"><button type="button" className="rb-btn primary" onClick={()=>selectedSavedReport ? saveChanges() : saveNewReport()}>Save Changes</button><button type="button" className="rb-btn" onClick={discardUnsavedChanges}>Discard Changes</button></div>}</div></div></section>
        </section>

        <section className="rb-card rb-formatting-card rb-formatting-row"><div className="rb-card-header"><div><span className="rb-eyebrow">REPORT FORMATTING</span><h3>View & Formatting</h3><p>Choose whether the report is shown as a table, data grid, or chart. Chart views use the executed result already available in Report Builder.</p></div><span className="rb-format-state">{visualization === "table" ? "TABLE VIEW" : `${visualization.toUpperCase()} VIEW`}</span></div><div className="rb-format-body"><div className="rb-format-types">{["table","bar","pie","line","histogram","data-grid"].map((type)=><button key={type} type="button" className={`rb-view-button ${visualization === type ? "active" : ""}`} onClick={()=>handleVisualizationChange(type)}>{type === "table" ? "Table" : type === "data-grid" ? "Data Grid" : `${type.charAt(0).toUpperCase()}${type.slice(1)} Chart`}</button>)}</div>{visualization !== "table" && visualization !== "data-grid" && <><div className="rb-chart-fields"><div className="rb-field"><label>{visualization === "histogram" ? "Value Field" : "Category / Label Field"}</label><select value={visualization === "histogram" ? effectiveChartValueField : effectiveChartCategoryField} onChange={(event)=>visualization === "histogram" ? setChartValueField(event.target.value) : setChartCategoryField(event.target.value)}>{sourceColumns.map((column)=><option key={column} value={column}>{displayName(column)}</option>)}</select></div>{visualization !== "histogram" && <div className="rb-field"><label>Value Field</label><select value={effectiveChartValueField} onChange={(event)=>setChartValueField(event.target.value)}>{sourceColumns.map((column)=><option key={column} value={column}>{displayName(column)}</option>)}</select></div>}</div><div className="rb-chart-fields"><div className="rb-field"><label>Aggregation</label><select value={chartAggregation} onChange={(event)=>setChartAggregation(event.target.value)}><option value="SUM">Sum</option><option value="AVG">Average</option><option value="COUNT">Count</option><option value="MIN">Minimum</option><option value="MAX">Maximum</option></select></div><div className="rb-field"><label>Sort</label><select value={chartSortDirection} onChange={(event)=>setChartSortDirection(event.target.value)}><option value="DESC">Descending</option><option value="ASC">Ascending</option></select></div><div className="rb-field"><label>Limit</label><input type="number" min="1" max="500" value={chartLimit} onChange={(event)=>setChartLimit(Math.min(500,Math.max(1,Number(event.target.value)||1)))}/></div>{visualization === "histogram" && <div className="rb-field"><label>Bins</label><input type="number" min="1" max="100" value={chartBins} onChange={(event)=>setChartBins(Math.min(100,Math.max(1,Number(event.target.value)||1)))}/></div>}{visualizationLoading && <div className="rb-chart-backend-note">Refreshing chart from reporting engine…</div>}</div></>}</div></section>

        <div className="rb-workspace rb-report-workspace rb-workspace-row"><aside className="rb-sidebar">
          <section className="rb-side-card"><div className="rb-side-header"><div><span className="rb-eyebrow">FIELD MANAGEMENT</span><h3>Report Columns</h3><p>Select, reorder, rename, format or remove fields from the report only. Source database columns are never changed.</p></div><span className="rb-count">{selectedColumns.length}</span></div><div className="rb-side-body"><div className="rb-button-row" style={{marginBottom:8}}><button type="button" className="rb-btn" onClick={()=>setColumnConfigs((current)=>current.map((column)=>({...column,selected:true})))}>Select All</button><button type="button" className="rb-btn" onClick={()=>setColumnConfigs((current)=>current.map((column)=>({...column,selected:false})))}>Clear</button></div><div className="rb-column-list">{columnConfigs.map((column)=><div key={column.id} className={`rb-column-item ${draggingId===column.id?"dragging":""} ${dragOverId===column.id?"drag-over":""}`} draggable onDragStart={()=>setDraggingId(column.id)} onDragOver={(event)=>{event.preventDefault();setDragOverId(column.id)}} onDrop={()=>{moveColumn(draggingId,column.id);setDraggingId("");setDragOverId("")}} onDragEnd={()=>{setDraggingId("");setDragOverId("")}}><span className="rb-grip">⋮⋮</span><div className="rb-column-text"><strong>{column.displayName}</strong><small>{column.sourceName} · {column.dataType}</small></div><input className="rb-checkbox" type="checkbox" checked={column.selected} onChange={()=>updateColumn(column.id,{selected:!column.selected})}/><button type="button" className={column.visible?"rb-icon active":"rb-icon"} onClick={()=>updateColumn(column.id,{visible:!column.visible})}>{column.visible?"◉":"○"}</button><button type="button" className={formatColumnId===column.id?"rb-icon active":"rb-icon"} onClick={()=>setFormatColumnId(formatColumnId===column.id?"":column.id)} title="Edit column details">⚙</button><button type="button" className="rb-icon rb-remove-icon" onClick={()=>removeColumn(column.id)} title="Remove from report">×</button>{formatColumnId===column.id && <div className="rb-settings"><div className="rb-settings-title"><strong>Column Settings</strong><button type="button" className="rb-icon" onClick={()=>setFormatColumnId("")}>×</button></div><div className="rb-settings-grid"><div className="rb-field rb-full"><label>Display Name</label><input value={column.displayName} onChange={(event)=>updateColumn(column.id,{displayName:event.target.value})}/></div><div className="rb-field"><label>Width</label><select value={column.width} onChange={(event)=>updateColumn(column.id,{width:event.target.value})}><option value="auto">Automatic</option><option value="100px">100 px</option><option value="150px">150 px</option><option value="200px">200 px</option><option value="250px">250 px</option><option value="300px">300 px</option></select></div><div className="rb-field"><label>Alignment</label><select value={column.align} onChange={(event)=>updateColumn(column.id,{align:event.target.value})}><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></select></div><div className="rb-field"><label>Number Format</label><select value={column.numberFormat} onChange={(event)=>updateColumn(column.id,{numberFormat:event.target.value})}><option value="automatic">Automatic</option><option value="integer">Integer</option><option value="decimal">Decimal</option><option value="percentage">Percentage</option><option value="currency">Currency ₹</option></select></div><div className="rb-field"><label>Decimals</label><select value={column.decimals} onChange={(event)=>updateColumn(column.id,{decimals:Number(event.target.value)})}>{[0,1,2,3,4].map((value)=><option key={value} value={value}>{value}</option>)}</select></div><div className="rb-field"><label>NULL Display</label><input value={column.nullDisplay} onChange={(event)=>updateColumn(column.id,{nullDisplay:event.target.value})}/></div><div className="rb-check-row rb-full"><label className="rb-check-label"><input type="checkbox" checked={column.bold} onChange={(event)=>updateColumn(column.id,{bold:event.target.checked})}/>Bold</label><label className="rb-check-label"><input type="checkbox" checked={column.italic} onChange={(event)=>updateColumn(column.id,{italic:event.target.checked})}/>Italic</label><label className="rb-check-label"><input type="checkbox" checked={column.wrap} onChange={(event)=>updateColumn(column.id,{wrap:event.target.checked})}/>Wrap</label></div><div className="rb-field"><label>Text Color</label><input className="rb-color" type="color" value={column.textColor} onChange={(event)=>updateColumn(column.id,{textColor:event.target.value})}/></div><div className="rb-field"><label>Cell Background</label><input className="rb-color" type="color" value={column.backgroundColor} onChange={(event)=>updateColumn(column.id,{backgroundColor:event.target.value})}/></div><div className="rb-button-row rb-full"><button type="button" className="rb-btn" onClick={resetColumnFormatting}>Reset Formatting</button></div></div></div>}</div>)}</div></div></section>

          <section className="rb-side-card rb-conditional-card"><div className="rb-side-header"><div><span className="rb-eyebrow">CONDITIONAL FORMATTING</span><h3>Conditional Formatting</h3><p>Apply display rules to a report column without changing source data.</p></div></div><div className="rb-side-body"><div className="rb-field"><label>Column</label><select value={formatColumnId} onChange={(event)=>setFormatColumnId(event.target.value)}><option value="">Select column</option>{columnConfigs.filter((column)=>column.selected).map((column)=><option key={column.id} value={column.id}>{column.displayName}</option>)}</select></div>{selectedFormatColumn ? <><div className="rb-conditional-summary">{safeArray(selectedFormatColumn.conditionalRules).length} rule(s) configured.</div><button type="button" className="rb-btn primary" onClick={addConditionalRule}>+ Add Rule</button>{safeArray(selectedFormatColumn.conditionalRules).map((rule)=><div className="rb-rule" key={rule.id}><div className="rb-rule-grid"><div className="rb-field"><label>Condition</label><select value={rule.operator} onChange={(event)=>updateRule(selectedFormatColumn.id,rule.id,{operator:event.target.value})}><option value="equals">Equals</option><option value="not_equals">Not equals</option><option value="contains">Contains</option><option value="starts_with">Starts with</option><option value="ends_with">Ends with</option><option value="not_contains">Does not contain</option><option value="greater_than">Greater than</option><option value="less_than">Less than</option><option value="greater_equal">Greater / equal</option><option value="less_equal">Less / equal</option></select></div><div className="rb-field"><label>Value</label><input value={rule.value} onChange={(event)=>updateRule(selectedFormatColumn.id,rule.id,{value:event.target.value})} placeholder="Value"/></div><button type="button" className="rb-icon" onClick={()=>removeRule(selectedFormatColumn.id,rule.id)}>×</button></div><div className="rb-rule-options"><label className="rb-check-label">Text <input className="rb-color" type="color" value={rule.textColor || "#991b1b"} onChange={(event)=>updateRule(selectedFormatColumn.id,rule.id,{textColor:event.target.value})}/></label><label className="rb-check-label">Background <input className="rb-color" type="color" value={rule.backgroundColor || "#fee2e2"} onChange={(event)=>updateRule(selectedFormatColumn.id,rule.id,{backgroundColor:event.target.value})}/></label><label className="rb-check-label"><input type="checkbox" checked={Boolean(rule.bold)} onChange={(event)=>updateRule(selectedFormatColumn.id,rule.id,{bold:event.target.checked})}/>Bold</label></div></div>)}</> : <div className="rb-conditional-empty">Select a report column to configure conditional formatting.</div>}
</div></section>
        </aside>

        <section className="rb-preview-card"><div className="rb-preview-header"><div><span className="rb-eyebrow">CUSTOM REPORT</span><h3>{reportName || "Custom Report"}</h3><p>{visibleColumns.length} visible column(s) · {displayedRows.length.toLocaleString()} row(s)</p></div><div className="rb-preview-actions"><button type="button" className="rb-btn" onClick={()=>{const rows=filterActive?filterRows(sourceRows,filter):sourceRows;setPreviewRows(rows);setMessage("Report preview refreshed.")}}>↻ Refresh</button><button type="button" className="rb-btn" disabled={!selectedSavedReport} title={!selectedSavedReport ? "Save the report configuration first" : "Save current report progress"} onClick={()=>saveChanges()}>Save Progress</button></div></div>
          <div className="rb-filter"><div className="rb-field"><label>Filter Field</label><select value={filter.column} onChange={(event)=>setFilter((current)=>({...current,column:event.target.value}))}><option value="">Select field</option>{sourceColumns.map((column)=><option key={column} value={column}>{displayName(column)}</option>)}</select></div><div className="rb-field"><label>Operator</label><select value={filter.operator} onChange={(event)=>setFilter((current)=>({...current,operator:event.target.value}))}><option value="contains">Contains</option><option value="equals">Equals</option><option value="not_equals">Not equals</option><option value="starts_with">Starts with</option><option value="ends_with">Ends with</option><option value="greater_than">Greater than</option><option value="less_than">Less than</option><option value="greater_equal">Greater / equal</option><option value="less_equal">Less / equal</option></select></div><div className="rb-field"><label>Find Value</label><input value={filter.value} placeholder="Enter a value..." onChange={(event)=>setFilter((current)=>({...current,value:event.target.value}))} onKeyDown={(event)=>{if(event.key==="Enter")applyFilter()}}/></div><button type="button" className="rb-btn primary" onClick={applyFilter} disabled={operationLoading}>Apply Filter</button><button type="button" className="rb-btn" onClick={clearFilter}>Clear</button></div>
          <div className="rb-sortbar"><div className="rb-field"><label>Sort Field</label><select value={sort.column} onChange={(event)=>setSort((current)=>({...current,column:event.target.value}))}><option value="">Select field</option>{sourceColumns.map((column)=><option key={column} value={column}>{displayName(column)}</option>)}</select></div><div className="rb-field"><label>Direction</label><select value={sort.direction} onChange={(event)=>setSort((current)=>({...current,direction:event.target.value}))}><option value="asc">Ascending</option><option value="desc">Descending</option></select></div><button type="button" className="rb-btn primary" onClick={applySort} disabled={operationLoading}>Apply Sort</button><button type="button" className="rb-btn" onClick={clearSort}>Clear Sort</button></div>
          {filterActive && <div className="rb-filter-note">Preview filter is active. Only filtered rows are included in exports.</div>}
          <div className="rb-report-content">{renderChart()}</div>
          <div className="rb-preview-footer"><span>{filterActive?"Filtered preview":"Full query result"}</span><span>Showing <strong>{displayedRows.length.toLocaleString()}</strong> rows · <strong>{visibleColumns.length}</strong> columns</span></div>
        </section></div>
        {message && <div className="rb-message">{message}</div>}
      </div>

      <div className="rb-print-document"><h1 style={{margin:"0 0 14px",fontFamily:"Arial, sans-serif",fontSize:20,color:"#172033"}}>{reportName || "Custom Report"}</h1><table style={{width:"100%",borderCollapse:"collapse",fontFamily:"Arial, sans-serif"}}><thead><tr>{visibleColumns.map((column)=><th key={column.id} style={{border:"1px solid #dce4ee",padding:7,background:"#f8fafc",textAlign:column.align,fontSize:10}}>{column.displayName}</th>)}</tr></thead><tbody>{displayedRows.map((row,rowIndex)=><tr key={`print_${rowIndex}`}>{visibleColumns.map((column)=><td key={column.id} style={{border:"1px solid #dce4ee",padding:7,textAlign:column.align,fontSize:9}}>{formatCell(row?.[column.sourceName],column)}</td>)}</tr>)}</tbody></table></div>
    </div>
  );
}
