import { API, apiFetch } from "./authClient";
import { executeReportJob, fetchExecutionJobResultPage } from "./executionClient";
import { createResultWindowCache } from "./resultWindowCache";
import { VirtualizedTable } from "./VirtualizedTable.jsx";

import { getDefaultAggregation, getSemanticDatasetId, getSemanticFieldLabel } from "./semanticFieldAdapter.js";
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
.data-source-manager .primary,
.data-source-manager .secondary,
.data-source-manager .danger-outline{
  min-height:36px;
  box-sizing:border-box;
  font-size:10px;
}
.data-source-manager .primary{padding:0 13px}
`;

import { useEffect, useMemo, useRef, useState } from "react";
const JOIN_DESIGNER_CSS = COMPONENT_APP_CSS + `
.jdx-root {
          --jdx-border: #dfe5ee;
          --jdx-border-soft: #e9eef5;
          --jdx-text: #172033;
          --jdx-muted: #748197;
          --jdx-blue: #2563eb;
          --jdx-blue-soft: #eff6ff;
          --jdx-bg: #f7f9fc;
          --jdx-white: #ffffff;
          color: var(--jdx-text);
        }

        .jdx-root *,
        .jdx-root *::before,
        .jdx-root *::after {
          box-sizing: border-box;
        }

        .jdx-eyebrow {
          display: block;
          color: #8a96a8;
          font-size: 8px;
          font-weight: 800;
          letter-spacing: .08em;
          text-transform: uppercase;
        }

        .jdx-heading {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 12px;
        }

        .jdx-heading h2 {
          margin: 4px 0 4px;
          font-size: 20px;
          line-height: 1.2;
        }

        .jdx-heading p {
          margin: 0;
          max-width: 760px;
          color: var(--jdx-muted);
          font-size: 10px;
          line-height: 1.55;
        }

        .jdx-mode {
          flex: 0 0 auto;
          padding: 7px 9px;
          border: 1px solid #cfe0fb;
          border-radius: 7px;
          background: var(--jdx-blue-soft);
          color: var(--jdx-blue);
          font-size: 7px;
          font-weight: 850;
          letter-spacing: .07em;
        }

        .jdx-message {
          margin-bottom: 12px;
          padding: 9px 11px;
          border: 1px solid #cbdcf7;
          border-radius: 7px;
          background: #f6f9ff;
          color: #315b9d;
          font-size: 9px;
          line-height: 1.4;
        }

        .jdx-message.error {
          border-color: #f2c7c7;
          background: #fff7f7;
          color: #b42318;
        }

        .jdx-card {
          border: 1px solid var(--jdx-border);
          border-radius: 10px;
          background: var(--jdx-white);
          box-shadow: 0 2px 8px rgba(15, 23, 42, .025);
        }

        .jdx-actions {
          overflow: hidden;
          margin-bottom: 12px;
        }

        .jdx-actions-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          padding: 14px 16px;
          border-bottom: 1px solid var(--jdx-border-soft);
        }

        .jdx-actions-title h3,
        .jdx-panel-title h3,
        .jdx-canvas-title h3,
        .jdx-preview-title h3 {
          margin: 3px 0;
          font-size: 13px;
        }

        .jdx-actions-title p,
        .jdx-panel-title p,
        .jdx-canvas-title p,
        .jdx-preview-title p {
          margin: 0;
          color: var(--jdx-muted);
          font-size: 8px;
          line-height: 1.45;
        }

        .jdx-action-buttons {
          display: flex;
          align-items: center;
          gap: 7px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }

        .jdx-btn {
          min-height: 30px;
          padding: 0 10px;
          border-radius: 6px;
          border: 1px solid #d2dae6;
          background: #fff;
          color: #475569;
          font: inherit;
          font-size: 8px;
          font-weight: 750;
          cursor: pointer;
          white-space: nowrap;
        }

        .jdx-btn:hover:not(:disabled) {
          border-color: #aebed4;
          background: #f8fafc;
        }

        .jdx-btn:disabled {
          opacity: .48;
          cursor: not-allowed;
        }

        .jdx-btn.primary {
          border-color: var(--jdx-blue);
          background: var(--jdx-blue);
          color: #fff;
        }

        .jdx-btn.primary:hover:not(:disabled) {
          background: #1d4ed8;
        }

        .jdx-btn.ghost {
          border-color: transparent;
          background: transparent;
          color: var(--jdx-blue);
        }

        .jdx-btn.danger {
          color: #b42318;
        }

        .jdx-btn.small {
          min-height: 26px;
          padding: 0 8px;
          font-size: 7px;
        }

        .jdx-summary {
          display: grid;
          grid-template-columns: repeat(8, minmax(0, 1fr));
          border-bottom: 1px solid var(--jdx-border-soft);
        }

        .jdx-summary-item {
          min-width: 0;
          padding: 8px 7px;
          border-right: 1px solid var(--jdx-border-soft);
          text-align: center;
        }

        .jdx-summary-item:last-child {
          border-right: 0;
        }

        .jdx-summary-item strong {
          display: block;
          color: #334155;
          font-size: 12px;
        }

        .jdx-summary-item span {
          display: block;
          margin-top: 2px;
          color: #8b97a8;
          font-size: 6px;
          text-transform: uppercase;
          letter-spacing: .04em;
        }

        .jdx-action-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 9px 16px;
        }

        .jdx-limit {
          display: flex;
          align-items: center;
          gap: 7px;
          color: #667085;
          font-size: 8px;
          font-weight: 700;
        }

        .jdx-limit input {
          width: 75px;
          height: 28px;
          padding: 0 7px;
          border: 1px solid #d3dbe7;
          border-radius: 6px;
          font: inherit;
          font-size: 8px;
          color: #344054;
          outline: none;
        }

        .jdx-limit input:focus,
        .jdx-control select:focus,
        .jdx-control input:focus,
        .jdx-search:focus {
          border-color: #93b4ea;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, .07);
          outline: none;
        }

        .jdx-action-state {
          display: flex;
          align-items: center;
          gap: 6px;
          color: #8490a2;
          font-size: 7px;
        }

        .jdx-dot {
          width: 6px;
          height: 6px;
          border-radius: 999px;
          background: #22c55e;
          box-shadow: 0 0 0 3px #dcfce7;
        }

        .jdx-workspace {
          display: grid;
          grid-template-columns: minmax(270px, 315px) minmax(0, 1fr);
          gap: 12px;
          align-items: start;
        }

        .jdx-sidebar {
          min-width: 0;
          position: sticky;
          top: 10px;
        }

        .jdx-panel-title {
          padding: 2px 2px 8px;
        }

        .jdx-feature {
          margin-bottom: 7px;
          overflow: hidden;
        }

        .jdx-feature-header {
          width: 100%;
          min-height: 52px;
          display: grid;
          grid-template-columns: 29px minmax(0, 1fr) auto 14px;
          align-items: center;
          gap: 8px;
          padding: 8px 10px;
          border: 0;
          background: #fff;
          text-align: left;
          cursor: pointer;
        }

        .jdx-feature-header:hover {
          background: #fbfcfe;
        }

        .jdx-feature-icon {
          width: 27px;
          height: 27px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 7px;
          background: #f1f5ff;
          color: #2563eb;
          font-size: 9px;
          font-weight: 850;
        }

        .jdx-feature:nth-of-type(3) .jdx-feature-icon {
          background: #eff6ff;
        }

        .jdx-feature:nth-of-type(4) .jdx-feature-icon {
          background: #ecfeff;
          color: #0f766e;
        }

        .jdx-feature:nth-of-type(5) .jdx-feature-icon {
          background: #fffbeb;
          color: #b45309;
        }

        .jdx-feature-heading {
          min-width: 0;
          display: flex;
          flex-direction: column;
        }

        .jdx-feature-heading strong {
          color: #334155;
          font-size: 9px;
        }

        .jdx-feature-heading small {
          margin-top: 2px;
          color: #98a2b3;
          font-size: 7px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-count {
          min-width: 21px;
          height: 21px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0 5px;
          border-radius: 999px;
          background: #f3f5f8;
          color: #64748b;
          font-size: 7px;
          font-weight: 850;
        }

        .jdx-chevron {
          color: #64748b;
          font-size: 10px;
        }

        .jdx-feature-body {
          padding: 9px;
          border-top: 1px solid var(--jdx-border-soft);
          background: #fbfcfe;
        }

        .jdx-feature-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 7px;
          margin-bottom: 7px;
        }

        .jdx-feature-toolbar span {
          color: #8a96a8;
          font-size: 7px;
          line-height: 1.4;
        }

        .jdx-rule-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .jdx-rule {
          padding: 7px;
          border: 1px solid #dde4ed;
          border-radius: 7px;
          background: #fff;
        }

        .jdx-rule-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
          margin-bottom: 6px;
        }

        .jdx-rule-top span {
          color: #64748b;
          font-size: 7px;
          font-weight: 800;
        }

        .jdx-control {
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .jdx-control label {
          color: #667085;
          font-size: 6px;
          font-weight: 800;
          letter-spacing: .04em;
          text-transform: uppercase;
        }

        .jdx-control input,
        .jdx-control select {
          width: 100%;
          min-width: 0;
          height: 28px;
          padding: 0 7px;
          border: 1px solid #d5dde8;
          border-radius: 5px;
          background: #fff;
          color: #344054;
          font: inherit;
          font-size: 7px;
        }

        .jdx-filter-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 72px;
          gap: 5px;
        }

        .jdx-filter-row .jdx-value {
          grid-column: 1 / -1;
        }

        .jdx-inline-row {
          display: grid;
          grid-template-columns: 19px minmax(0, 1fr) 29px;
          gap: 5px;
          align-items: center;
        }

        .jdx-inline-row.aggregation {
          grid-template-columns: 19px minmax(0, 1fr) 78px 29px;
        }

        .jdx-index {
          width: 19px;
          height: 19px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 5px;
          background: #f1f5f9;
          color: #64748b;
          font-size: 6px;
          font-weight: 850;
        }

        .jdx-icon-button {
          width: 25px;
          height: 25px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 1px solid #dce3eb;
          border-radius: 5px;
          background: #fff;
          color: #64748b;
          cursor: pointer;
          font: inherit;
          font-size: 9px;
        }

        .jdx-icon-button:hover {
          border-color: #b9c6d7;
          color: #2563eb;
        }

        .jdx-icon-button.danger:hover {
          border-color: #efb4b4;
          color: #b42318;
        }

        .jdx-calculated-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 6px;
        }

        .jdx-canvas {
          min-width: 0;
        }

        .jdx-canvas-card {
          overflow: hidden;
        }

        .jdx-canvas-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 13px 15px;
          border-bottom: 1px solid var(--jdx-border-soft);
        }

        .jdx-canvas-stats {
          min-width: 57px;
          padding: 6px 8px;
          border: 1px solid #dce6f5;
          border-radius: 7px;
          background: #f8fbff;
          text-align: center;
        }

        .jdx-canvas-stats strong {
          display: block;
          color: #2563eb;
          font-size: 12px;
        }

        .jdx-canvas-stats span {
          color: #8290a4;
          font-size: 6px;
          text-transform: uppercase;
        }

        .jdx-datasets {
          display: flex;
          flex-direction: column;
          gap: 7px;
          max-height: 505px;
          overflow-y: auto;
          padding: 10px 12px;
          background: #f9fbfd;
          scrollbar-width: thin;
        }

        .jdx-dataset {
          overflow: hidden;
          border: 1px solid #dce4ee;
          border-radius: 8px;
          background: #fff;
        }

        .jdx-dataset.expanded {
          border-color: #b9cff1;
          box-shadow: 0 3px 10px rgba(37, 99, 235, .05);
        }

        .jdx-dataset-header {
          width: 100%;
          min-height: 53px;
          display: grid;
          grid-template-columns: 28px minmax(0, 1fr) auto 14px;
          align-items: center;
          gap: 8px;
          padding: 8px 10px;
          border: 0;
          background: #fff;
          text-align: left;
          cursor: pointer;
        }

        .jdx-dataset-header:hover {
          background: #fbfdff;
        }

        .jdx-dataset-number {
          width: 26px;
          height: 26px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 7px;
          background: #eef4ff;
          color: #2563eb;
          font-size: 8px;
          font-weight: 850;
        }

        .jdx-dataset-name {
          min-width: 0;
          display: flex;
          flex-direction: column;
        }

        .jdx-dataset-name strong {
          color: #334155;
          font-size: 9px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-dataset-name small {
          margin-top: 2px;
          color: #8c98a9;
          font-size: 6px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-dataset-meta {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          color: #94a3b8;
          font-size: 6px;
        }

        .jdx-dataset-meta b {
          margin-top: 2px;
          color: #64748b;
          font-size: 6px;
        }

        .jdx-dataset-body {
          padding: 8px 10px 10px;
          border-top: 1px solid var(--jdx-border-soft);
          background: #fbfcfe;
        }

        .jdx-dataset-tools {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 7px;
          margin-bottom: 7px;
        }

        .jdx-search {
          flex: 1;
          min-width: 0;
          height: 27px;
          padding: 0 7px;
          border: 1px solid #d5dde8;
          border-radius: 5px;
          color: #344054;
          font: inherit;
          font-size: 7px;
          outline: none;
        }

        .jdx-dataset-tool-links {
          display: flex;
          gap: 6px;
          flex-shrink: 0;
        }

        .jdx-link {
          border: 0;
          padding: 0;
          background: transparent;
          color: #2563eb;
          font: inherit;
          font-size: 7px;
          font-weight: 750;
          cursor: pointer;
        }

        .jdx-link:disabled {
          color: #aab4c2;
          cursor: not-allowed;
        }

        .jdx-fields {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 4px;
          max-height: 215px;
          overflow-y: auto;
          padding-right: 2px;
          scrollbar-width: thin;
        }

        .jdx-field {
          min-width: 0;
          min-height: 28px;
          display: flex;
          align-items: center;
          gap: 5px;
          padding: 4px 6px;
          border: 1px solid #dbe3ec;
          border-radius: 5px;
          background: #fff;
          color: #64748b;
          cursor: pointer;
          text-align: left;
        }

        .jdx-field:hover {
          border-color: #b5c8e6;
          background: #f8fbff;
        }

        .jdx-field.selected {
          border-color: #a5c1ed;
          background: #eff6ff;
          color: #1d4ed8;
        }

        .jdx-field-check {
          flex: 0 0 auto;
          width: 12px;
          height: 12px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 3px;
          font-size: 7px;
          font-weight: 900;
        }

        .jdx-field-name {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 7px;
        }

        .jdx-selected-note {
          margin-top: 6px;
          color: #7f8ca0;
          font-size: 6px;
        }

        .jdx-warning {
          margin: 0 12px 10px;
          padding: 7px 9px;
          border: 1px solid #f2dfaa;
          border-radius: 6px;
          background: #fffbeb;
          color: #92400e;
          font-size: 7px;
        }

        .jdx-join-area {
          margin: 10px 12px 12px;
          padding: 11px;
          border: 1px solid #dce4ee;
          border-radius: 8px;
          background: #fff;
        }

        .jdx-join-heading {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 10px;
          margin-bottom: 9px;
        }

        .jdx-join-heading h4 {
          margin: 3px 0;
          font-size: 10px;
        }

        .jdx-join-heading p {
          margin: 0;
          color: #8a96a8;
          font-size: 7px;
          line-height: 1.4;
        }

        .jdx-join-builder {
          display: grid;
          grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) 88px minmax(0, 1.1fr) minmax(0, 1fr);
          gap: 6px;
          align-items: end;
          padding: 9px;
          border: 1px solid #e4e9f0;
          border-radius: 7px;
          background: #f8fafc;
        }

        .jdx-join-builder .jdx-control span {
          color: #667085;
          font-size: 6px;
          font-weight: 800;
          text-transform: uppercase;
        }

        .jdx-join-builder select {
          width: 100%;
          height: 29px;
          margin-top: 3px;
          padding: 0 6px;
          border: 1px solid #d5dde8;
          border-radius: 5px;
          background: #fff;
          color: #344054;
          font: inherit;
          font-size: 7px;
          outline: none;
        }

        .jdx-join-actions {
          grid-column: 1 / -1;
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 7px;
          padding-top: 2px;
        }

        .jdx-pipeline {
          display: flex;
          flex-direction: column;
          gap: 5px;
          margin-top: 8px;
        }

        .jdx-pipeline-item {
          display: grid;
          grid-template-columns: 21px minmax(0, 1fr) auto minmax(0, 1fr) auto;
          align-items: center;
          gap: 7px;
          padding: 7px;
          border: 1px solid #e0e7ef;
          border-radius: 6px;
          background: #fbfcfe;
        }

        .jdx-pipeline-number {
          width: 20px;
          height: 20px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 5px;
          background: #eef4ff;
          color: #2563eb;
          font-size: 6px;
          font-weight: 850;
        }

        .jdx-pipeline-side {
          min-width: 0;
          display: flex;
          flex-direction: column;
        }

        .jdx-pipeline-side strong {
          color: #334155;
          font-size: 7px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-pipeline-side span {
          margin-top: 2px;
          color: #64748b;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 6px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-pipeline-type {
          padding: 3px 5px;
          border-radius: 4px;
          background: #eef2ff;
          color: #4338ca;
          font-size: 5px;
          font-weight: 850;
        }

        .jdx-pipeline-eq {
          color: #64748b;
          font-size: 9px;
          font-weight: 850;
        }

        .jdx-pipeline-actions {
          display: flex;
          gap: 3px;
        }

        .jdx-pipeline-actions button {
          width: 21px;
          height: 21px;
          border: 1px solid #d8e0ea;
          border-radius: 4px;
          background: #fff;
          color: #64748b;
          cursor: pointer;
          font-size: 7px;
        }

        .jdx-pipeline-actions button:disabled {
          opacity: .35;
          cursor: not-allowed;
        }

        .jdx-empty {
          padding: 17px 10px;
          border: 1px dashed #d5deea;
          border-radius: 7px;
          background: #fbfcfe;
          text-align: center;
        }

        .jdx-empty strong {
          display: block;
          color: #64748b;
          font-size: 8px;
        }

        .jdx-empty span {
          display: block;
          margin-top: 3px;
          color: #98a2b3;
          font-size: 7px;
        }

        .jdx-preview {
          margin-top: 12px;
          overflow: hidden;
        }

        .jdx-preview-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 12px 15px;
          border-bottom: 1px solid var(--jdx-border-soft);
        }

        .jdx-preview-meta {
          min-width: 62px;
          padding: 6px 8px;
          border: 1px solid #dce6f5;
          border-radius: 6px;
          background: #f8fbff;
          text-align: center;
        }

        .jdx-preview-meta strong {
          display: block;
          color: #2563eb;
          font-size: 11px;
        }

        .jdx-preview-meta span {
          color: #8290a4;
          font-size: 5px;
          text-transform: uppercase;
        }

        .jdx-result-wrap {
          max-height: 390px;
          overflow: auto;
        }

        .jdx-result-table {
          width: 100%;
          min-width: 700px;
          border-collapse: collapse;
        }

        .jdx-result-table th {
          position: sticky;
          top: 0;
          z-index: 2;
          padding: 8px 9px;
          border-bottom: 1px solid #dfe5ee;
          background: #f8fafc;
          color: #64748b;
          font-size: 6px;
          text-align: left;
          white-space: nowrap;
        }

        .jdx-result-table td {
          padding: 7px 9px;
          border-bottom: 1px solid #edf1f5;
          color: #475569;
          font-size: 7px;
          white-space: nowrap;
        }

        .jdx-result-table tbody tr:hover {
          background: #fbfdff;
        }

        .jdx-preview-empty {
          min-height: 150px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-direction: column;
          gap: 5px;
          padding: 15px;
          text-align: center;
        }

        .jdx-preview-empty-icon {
          width: 32px;
          height: 32px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 8px;
          background: #eef4ff;
          color: #2563eb;
          font-size: 15px;
        }

        .jdx-preview-empty strong {
          color: #475569;
          font-size: 8px;
        }

        .jdx-preview-empty span {
          color: #98a2b3;
          font-size: 7px;
        }

        @media (max-width: 1100px) {
          .jdx-workspace {
            grid-template-columns: 1fr;
          }

          .jdx-sidebar {
            position: static;
          }

          .jdx-join-builder {
            grid-template-columns: 1fr 1fr;
          }

          .jdx-join-actions {
            grid-column: 1 / -1;
          }

          .jdx-summary {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }
        }

        @media (max-width: 760px) {
          .jdx-heading,
          .jdx-actions-top,
          .jdx-action-footer,
          .jdx-canvas-header,
          .jdx-preview-header,
          .jdx-join-heading {
            flex-direction: column;
            align-items: stretch;
          }

          .jdx-action-buttons {
            justify-content: stretch;
          }

          .jdx-action-buttons .jdx-btn {
            flex: 1;
          }

          .jdx-summary {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .jdx-summary-item:nth-child(2n) {
            border-right: 0;
          }

          .jdx-join-builder {
            grid-template-columns: 1fr;
          }

          .jdx-join-actions {
            grid-column: auto;
          }

          .jdx-fields {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .jdx-calculated-grid {
            grid-template-columns: 1fr;
          }

          .jdx-inline-row.aggregation {
            grid-template-columns: 19px minmax(0, 1fr) 29px;
          }

          .jdx-inline-row.aggregation .jdx-control:nth-child(3) {
            grid-column: 2;
          }

          .jdx-pipeline-item {
            grid-template-columns: 21px minmax(0, 1fr) auto;
          }

          .jdx-pipeline-type,
          .jdx-pipeline-eq {
            display: none;
          }

          .jdx-pipeline-side:nth-of-type(4) {
            grid-column: 2 / -1;
          }

          .jdx-pipeline-actions {
            grid-column: 3;
            grid-row: 1;
          }
        }


        /* ============================================================
           ALIGNMENT / READABILITY FIX
           Keeps the existing component architecture and behaviour.
           ============================================================ */

        .jdx-root {
          width: 100%;
          font-size: 13px;
        }

        .jdx-root,
        .jdx-root * {
          box-sizing: border-box;
        }

        .jdx-workspace {
          width: 100%;
          grid-template-columns: minmax(300px, 330px) minmax(0, 1fr);
          gap: 16px;
          align-items: start;
        }

        .jdx-sidebar {
          width: 100%;
          min-width: 0;
        }

        .jdx-canvas {
          width: 100%;
          min-width: 0;
        }

        .jdx-canvas-card {
          width: 100%;
          overflow: visible;
        }

        .jdx-canvas-header {
          min-height: 82px;
          padding: 18px 20px;
          gap: 18px;
        }

        .jdx-canvas-title {
          min-width: 0;
        }

        .jdx-canvas-title h3 {
          font-size: 18px;
          line-height: 1.25;
          margin: 4px 0 6px;
        }

        .jdx-canvas-title p {
          font-size: 12px;
          line-height: 1.5;
        }

        .jdx-canvas-stats {
          min-width: 86px;
          padding: 10px 12px;
          flex: 0 0 auto;
        }

        .jdx-canvas-stats strong {
          font-size: 17px;
          line-height: 1.1;
        }

        .jdx-canvas-stats span {
          font-size: 9px;
          margin-top: 4px;
        }

        .jdx-datasets {
          width: 100%;
          max-height: 680px;
          overflow-y: auto;
          overflow-x: hidden;
          padding: 14px 16px;
          gap: 10px;
          background: #f8fafc;
        }

        .jdx-dataset {
          width: 100%;
          min-width: 0;
          overflow: visible;
          border-radius: 10px;
          background: #fff;
        }

        .jdx-dataset.expanded {
          border-color: #b9cff1;
          box-shadow: 0 3px 12px rgba(37, 99, 235, .07);
        }

        .jdx-dataset-header {
          width: 100%;
          min-height: 68px;
          display: grid;
          grid-template-columns: 38px minmax(0, 1fr) 110px 22px;
          align-items: center;
          gap: 12px;
          padding: 12px 16px;
          outline: none;
        }

        .jdx-dataset-header:focus {
          outline: none;
          box-shadow: none;
        }

        .jdx-dataset-header:focus-visible {
          box-shadow: inset 0 0 0 2px #93c5fd;
          border-radius: 9px;
        }

        .jdx-dataset-number {
          width: 36px;
          height: 36px;
          border-radius: 9px;
          font-size: 12px;
        }

        .jdx-dataset-name strong {
          font-size: 14px;
          line-height: 1.25;
          color: #1e293b;
        }

        .jdx-dataset-name small {
          margin-top: 4px;
          font-size: 10px;
          line-height: 1.3;
          color: #7b8798;
        }

        .jdx-dataset-meta {
          font-size: 10px;
          line-height: 1.25;
        }

        .jdx-dataset-meta b {
          margin-top: 4px;
          font-size: 10px;
          line-height: 1.25;
        }

        .jdx-chevron {
          width: 22px;
          text-align: center;
          font-size: 14px;
        }

        .jdx-dataset-body {
          width: 100%;
          padding: 14px 16px 16px;
          overflow: visible;
        }

        .jdx-dataset-tools {
          width: 100%;
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          align-items: center;
          gap: 12px;
          margin-bottom: 12px;
        }

        .jdx-search {
          width: 100%;
          height: 40px;
          padding: 0 12px;
          font-size: 12px;
          border-radius: 7px;
        }

        .jdx-dataset-tool-links {
          gap: 10px;
          align-items: center;
        }

        .jdx-link {
          font-size: 11px;
        }

        .jdx-fields {
          width: 100%;
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
          max-height: 260px;
          overflow-y: auto;
          overflow-x: hidden;
          padding: 2px 4px 2px 0;
          align-items: stretch;
        }

        .jdx-field {
          width: 100%;
          min-width: 0;
          min-height: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 0 10px;
          border-radius: 7px;
          font-size: 12px;
          line-height: 1.2;
        }

        .jdx-field-check {
          width: 16px;
          height: 16px;
          flex: 0 0 16px;
          font-size: 11px;
        }

        .jdx-field-name {
          min-width: 0;
          font-size: 12px;
          line-height: 1.2;
        }

        .jdx-selected-note {
          margin-top: 10px;
          font-size: 10px;
          line-height: 1.4;
        }

        .jdx-join-area {
          margin: 14px 16px 16px;
          padding: 16px;
          border-radius: 10px;
        }

        .jdx-join-heading h4 {
          font-size: 14px;
          line-height: 1.3;
        }

        .jdx-join-heading p {
          font-size: 11px;
        }

        .jdx-join-builder {
          grid-template-columns:
            minmax(0, 1.2fr)
            minmax(0, 1fr)
            110px
            minmax(0, 1.2fr)
            minmax(0, 1fr);
          gap: 10px;
          padding: 12px;
        }

        .jdx-join-builder .jdx-control span,
        .jdx-control label {
          font-size: 10px;
        }

        .jdx-control select,
        .jdx-control input {
          min-height: 38px;
          height: 38px;
          font-size: 11px;
        }

        .jdx-feature-header {
          min-height: 64px;
          padding: 12px 14px;
        }

        .jdx-feature-title strong {
          font-size: 13px;
        }

        .jdx-feature-title small {
          font-size: 10px;
        }

        .jdx-feature-icon {
          width: 30px;
          height: 30px;
          font-size: 12px;
        }

        .jdx-feature-count {
          font-size: 10px;
        }

        .jdx-feature-body {
          padding: 12px 14px;
        }

        .jdx-btn {
          min-height: 38px;
          padding: 0 13px;
          font-size: 11px;
        }

        .jdx-summary {
          grid-template-columns: repeat(8, minmax(0, 1fr));
        }

        .jdx-summary-item {
          min-height: 64px;
          padding: 10px 8px;
        }

        .jdx-summary-item strong {
          font-size: 16px;
        }

        .jdx-summary-item span {
          margin-top: 4px;
          font-size: 9px;
        }

        .jdx-preview-title h3 {
          font-size: 16px;
        }

        .jdx-preview-title p {
          font-size: 11px;
        }

        .jdx-preview-meta strong {
          font-size: 15px;
        }

        .jdx-preview-meta span {
          font-size: 9px;
        }

        .jdx-result-table th {
          padding: 10px 12px;
          font-size: 10px;
        }

        .jdx-result-table td {
          padding: 9px 12px;
          font-size: 11px;
        }

        @media (max-width: 1100px) {
          .jdx-workspace {
            grid-template-columns: 1fr;
          }

          .jdx-sidebar {
            position: static;
          }

          .jdx-fields {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .jdx-summary {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }
        }

        @media (max-width: 760px) {
          .jdx-canvas-header,
          .jdx-dataset-tools {
            grid-template-columns: 1fr;
            display: grid;
          }

          .jdx-canvas-header {
            align-items: stretch;
          }

          .jdx-canvas-stats {
            width: 100%;
          }

          .jdx-dataset-header {
            grid-template-columns: 34px minmax(0, 1fr) 72px 18px;
            gap: 8px;
            padding: 10px;
          }

          .jdx-dataset-number {
            width: 32px;
            height: 32px;
          }

          .jdx-fields {
            grid-template-columns: 1fr;
          }

          .jdx-summary {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
        /* ============================================================
           QUERY CONFIGURATION / APPLY-BUILD STATE
           ============================================================ */

        .jdx-config-management {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          align-items: center;
          gap: 16px;
          padding: 12px 16px;
          border-top: 1px solid var(--jdx-border-soft);
          background: #fbfcfe;
        }

        .jdx-config-info {
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .jdx-config-info strong {
          color: #334155;
          font-size: 11px;
        }

        .jdx-config-info small {
          color: #8490a2;
          font-size: 8px;
          line-height: 1.45;
        }

        .jdx-config-controls {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 7px;
          flex-wrap: wrap;
        }

        .jdx-config-name,
        .jdx-config-select {
          height: 32px;
          min-width: 165px;
          padding: 0 9px;
          border: 1px solid #d5dde8;
          border-radius: 6px;
          background: #fff;
          color: #344054;
          font: inherit;
          font-size: 8px;
        }

        .jdx-config-name:focus,
        .jdx-config-select:focus {
          border-color: #93b4ea;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, .07);
          outline: none;
        }

        .jdx-lock-scope {
          min-width: 0;
          margin: 0;
          padding: 0;
          border: 0;
        }

        .jdx-lock-scope:disabled {
          opacity: .88;
        }

        .jdx-dataset-section {
          width: 100%;
          margin-bottom: 12px;
          overflow: hidden;
        }

        .jdx-dataset-header-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 0 0 auto;
        }

        .jdx-dataset-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          padding: 12px 16px 16px;
          background: #f8fafc;
        }

        .jdx-dataset-row {
          overflow: hidden;
          border: 1px solid #dce4ee;
          border-radius: 9px;
          background: #fff;
        }

        .jdx-dataset-row.expanded {
          border-color: #b9cff1;
          box-shadow: 0 3px 12px rgba(37, 99, 235, .05);
        }

        .jdx-dataset-row-main {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          align-items: center;
          gap: 8px;
        }

        .jdx-dataset-row-toggle {
          width: 100%;
          min-width: 0;
          min-height: 64px;
          display: grid;
          grid-template-columns: 38px minmax(0, 1fr) 110px 22px;
          align-items: center;
          gap: 12px;
          padding: 10px 12px 10px 16px;
          border: 0;
          background: #fff;
          color: inherit;
          text-align: left;
          cursor: pointer;
        }

        .jdx-dataset-row-toggle:disabled {
          cursor: default;
        }

        .jdx-dataset-row-main > .jdx-btn {
          margin-right: 10px;
        }

        .jdx-dataset-section .jdx-dataset-body {
          padding: 12px 16px 15px;
          border-top: 1px solid var(--jdx-border-soft);
          background: #fbfcfe;
        }

        .jdx-dataset-section .jdx-fields {
          max-height: 230px;
        }

        .jdx-dataset-empty {
          margin: 12px 16px 16px;
        }

        .jdx-preview-header-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 0 0 auto;
        }

        /* ============================================================
           SAVED CONNECTION / TABLE BROWSER
           ============================================================ */

        .jdx-browser-backdrop {
          position: fixed;
          inset: 0;
          z-index: 2000;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          background: rgba(15, 23, 42, .42);
          backdrop-filter: blur(2px);
        }

        .jdx-browser-modal {
          width: min(1440px, 96vw);
          max-height: min(860px, 92vh);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          border: 1px solid #d8e0eb;
          border-radius: 14px;
          background: #fff;
          box-shadow: 0 24px 70px rgba(15, 23, 42, .22);
        }

        .jdx-browser-modal-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 18px;
          padding: 18px 20px;
          border-bottom: 1px solid #e6ebf2;
        }

        .jdx-browser-modal-header h3 {
          margin: 4px 0 5px;
          color: #0f172a;
          font-size: 18px;
        }

        .jdx-browser-modal-header p {
          max-width: 760px;
          margin: 0;
          color: #748197;
          font-size: 10px;
          line-height: 1.5;
        }

        .jdx-browser-modal-body {
          min-height: 0;
          flex: 1;
          display: grid;
          grid-template-columns: 1.05fr 1.05fr 1.35fr 1.05fr;
          overflow: hidden;
          background: #f8fafc;
        }

        .jdx-browser-pane {
          min-width: 0;
          min-height: 0;
          display: flex;
          flex-direction: column;
          border-right: 1px solid #e1e7ef;
          background: #fff;
        }

        .jdx-browser-pane:last-child {
          border-right: 0;
        }

        .jdx-browser-pane-head {
          min-height: 52px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          padding: 0 12px;
          border-bottom: 1px solid #e7ecf3;
          background: #fbfcfe;
        }

        .jdx-browser-pane-head span {
          color: #334155;
          font-size: 9px;
          font-weight: 800;
        }

        .jdx-browser-pane-head small {
          color: #98a2b3;
          font-size: 7px;
        }

        .jdx-browser-list {
          min-height: 0;
          flex: 1;
          overflow-y: auto;
          padding: 8px;
        }

        .jdx-browser-list-item {
          width: 100%;
          min-height: 52px;
          display: grid;
          grid-template-columns: 24px minmax(0, 1fr);
          align-items: center;
          gap: 8px;
          margin-bottom: 5px;
          padding: 7px 8px;
          border: 1px solid transparent;
          border-radius: 7px;
          background: #fff;
          color: #334155;
          text-align: left;
          cursor: pointer;
        }

        .jdx-browser-list-item:hover {
          border-color: #d7e3f4;
          background: #f8fbff;
        }

        .jdx-browser-list-item.active {
          border-color: #b8d0f5;
          background: #eef5ff;
          color: #1d4ed8;
        }

        .jdx-browser-item-icon {
          width: 22px;
          height: 22px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 6px;
          background: #f1f5f9;
          color: #64748b;
          font-size: 8px;
          font-weight: 800;
        }

        .jdx-browser-list-item.active .jdx-browser-item-icon {
          background: #dbeafe;
          color: #2563eb;
        }

        .jdx-browser-list-item span:last-child {
          min-width: 0;
          display: flex;
          flex-direction: column;
        }

        .jdx-browser-list-item strong {
          overflow: hidden;
          color: #334155;
          font-size: 9px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-browser-list-item small {
          margin-top: 3px;
          overflow: hidden;
          color: #98a2b3;
          font-size: 7px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-browser-toolbar {
          padding: 8px;
          border-bottom: 1px solid #e7ecf3;
        }

        .jdx-browser-toolbar .jdx-search {
          height: 34px;
          font-size: 9px;
        }

        .jdx-browser-current-path {
          margin: 2px 2px 8px;
          padding: 7px 8px;
          border-radius: 6px;
          background: #f8fafc;
          color: #64748b;
          font-size: 7px;
          font-weight: 700;
        }

        .jdx-browser-selected-object {
          display: flex;
          flex-direction: column;
          gap: 3px;
          padding: 12px;
          border-bottom: 1px solid #e7ecf3;
          background: #fbfcfe;
        }

        .jdx-browser-selected-object strong {
          overflow: hidden;
          color: #1e293b;
          font-size: 11px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-browser-selected-object small {
          color: #8a96a8;
          font-size: 8px;
        }

        .jdx-browser-columns-list {
          min-height: 0;
          flex: 1;
          overflow-y: auto;
          padding: 8px;
        }

        .jdx-browser-column {
          display: flex;
          align-items: center;
          gap: 7px;
          min-height: 31px;
          padding: 0 8px;
          border-bottom: 1px solid #f0f3f7;
        }

        .jdx-browser-column span {
          color: #16a34a;
          font-size: 8px;
        }

        .jdx-browser-column strong {
          overflow: hidden;
          color: #475569;
          font-size: 8px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-browser-empty {
          padding: 20px 12px;
          color: #98a2b3;
          font-size: 8px;
          line-height: 1.5;
          text-align: center;
        }

        .jdx-browser-message {
          margin: 10px 12px 0;
          padding: 8px 10px;
          border: 1px solid #bfdbfe;
          border-radius: 6px;
          background: #eff6ff;
          color: #1d4ed8;
          font-size: 8px;
        }

        .jdx-browser-message.error {
          border-color: #fecaca;
          background: #fff1f2;
          color: #b91c1c;
        }

        .jdx-browser-modal-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 11px 14px;
          border-top: 1px solid #e2e8f0;
          background: #fff;
        }

        .jdx-browser-modal-footer > span {
          color: #748197;
          font-size: 8px;
        }

        @media (max-width: 1100px) {
          .jdx-browser-modal-body {
            grid-template-columns: 1fr 1fr;
            overflow-y: auto;
          }

          .jdx-browser-pane {
            min-height: 260px;
          }

          .jdx-browser-pane:nth-child(2) {
            border-right: 0;
          }

          .jdx-browser-pane:nth-child(-n+2) {
            border-bottom: 1px solid #e1e7ef;
          }

          .jdx-config-management {
            grid-template-columns: 1fr;
          }

          .jdx-config-controls {
            justify-content: flex-start;
          }
        }

        @media (max-width: 760px) {
          .jdx-dataset-row-main {
            grid-template-columns: 1fr;
          }

          .jdx-dataset-row-main > .jdx-btn {
            margin: 0 10px 10px;
          }

          .jdx-dataset-row-toggle {
            grid-template-columns: 34px minmax(0, 1fr) 74px 18px;
            gap: 8px;
            padding: 9px 10px;
          }

          .jdx-dataset-header-actions {
            width: 100%;
            justify-content: stretch;
          }

          .jdx-dataset-header-actions .jdx-btn {
            flex: 1;
          }

          .jdx-browser-backdrop {
            padding: 8px;
          }

          .jdx-browser-modal {
            width: 100%;
            max-height: 96vh;
          }

          .jdx-browser-modal-body {
            grid-template-columns: 1fr;
          }

          .jdx-browser-pane {
            min-height: 220px;
            border-right: 0;
            border-bottom: 1px solid #e1e7ef;
          }

          .jdx-browser-modal-footer {
            align-items: stretch;
            flex-direction: column;
          }

          .jdx-config-controls {
            display: grid;
            grid-template-columns: 1fr 1fr;
          }

          .jdx-config-name,
          .jdx-config-select {
            min-width: 0;
            width: 100%;
          }
        }

        /* ============================================================
           CONNECT DATASETS — REPORTING DATASET LIST
           Existing Data Source datasets remain the baseline. The list
           is intentionally compact; editing/adding opens the browser.
           ============================================================ */

        .jdx-connect-datasets-section {
          overflow: hidden;
        }

        .jdx-connect-datasets-header {
          min-height: 76px;
          padding: 14px 16px 12px;
          align-items: center;
        }

        .jdx-connect-datasets-header-actions {
          display: flex;
          align-items: center;
          gap: 12px;
          flex: 0 0 auto;
        }

        .jdx-connect-dataset-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          padding: 12px 16px 16px;
          background: #f8fafc;
        }

        .jdx-connect-dataset-row {
          overflow: hidden;
          border: 1px solid #dce4ee;
          border-radius: 9px;
          background: #fff;
          transition: border-color .15s ease, box-shadow .15s ease;
        }

        .jdx-connect-dataset-row.expanded {
          border-color: #b9cff1;
          box-shadow: 0 3px 12px rgba(37, 99, 235, .05);
        }

        .jdx-connect-dataset-row-head {
          display: flex;
          align-items: stretch;
          gap: 8px;
          min-width: 0;
        }

        .jdx-connect-dataset-row-toggle {
          flex: 1 1 auto;
          min-width: 0;
          min-height: 64px;
          display: grid;
          grid-template-columns: 34px minmax(0, 1fr) auto 18px;
          align-items: center;
          gap: 10px;
          padding: 9px 10px 9px 12px;
          border: 0;
          background: #fff;
          color: inherit;
          text-align: left;
          cursor: pointer;
          font: inherit;
        }

        .jdx-connect-dataset-row.expanded .jdx-connect-dataset-row-toggle {
          background: #fbfdff;
          border-bottom: 1px solid #e4eaf2;
        }

        .jdx-connect-dataset-row-toggle:disabled {
          cursor: default;
        }

        .jdx-connect-dataset-modify {
          align-self: center;
          flex: 0 0 auto;
          margin-right: 10px;
        }

        .jdx-connect-dataset-index {
          width: 30px;
          height: 30px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 7px;
          background: #eef4ff;
          color: #2457bd;
          font-size: 10px;
          font-weight: 800;
        }

        .jdx-connect-dataset-info {
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .jdx-connect-dataset-info strong {
          overflow: hidden;
          color: #10213a;
          font-size: 11px;
          font-weight: 800;
          line-height: 1.25;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-connect-dataset-info small {
          overflow: hidden;
          color: #718096;
          font-size: 8px;
          line-height: 1.35;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-connect-dataset-status {
          min-width: 58px;
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 2px;
        }

        .jdx-connect-dataset-status b {
          color: #2457bd;
          font-size: 10px;
          line-height: 1;
        }

        .jdx-connect-dataset-status span {
          color: #8491a5;
          font-size: 7px;
          text-transform: uppercase;
          letter-spacing: .04em;
        }

        .jdx-connect-dataset-body {
          padding: 10px 12px 12px;
          background: #fbfcfe;
        }

        .jdx-connect-dataset-meta {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 9px;
        }

        .jdx-connect-dataset-meta > div:first-child {
          min-width: 0;
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
        }

        .jdx-connect-dataset-meta > div:first-child span {
          padding: 4px 7px;
          border: 1px solid #e0e7f0;
          border-radius: 5px;
          background: #fff;
          color: #64748b;
          font-size: 7px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .03em;
        }

        .jdx-connect-dataset-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          margin-bottom: 8px;
        }

        .jdx-connect-dataset-toolbar .jdx-search {
          width: min(320px, 100%);
          height: 32px;
        }

        .jdx-connect-dataset-toolbar > span {
          flex: 0 0 auto;
          color: #718096;
          font-size: 8px;
        }

        .jdx-connect-dataset-fields {
          max-height: 260px;
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
          overflow-y: auto;
          padding: 2px;
        }

        /* Output field selector — intentionally styled as a quiet list of
           selectable rows rather than browser-default buttons. */
        .jdx-connect-field {
          width: 100%;
          min-width: 0;
          min-height: 38px;
          display: flex;
          align-items: center;
          gap: 9px;
          padding: 7px 10px;
          border: 1px solid #dbe3ed;
          border-radius: 7px;
          background: #fff;
          color: #334155;
          text-align: left;
          cursor: pointer;
          font: inherit;
          transition: border-color .15s ease, background .15s ease, box-shadow .15s ease;
        }

        .jdx-connect-field:hover:not(:disabled) {
          border-color: #b9cbe3;
          background: #f8fbff;
        }

        .jdx-connect-field.selected {
          border-color: #9dbcf0;
          background: #eef5ff;
          box-shadow: inset 0 0 0 1px rgba(37, 99, 235, .05);
        }

        .jdx-connect-field:disabled {
          cursor: default;
          opacity: 1;
        }

        .jdx-connect-field-check {
          width: 18px;
          height: 18px;
          flex: 0 0 18px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          background: #fff;
          color: transparent;
          font-size: 11px;
          font-weight: 900;
          line-height: 1;
        }

        .jdx-connect-field.selected .jdx-connect-field-check {
          border-color: #2563eb;
          background: #2563eb;
          color: #fff;
        }

        .jdx-connect-field-name {
          min-width: 0;
          overflow: hidden;
          color: #475569;
          font-size: 9px;
          font-weight: 600;
          line-height: 1.3;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .jdx-connect-field.selected .jdx-connect-field-name {
          color: #1d4ed8;
          font-weight: 700;
        }

        .jdx-connect-dataset-body {
          padding: 12px 14px 14px;
          background: #f8fafc;
        }

        .jdx-connect-dataset-meta {
          margin-bottom: 10px;
          padding: 2px 0;
        }

        .jdx-connect-dataset-toolbar {
          margin-bottom: 10px;
          padding: 8px 9px;
          border: 1px solid #e1e8f1;
          border-radius: 8px;
          background: #fff;
        }

        .jdx-connect-dataset-toolbar .jdx-search {
          height: 34px;
          border-color: #d6e0ec;
          background: #fbfdff;
        }

        .jdx-selected-note {
          margin-top: 9px;
          padding: 7px 9px;
          border-top: 1px solid #e1e8f1;
          color: #718096;
          font-size: 8px;
          line-height: 1.4;
        }

        .jdx-connect-datasets-limit-note {
          padding: 0 16px 12px;
          color: #7b8798;
          font-size: 8px;
          text-align: right;
        }

        /* Dataset browser polish — keeps the existing two-pane structure but
           gives each navigation level and selectable field a consistent surface. */
        .jdx-browser-modal {
          width: min(1280px, 96vw);
          max-height: min(820px, 90vh);
          border-color: #d7e0eb;
          border-radius: 16px;
          box-shadow: 0 28px 80px rgba(15, 23, 42, .24);
        }

        .jdx-browser-modal-header {
          padding: 18px 20px 16px;
          background: #fff;
        }

        .jdx-browser-modal-body {
          grid-template-columns: 280px minmax(0, 1fr);
          background: #f5f8fc;
        }

        .jdx-browser-tree-pane {
          background: #f8fafc;
        }

        .jdx-browser-pane-head {
          min-height: 48px;
          padding: 0 13px;
          background: #fff;
        }

        .jdx-browser-tree {
          padding: 10px;
          background: #f8fafc;
        }

        .jdx-tree-connection {
          margin-bottom: 6px;
          padding-bottom: 4px;
        }

        .jdx-tree-row {
          min-height: 40px;
          border-color: transparent;
          background: transparent;
        }

        .jdx-tree-row:hover {
          background: #fff;
          border-color: #e0e7f0;
        }

        .jdx-tree-row.active {
          background: #eef5ff;
          border-color: #c7daf5;
        }

        .jdx-tree-children {
          margin-left: 13px;
          padding-left: 12px;
          border-left-color: #dbe3ed;
        }

        .jdx-browser-main-pane {
          background: #fff;
        }

        .jdx-browser-main-toolbar {
          padding: 11px 14px;
          background: #fff;
        }

        .jdx-browser-table-area {
          min-height: 190px;
          max-height: 300px;
          padding: 12px 14px;
          background: #f8fafc;
        }

        .jdx-browser-object-grid {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .jdx-browser-object-card {
          min-height: 46px;
          padding: 7px 10px;
          border-color: #dce4ee;
          border-radius: 7px;
          background: #fff;
        }

        .jdx-browser-object-card:hover {
          border-color: #b9cbe3;
          background: #fbfdff;
        }

        .jdx-browser-object-card.active {
          border-color: #9dbcf0;
          background: #eef5ff;
          box-shadow: inset 3px 0 0 #2563eb;
        }

        .jdx-browser-columns-panel {
          background: #fff;
        }

        .jdx-browser-columns-head {
          padding: 11px 14px;
          background: #fff;
        }

        .jdx-browser-select-columns {
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 7px;
          max-height: 180px;
          padding: 10px 12px 12px;
          background: #f8fafc;
        }

        .jdx-browser-select-column {
          min-height: 36px;
          padding: 6px 8px;
          border-color: #dbe3ed;
          border-radius: 7px;
          background: #fff;
        }

        .jdx-browser-select-column:hover {
          border-color: #b9cbe3;
          background: #fbfdff;
        }

        .jdx-browser-select-column.selected {
          border-color: #9dbcf0;
          background: #eef5ff;
        }

        .jdx-browser-select-column input {
          width: 15px;
          height: 15px;
          flex: 0 0 15px;
          margin: 0;
        }

        .jdx-browser-select-column span {
          font-size: 8px;
        }

        .jdx-browser-modal-footer {
          min-height: 58px;
          padding: 10px 14px;
          background: #fff;
        }


        @media (max-width: 900px) {
          .jdx-connect-dataset-list {
            padding-left: 12px;
            padding-right: 12px;
          }

          .jdx-connect-dataset-fields {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }

        @media (max-width: 600px) {
          .jdx-connect-dataset-row-toggle {
            grid-template-columns: 32px minmax(0, 1fr) 18px;
          }

          .jdx-connect-dataset-status {
            display: none;
          }

          .jdx-connect-dataset-modify {
            margin-right: 8px;
          }

          .jdx-connect-dataset-meta,
          .jdx-connect-dataset-toolbar {
            align-items: stretch;
            flex-direction: column;
          }

          .jdx-connect-dataset-toolbar .jdx-search {
            width: 100%;
          }

          .jdx-connect-dataset-fields {
            grid-template-columns: 1fr;
          }
        }



        /* ============================================================
           CONNECT DATA SET — FINAL SIDEBAR CONTROL FIX
           The generic JOIN builder uses five narrow grid tracks. Connect Data
           Set has a nested field grid, so the outer builder must be a full-width
           block and the inner grid must own the five controls.
           ============================================================ */
        .jdx-sidebar .jdx-feature .jdx-connect-join-builder {
          display: block !important;
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
          grid-template-columns: none !important;
          grid-template-areas: none !important;
          box-sizing: border-box !important;
          overflow: visible !important;
        }

        .jdx-sidebar .jdx-feature .jdx-connect-join-builder .jdx-join-fields-grid {
          display: grid !important;
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
          grid-template-areas:
            "dataset-a field-a"
            "join-type join-type"
            "dataset-b field-b" !important;
          gap: 10px !important;
          box-sizing: border-box !important;
        }

        .jdx-sidebar .jdx-feature .jdx-connect-join-builder .jdx-connect-control {
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
          display: flex !important;
          flex-direction: column !important;
          box-sizing: border-box !important;
        }

        .jdx-sidebar .jdx-feature .jdx-connect-join-builder .jdx-connect-control select {
          display: block !important;
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
          height: 40px !important;
          min-height: 40px !important;
          box-sizing: border-box !important;
        }

        .jdx-sidebar .jdx-feature-body .jdx-sort-row {
          display: grid !important;
          grid-template-columns: 28px minmax(0, 1fr) 82px 40px !important;
          gap: 8px !important;
          align-items: center !important;
          width: 100% !important;
          min-width: 0 !important;
          box-sizing: border-box !important;
        }

        .jdx-sidebar .jdx-feature-body .jdx-sort-row select {
          display: block !important;
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
          height: 40px !important;
          min-height: 40px !important;
          box-sizing: border-box !important;
        }

        .jdx-sidebar .jdx-feature-body .jdx-sort-row .jdx-icon-button {
          width: 40px !important;
          min-width: 40px !important;
          height: 40px !important;
          min-height: 40px !important;
          box-sizing: border-box !important;
        }

        /* ============================================================
           FINAL REQUESTED JOIN DESIGNER FIXES
           Only the requested Query Features / dataset selector / preview
           surfaces are adjusted here. Feature order and behavior stay intact.
           ============================================================ */

        /* 2 + 3 — widen Query Features and align its heading with the
           Select Dataset card. The existing responsive breakpoint remains. */
        .jdx-workspace {
          grid-template-columns: 420px minmax(0, 1fr) !important;
          gap: 14px !important;
        }

        .jdx-sidebar {
          padding-top: 17px !important;
        }

        /* 4 — use the same field-control surface as Connect Data Set. */
        .jdx-sidebar .jdx-feature-body .jdx-groupby-row select,
        .jdx-sidebar .jdx-feature-body .jdx-aggregation-row select,
        .jdx-sidebar .jdx-feature-body .jdx-sort-row select {
          display: block !important;
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
          height: 42px !important;
          min-height: 42px !important;
          margin: 0 !important;
          padding: 0 32px 0 12px !important;
          border: 1px solid #cbd8e8 !important;
          border-radius: 8px !important;
          background: #ffffff !important;
          background-image: none !important;
          color: #172033 !important;
          font-family: inherit !important;
          font-size: 10px !important;
          font-weight: 500 !important;
          line-height: 42px !important;
          appearance: auto !important;
          -webkit-appearance: auto !important;
          outline: none !important;
          box-shadow: none !important;
          overflow: hidden !important;
          text-overflow: ellipsis !important;
          white-space: nowrap !important;
          box-sizing: border-box !important;
        }

        .jdx-sidebar .jdx-feature-body .jdx-groupby-row select:hover,
        .jdx-sidebar .jdx-feature-body .jdx-aggregation-row select:hover,
        .jdx-sidebar .jdx-feature-body .jdx-sort-row select:hover {
          border-color: #b5c8e6 !important;
          background: #ffffff !important;
        }

        .jdx-sidebar .jdx-feature-body .jdx-groupby-row select:focus,
        .jdx-sidebar .jdx-feature-body .jdx-aggregation-row select:focus,
        .jdx-sidebar .jdx-feature-body .jdx-sort-row select:focus {
          border-color: #93b4ea !important;
          background: #ffffff !important;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, .07) !important;
        }

        .jdx-sidebar .jdx-feature-body .jdx-groupby-row select:disabled,
        .jdx-sidebar .jdx-feature-body .jdx-aggregation-row select:disabled,
        .jdx-sidebar .jdx-feature-body .jdx-sort-row select:disabled {
          background: #f8fafc !important;
          color: #94a3b8 !important;
          border-color: #dbe3ec !important;
          opacity: 1 !important;
        }

        @media (max-width: 1100px) {
          .jdx-workspace {
            grid-template-columns: 1fr !important;
          }

          .jdx-sidebar {
            padding-top: 0 !important;
          }
        }


`;

const MAX_VISIBLE_DATASETS = 10;

function getColumnName(column) {
  if (typeof column === "string") return column;
  return column?.name || column?.field || column?.column_name || "";
}

function getDatasetObjectName(dataset) {
  return (
    dataset?.object_name ||
    dataset?.objectName ||
    dataset?.table ||
    dataset?.collection ||
    dataset?.name ||
    "Dataset"
  );
}

function getDatasetSourceType(dataset) {
  return dataset?.sourceType || dataset?.source_type || "";
}

function getDatasetDatabase(dataset) {
  return dataset?.database || dataset?.schema || "";
}

function getDatasetConnectionId(dataset) {
  return dataset?.connectionId || dataset?.connection_id || "";
}

function getDatasetLabel(dataset) {
  if (!dataset) return "Dataset";

  const source = String(
    dataset.sourceType || dataset.source_type || ""
  ).toUpperCase();

  return `${source} → ${dataset.database || ""} → ${getDatasetObjectName(
    dataset
  )}`;
}

function getDatasetShortName(dataset) {
  return getDatasetObjectName(dataset);
}

function getResultCellValue(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function createId(prefix, index = 0) {
  return `${prefix}_${Date.now()}_${index}_${Math.random()
    .toString(36)
    .slice(2, 7)}`;
}

export default function JoinDesigner({ datasets = [], onReportResult, onDatasetsChange }) {
  const [joins, setJoins] = useState([]);
  const [limit, setLimit] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState(null);
  const [previewPage, setPreviewPage] = useState(0);
  const [previewPageLoading, setPreviewPageLoading] = useState(false);
  const resultWindowCacheRef = useRef(null);
  if (resultWindowCacheRef.current == null) resultWindowCacheRef.current = createResultWindowCache({ maxWindows: 8 });
  const previewRequestRef = useRef({ sequence: 0, controller: null });

  const cancelPreviewRequest = () => {
    previewRequestRef.current.controller?.abort();
    previewRequestRef.current.controller = null;
    previewRequestRef.current.sequence += 1;
  };

  useEffect(() => () => {
    previewRequestRef.current.controller?.abort();
    previewRequestRef.current.controller = null;
  }, []);
  const [savedConnections, setSavedConnections] = useState([]);
  const [connectionsLoading, setConnectionsLoading] = useState(false);

  const [leftDataset, setLeftDataset] = useState("");
  const [rightDataset, setRightDataset] = useState("");
  const [leftColumn, setLeftColumn] = useState("");
  const [rightColumn, setRightColumn] = useState("");
  const [editingJoinId, setEditingJoinId] = useState("");
  const [joinType, setJoinType] = useState("INNER");

  const [selectedFields, setSelectedFields] = useState({});
  const [filters, setFilters] = useState([]);
  const [sorts, setSorts] = useState([]);
  const [groupBy, setGroupBy] = useState([]);
  const [aggregations, setAggregations] = useState([]);
  const [calculatedColumns, setCalculatedColumns] = useState([]);

  const [draggedField, setDraggedField] = useState(null);
  const [expandedDatasets, setExpandedDatasets] = useState({});
  const [datasetSearch, setDatasetSearch] = useState({});
  const [collapsedFeatures, setCollapsedFeatures] = useState({
    filters: true,
    grouping: true,
    aggregation: true,
    calculated: true,
    sorting: true,
  });

  // ------------------------------------------------------------
  // Applied query / configuration state
  // Apply creates an immutable execution snapshot. Build can only
  // consume that snapshot; it never builds from an un-applied draft.
  // ------------------------------------------------------------
  const [configurationLocked, setConfigurationLocked] = useState(false);
  const [appliedConfiguration, setAppliedConfiguration] = useState(null);
  const [savedConfigurations, setSavedConfigurations] = useState([]);
  const [selectedSavedConfigurationId, setSelectedSavedConfigurationId] = useState("");
  const [configurationName, setConfigurationName] = useState("");


  useEffect(() => {
    let active = true;

    const loadReportingDatasets = async () => {
      try {
        const response = await apiFetch(`${API}/datasets`, {
          headers: { Accept: "application/json" },
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          throw new Error(
            data.message ||
              data.detail ||
              `Unable to load reporting datasets (HTTP ${response.status}).`
          );
        }

        if (active && onDatasetsChange) {
          onDatasetsChange(
            Array.isArray(data.datasets) ? data.datasets : []
          );
        }
      } catch (error) {
        console.error(
          "Unable to synchronize reporting datasets for Join Designer:",
          error
        );
      }
    };

    loadReportingDatasets();

    return () => {
      active = false;
    };
  }, [onDatasetsChange]);

  useEffect(() => {
    let active = true;

    const loadSavedConnections = async () => {
      setConnectionsLoading(true);

      try {
        const response = await apiFetch(`${API}/datasource/connections`, {
          headers: { Accept: "application/json" },
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          throw new Error(
            data.message ||
              data.detail ||
              `Unable to load saved connections (HTTP ${response.status}).`
          );
        }

        if (active) {
          setSavedConnections(
            Array.isArray(data.connections) ? data.connections : []
          );
        }
      } catch (error) {
        console.error(
          "Unable to load saved connections for Join Designer:",
          error
        );

        if (active) {
          setSavedConnections([]);
        }
      } finally {
        if (active) {
          setConnectionsLoading(false);
        }
      }
    };

    loadSavedConnections();

    return () => {
      active = false;
    };
  }, []);

  const savedConnectionMap = useMemo(
    () =>
      new Map(
        savedConnections
          .filter((connection) => connection?.id)
          .map((connection) => [connection.id, connection])
      ),
    [savedConnections]
  );

  const resolveDatasetConnection = (dataset) => {
    const connectionId = getDatasetConnectionId(dataset);

    return (
      (connectionId && savedConnectionMap.get(connectionId)) ||
      null
    );
  };

  const CONFIG_STORAGE_KEY = "reporting_tool_join_configurations";

  useEffect(() => {
    try {
      const stored = JSON.parse(
        localStorage.getItem(CONFIG_STORAGE_KEY) || "[]"
      );
      // Intentional localStorage -> React state hydration.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSavedConfigurations(Array.isArray(stored) ? stored : []);
    } catch (error) {
      console.error("Unable to load saved JOIN configurations:", error);
      // Reset after invalid localStorage data.
      setSavedConfigurations([]);
    }
  }, []);

  const persistSavedConfigurations = (items) => {
    setSavedConfigurations(items);
    try {
      localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(items));
    } catch (error) {
      console.error("Unable to persist JOIN configurations:", error);
    }
  };

  const selectedLeft = datasets.find((dataset) => dataset.id === leftDataset);
  const selectedRight = datasets.find(
    (dataset) => dataset.id === rightDataset
  );

  const leftColumns = useMemo(
    () => selectedLeft?.columns || [],
    [selectedLeft]
  );

  const rightColumns = useMemo(
    () => selectedRight?.columns || [],
    [selectedRight]
  );

  const availableQueryFields = useMemo(
    () =>
      datasets.flatMap((dataset) =>
        (dataset.columns || [])
          .map((rawField) => {
            const fieldName = getColumnName(rawField);
            const semanticLabel = getSemanticFieldLabel(dataset, fieldName);

            return {
              value: `${dataset.id}.${fieldName}`,
              label: `${getDatasetShortName(dataset)}.${semanticLabel}`,
              datasetId: dataset.id,
              field: fieldName,
              semanticRole: dataset?.semantic?.fields?.find?.((item) => (item?.physical_field || item?.physicalField) === fieldName)?.role || null,
            };
          })
          .filter((field) => field.field)
      ),
    [datasets]
  );

  const hasQueryFields = availableQueryFields.length > 0;

  const selectedFieldCount = Object.values(selectedFields).reduce(
    (total, fields) => total + fields.length,
    0
  );

  const selectedDatasetCount = Object.values(selectedFields).filter(
    (fields) => fields.length > 0
  ).length;

  const toggleDatasetExpanded = (datasetId) => {
    setExpandedDatasets((current) => ({
      ...current,
      [datasetId]: !(current[datasetId] ?? false),
    }));
  };

  const toggleField = (datasetId, field) => {
    setSelectedFields((current) => {
      const existing = current[datasetId] || [];
      const next = existing.includes(field)
        ? existing.filter((item) => item !== field)
        : [...existing, field];

      return { ...current, [datasetId]: next };
    });

    setResult(null);
  };

  const selectAllFields = (dataset) => {
    const fields = (dataset.columns || [])
      .map(getColumnName)
      .filter(Boolean);

    setSelectedFields((current) => ({
      ...current,
      [dataset.id]: fields,
    }));

    setResult(null);
  };

  const clearDatasetFields = (datasetId) => {
    setSelectedFields((current) => ({
      ...current,
      [datasetId]: [],
    }));

    setResult(null);
  };

  const updateJoinDraftDataset = (side, datasetId) => {
    if (side === "left") {
      setLeftDataset(datasetId);
      setLeftColumn("");
    } else {
      setRightDataset(datasetId);
      setRightColumn("");
    }

    setResult(null);
    setMessage("");
  };

  const resetJoinDraft = () => {
    setLeftDataset("");
    setRightDataset("");
    setLeftColumn("");
    setRightColumn("");
    setJoinType("INNER");
    setEditingJoinId("");
    setMessage("");
  };

  const addJoin = () => {
    if (!leftDataset || !rightDataset) {
      setMessage("Select both datasets for the JOIN.");
      return;
    }

    if (leftDataset === rightDataset) {
      setMessage("Dataset A and Dataset B must be different.");
      return;
    }

    if (!leftColumn || !rightColumn) {
      setMessage("Select both JOIN fields.");
      return;
    }

    const exists = joins.some(
      (join) =>
        join.left_dataset === leftDataset &&
        join.right_dataset === rightDataset &&
        join.left_column === leftColumn &&
        join.right_column === rightColumn &&
        join.join_type === joinType
    );

    if (exists) {
      setMessage("This JOIN relationship already exists.");
      return;
    }

    const join = {
      id: editingJoinId || createId("join", joins.length),
      left_dataset: leftDataset,
      right_dataset: rightDataset,
      left_column: leftColumn,
      right_column: rightColumn,
      join_type: joinType,
    };

    if (editingJoinId) {
      setJoins((current) =>
        current.map((item) => (item.id === editingJoinId ? join : item))
      );
      setResult(null);
      setMessage("JOIN connection updated.");
    } else {
      setJoins((current) => [...current, join]);
      setResult(null);
      setMessage("JOIN connection saved.");
    }

    resetJoinDraft();
  };

  const editJoin = (join) => {
    if (!join) return;

    setEditingJoinId(join.id);
    setLeftDataset(join.left_dataset || "");
    setRightDataset(join.right_dataset || "");
    setLeftColumn(join.left_column || "");
    setRightColumn(join.right_column || "");
    setJoinType(join.join_type || "INNER");
    setResult(null);
    setMessage("JOIN loaded for editing. Update the fields and save the connection.");
  };

  const removeJoin = (id) => {
    setJoins((current) => current.filter((join) => join.id !== id));
    setResult(null);
    setMessage("JOIN removed. Refresh the preview when ready.");
  };

  const moveJoin = (index, direction) => {
    const newIndex = direction === "up" ? index - 1 : index + 1;

    if (newIndex < 0 || newIndex >= joins.length) return;

    setJoins((current) => {
      const updated = [...current];
      [updated[index], updated[newIndex]] = [
        updated[newIndex],
        updated[index],
      ];
      return updated;
    });

    setResult(null);
  };

  const startDragField = (datasetId, field) => {
    setDraggedField({ datasetId, field });
  };

  const dropOnJoinField = (side) => {
    if (!draggedField) return;

    if (side === "left") {
      setLeftDataset(draggedField.datasetId);
      setLeftColumn(draggedField.field);
    } else {
      setRightDataset(draggedField.datasetId);
      setRightColumn(draggedField.field);
    }

    setMessage(
      `${draggedField.field} dropped into the ${side.toUpperCase()} JOIN field.`
    );
    setDraggedField(null);
    setResult(null);
  };

  const addFilter = () => {
    if (!hasQueryFields) return;

    setFilters((current) => [
      ...current,
      {
        id: createId("filter", current.length),
        field: availableQueryFields[0].value,
        operator: "=",
        value: "",
      },
    ]);

    setCollapsedFeatures((current) => ({
      ...current,
      filters: false,
    }));
  };

  const updateFilter = (id, key, value) => {
    setFilters((current) =>
      current.map((item) =>
        item.id === id ? { ...item, [key]: value } : item
      )
    );
    setResult(null);
  };

  const removeFilter = (id) => {
    setFilters((current) => current.filter((item) => item.id !== id));
    setResult(null);
  };

  const addSort = () => {
    if (!hasQueryFields) return;

    setSorts((current) => [
      ...current,
      {
        id: createId("sort", current.length),
        field: availableQueryFields[0].value,
        direction: "ASC",
      },
    ]);

    setCollapsedFeatures((current) => ({
      ...current,
      sorting: false,
    }));
  };

  const updateSort = (id, key, value) => {
    setSorts((current) =>
      current.map((item) =>
        item.id === id ? { ...item, [key]: value } : item
      )
    );
    setResult(null);
  };

  const removeSort = (id) => {
    setSorts((current) => current.filter((item) => item.id !== id));
    setResult(null);
  };

  const addGroupBy = () => {
    if (!hasQueryFields) return;

    setGroupBy((current) => [
      ...current,
      availableQueryFields[0].value,
    ]);

    setCollapsedFeatures((current) => ({
      ...current,
      grouping: false,
    }));

    setResult(null);
  };

  const updateGroupBy = (index, value) => {
    setGroupBy((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index ? value : item
      )
    );
    setResult(null);
  };

  const removeGroupBy = (index) => {
    setGroupBy((current) =>
      current.filter((_, itemIndex) => itemIndex !== index)
    );
    setResult(null);
  };

  const addAggregation = () => {
    if (!hasQueryFields) return;

    setAggregations((current) => [
      ...current,
      {
        id: createId("aggregation", current.length),
        field: availableQueryFields[0].value,
        function:
          getDefaultAggregation(
            datasets.find((dataset) => dataset.id === availableQueryFields[0].datasetId),
            availableQueryFields[0].field
          ) || "COUNT",
      },
    ]);

    setCollapsedFeatures((current) => ({
      ...current,
      aggregation: false,
    }));

    setResult(null);
  };

  const updateAggregation = (id, key, value) => {
    setAggregations((current) =>
      current.map((item) =>
        item.id === id ? { ...item, [key]: value } : item
      )
    );
    setResult(null);
  };

  const removeAggregation = (id) => {
    setAggregations((current) =>
      current.filter((item) => item.id !== id)
    );
    setResult(null);
  };

  const addCalculatedColumn = () => {
    if (!hasQueryFields) return;

    setCalculatedColumns((current) => [
      ...current,
      {
        id: createId("calculated", current.length),
        alias: `Calculated_${current.length + 1}`,
        left_field: availableQueryFields[0].value,
        operation: "ADD",
        right_field: "",
        right_value: "",
      },
    ]);

    setCollapsedFeatures((current) => ({
      ...current,
      calculated: false,
    }));

    setResult(null);
  };

  const updateCalculatedColumn = (id, key, value) => {
    setCalculatedColumns((current) =>
      current.map((item) =>
        item.id === id ? { ...item, [key]: value } : item
      )
    );
    setResult(null);
  };

  const removeCalculatedColumn = (id) => {
    setCalculatedColumns((current) =>
      current.filter((item) => item.id !== id)
    );
    setResult(null);
  };

  const clearQuerySettings = () => {
    setFilters([]);
    setSorts([]);
    setGroupBy([]);
    setAggregations([]);
    setCalculatedColumns([]);
    setResult(null);
    setMessage(
      "Query rules cleared. Dataset selections and JOIN relationships were kept."
    );
  };

  const getConfigurationSnapshot = () => ({
    datasets: datasets.map((dataset) => ({
      id: dataset.id,
      connection_id: getDatasetConnectionId(dataset),
      source_type: getDatasetSourceType(dataset),
      database: getDatasetDatabase(dataset),
      object_name: getDatasetObjectName(dataset),
      object_type: dataset.object_type || "table",
      columns: dataset.columns || [],
    })),
    joins: joins.map((item) => ({
      left_dataset: item.left_dataset,
      right_dataset: item.right_dataset,
      left_column: item.left_column,
      right_column: item.right_column,
      join_type: item.join_type,
    })),
    selectedFields,
    filters,
    sorts,
    group_by: groupBy,
    aggregations,
    calculated_columns: calculatedColumns,
    limit: Number(limit) || 0,
  });

  const getConfigurationFingerprint = (configuration) =>
    JSON.stringify(configuration);

  const currentConfigurationFingerprint = getConfigurationFingerprint(
    getConfigurationSnapshot()
  );

  const isAppliedConfigurationCurrent =
    Boolean(appliedConfiguration) &&
    appliedConfiguration.fingerprint === currentConfigurationFingerprint;

  const buildRequestBody = () => ({
    datasets: datasets.map((dataset) => {
      const connection = resolveDatasetConnection(dataset);

      const sourceType =
        getDatasetSourceType(dataset) ||
        connection?.source_type ||
        connection?.sourceType ||
        "";

      const database = getDatasetDatabase(dataset);
      const objectName = getDatasetObjectName(dataset);

      return {
        id: dataset.id,
        source_type: sourceType,
        host: dataset.host || connection?.host || "",
        port: Number(dataset.port || connection?.port || 0),
        username:
          dataset.username ??
          connection?.username ??
          undefined,
        // GET /datasource/connections intentionally does not expose passwords.
        // Never manufacture password: null for a saved connection.
        ...(dataset.password
          ? { password: dataset.password }
          : {}),
        database,
        table: objectName,
        object_name: objectName,
        connection_id: getDatasetConnectionId(dataset),
        ...(getSemanticDatasetId(dataset)
          ? { semantic_dataset_id: getSemanticDatasetId(dataset) }
          : {}),
      };
    }),

    joins: joins.map(
      ({
        left_dataset,
        right_dataset,
        left_column,
        right_column,
        join_type,
      }) => ({
        left_dataset,
        right_dataset,
        left_column,
        right_column,
        join_type,
      })
    ),

    columns: Object.entries(selectedFields).flatMap(
      ([datasetId, fields]) =>
        fields.map((field) => ({
          field: `${datasetId}.${field}`,
          alias: `${datasetId}.${field}`,
        }))
    ),

    filters: filters
      .filter((item) => item.field)
      .map(({ ...item }) => item),

    sorts: sorts
      .filter((item) => item.field)
      .map(({ ...item }) => item),

    group_by: groupBy.filter(Boolean),

    aggregations: aggregations
      .filter((item) => item.field && item.function)
      .map(({ ...item }) => item),

    calculated_columns: calculatedColumns
      .filter(
        (item) =>
          item.alias &&
          item.left_field &&
          item.operation &&
          (item.right_field || item.right_value !== "")
      )
      .map(({ ...item }) => ({
        ...item,
        right_field: item.right_field || null,
        right_value: item.right_field ? null : item.right_value,
      })),

    limit: Number(limit) || 0,
  });


  const runReportQuery = async (body) => {
    const { jobId, result } = await executeReportJob(body, { loadAll: false, pageSize: 5000, returnOnFirstPage: true });

    return {
      ...result,
      success: result?.success !== false,
      execution_job_id: jobId,
      applied_joins: body.joins,
      applied_columns: body.columns,
      applied_filters: body.filters,
      applied_sorts: body.sorts,
      applied_group_by: body.group_by,
      applied_aggregations: body.aggregations,
      applied_calculated_columns: body.calculated_columns,
      applied_limit: body.limit,
      execution_status: result?.execution_status || "completed",
      execution_in_progress: Boolean(result?.execution_in_progress),
    };
  };

  const validateCurrentConfiguration = () => {
    if (datasets.length < 2) {
      throw new Error("Add at least two datasets in Data Sources.");
    }

    if (joins.length < 1) {
      throw new Error("Create at least one JOIN relationship first.");
    }

    if (selectedFieldCount === 0) {
      throw new Error("Select at least one output field before applying the configuration.");
    }

    const unresolvedConnections = datasets.filter((dataset) => {
      const connection = resolveDatasetConnection(dataset);
      return (
        getDatasetConnectionId(dataset) &&
        !connection &&
        !dataset.host
      );
    });

    if (unresolvedConnections.length > 0) {
      throw new Error(
        connectionsLoading
          ? "Saved database connections are still loading. Please try Apply again in a moment."
          : "One or more reporting datasets reference a saved connection that could not be loaded. Refresh Data Sources and try again."
      );
    }

    const body = buildRequestBody();

    const invalidDataset = body.datasets.find(
      (dataset) =>
        !dataset.source_type ||
        !dataset.host ||
        !dataset.port ||
        !dataset.database ||
        !dataset.table
    );

    if (invalidDataset) {
      throw new Error(
        `Dataset "${invalidDataset.table || invalidDataset.id}" is missing connection or object details. Refresh the saved connections and datasets in Data Sources.`
      );
    }

    return body;
  };

  const applyConfiguration = async () => {
    cancelPreviewRequest();
    if (configurationLocked) {
      setMessage("Configuration is already applied. Choose Edit Configuration to make changes.");
      return;
    }

    setMessage("");
    setResult(null);
    setLoading(true);

    try {
      const body = validateCurrentConfiguration();
      const data = await runReportQuery(body);
      const snapshot = getConfigurationSnapshot();

      /*
       * The execution-job response is the authoritative result of the exact
       * configuration the user just applied. Live Preview consumes only the
       * first bounded result page; later pages are fetched from ResultStore by
       * job id. This keeps Apply and Live Preview on one execution path while
       * avoiding browser-side full-result materialization.
       */
      const previewResult = {
        ...data,
        source: "report_query_live_preview",
        preview_only: true,
      };

      setResult(previewResult);
      setPreviewPage(0);
      setAppliedConfiguration({
        fingerprint: getConfigurationFingerprint(snapshot),
        snapshot,
        requestBody: body,
        result: previewResult,
        appliedAt: new Date().toISOString(),
      });
      setConfigurationLocked(true);

      setMessage(
        `Configuration applied successfully. ${data.returned_rows || data.rows?.length || 0} row(s) loaded into Live Preview.`
      );
    } catch (error) {
      console.error(error);
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const editConfiguration = () => {
    cancelPreviewRequest();
    setConfigurationLocked(false);
    setAppliedConfiguration(null);
    setResult(null);
    setMessage("Configuration unlocked. Make your changes, then click Apply again.");
  };

  const buildAppliedReport = () => {
    if (!appliedConfiguration || !isAppliedConfigurationCurrent) {
      setMessage("Apply the current configuration before building the report.");
      return;
    }

    if (!onReportResult) {
      setMessage("Report Builder is not available.");
      return;
    }

    onReportResult(appliedConfiguration.result);
    setMessage("Applied configuration sent to Report Builder.");
  };

  const loadPreviewPage = async (pageIndex) => {
    const jobId = result?.execution_job_id;
    if (!jobId || previewPageLoading || pageIndex < 0) return;

    cancelPreviewRequest();
    const controller = new AbortController();
    const requestSequence = previewRequestRef.current.sequence;
    previewRequestRef.current.controller = controller;
    setPreviewPageLoading(true);
    try {
      const pageSize = 500;
      const page = await resultWindowCacheRef.current.get(jobId, {
        offset: pageIndex * pageSize,
        limit: pageSize,
        signal: controller.signal,
      }, fetchExecutionJobResultPage);
      if (controller.signal.aborted || previewRequestRef.current.sequence !== requestSequence) return;
      setResult((current) => current ? ({
        ...current,
        rows: Array.isArray(page?.rows) ? page.rows : [],
        columns: Array.isArray(page?.columns) && page.columns.length ? page.columns : current.columns,
        returned_rows: Number(page?.returned_rows ?? page?.rows?.length ?? 0) || 0,
        total_rows: Number(page?.total_rows ?? current.total_rows ?? 0) || 0,
        page_offset: Number(page?.offset ?? pageIndex * pageSize) || 0,
        page_size: Number(page?.limit ?? pageSize) || pageSize,
        has_more: Boolean(page?.has_more),
      }) : current);
      setPreviewPage(pageIndex);
    } catch (error) {
      if (error?.name !== "AbortError") setMessage(`Unable to load preview page: ${error.message}`);
    } finally {
      if (previewRequestRef.current.sequence === requestSequence) {
        previewRequestRef.current.controller = null;
        setPreviewPageLoading(false);
      }
    }
  };

  const refreshLivePreview = async () => {
    cancelPreviewRequest();
    if (!appliedConfiguration || !isAppliedConfigurationCurrent) {
      setMessage("Apply the current configuration before refreshing Live Preview.");
      return;
    }

    setMessage("");
    setLoading(true);

    try {
      /*
       * Refresh the exact immutable request captured by Apply. The backend
       * therefore uses the same saved connections, JOINs and query rules as
       * the applied configuration instead of rebuilding a separate client
       * preview from individual datasets.
       */
      const data = await runReportQuery(appliedConfiguration.requestBody);
      const previewResult = {
        ...data,
        source: "report_query_live_preview",
        preview_only: true,
      };

      setResult(previewResult);
      setPreviewPage(0);
      setAppliedConfiguration((current) =>
        current
          ? { ...current, result: previewResult }
          : current
      );

      setMessage(
        `Live Preview refreshed successfully. ${
          data.returned_rows || data.rows?.length || 0
        } row(s) returned.`
      );
    } catch (error) {
      console.error(error);
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const saveConfiguration = () => {
    if (!appliedConfiguration || !isAppliedConfigurationCurrent) {
      setMessage("Apply the current configuration before saving it.");
      return;
    }

    const name = configurationName.trim();

    if (!name) {
      setMessage("Enter a configuration name before saving.");
      return;
    }

    const now = new Date().toISOString();
    const existing = savedConfigurations.find(
      (item) => item.name.toLowerCase() === name.toLowerCase()
    );

    const item = {
      id: existing?.id || createId("config", savedConfigurations.length),
      name,
      ...appliedConfiguration,
      savedAt: existing?.savedAt || now,
      updatedAt: now,
    };

    const next = [
      item,
      ...savedConfigurations.filter((entry) => entry.id !== item.id),
    ];

    persistSavedConfigurations(next);
    setSelectedSavedConfigurationId(item.id);
    setConfigurationName(name);
    setMessage(`Configuration "${name}" saved.`);
  };

  const deleteConfiguration = () => {
    if (!selectedSavedConfigurationId) {
      setMessage("Select a saved configuration to delete.");
      return;
    }

    const target = savedConfigurations.find(
      (item) => item.id === selectedSavedConfigurationId
    );

    if (!target) {
      setMessage("The selected saved configuration no longer exists.");
      return;
    }

    const next = savedConfigurations.filter(
      (item) => item.id !== selectedSavedConfigurationId
    );

    persistSavedConfigurations(next);
    setSelectedSavedConfigurationId("");
    setMessage(`Configuration "${target.name}" deleted.`);
  };

  const loadConfiguration = (configurationId) => {
    const item = savedConfigurations.find(
      (entry) => entry.id === configurationId
    );

    if (!item) {
      setSelectedSavedConfigurationId("");
      return;
    }

    const snapshot = item.snapshot || {};

    const currentDatasetIds = new Set(datasets.map((dataset) => dataset.id));
    const snapshotDatasetIds = new Set(
      (snapshot.datasets || []).map((dataset) => dataset.id)
    );

    if (
      currentDatasetIds.size !== snapshotDatasetIds.size ||
      [...currentDatasetIds].some((id) => !snapshotDatasetIds.has(id))
    ) {
      setMessage(
        "This configuration was saved with a different dataset set. Load it from Data Sources first so the dataset IDs match."
      );
      return;
    }

    setSelectedSavedConfigurationId(configurationId);
    setConfigurationName(item.name);
    setJoins(
      (snapshot.joins || []).map((join, index) => ({
        ...join,
        id: createId("join", index),
      }))
    );
    setSelectedFields(snapshot.selectedFields || {});
    setFilters(
      (snapshot.filters || []).map((filter, index) => ({
        ...filter,
        id: filter.id || createId("filter", index),
      }))
    );
    setSorts(
      (snapshot.sorts || []).map((sort, index) => ({
        ...sort,
        id: sort.id || createId("sort", index),
      }))
    );
    setGroupBy(snapshot.group_by || []);
    setAggregations(
      (snapshot.aggregations || []).map((item, index) => ({
        ...item,
        id: item.id || createId("aggregation", index),
      }))
    );
    setCalculatedColumns(
      (snapshot.calculated_columns || []).map((item, index) => ({
        ...item,
        id: item.id || createId("calculated", index),
      }))
    );
    setLimit(snapshot.limit ?? 0);
    setConfigurationLocked(false);
    setAppliedConfiguration(null);
    setResult(null);
    setMessage(`Configuration "${item.name}" loaded into the editor. Click Apply to validate it.`);
  };

  const visibleDatasets = datasets.slice(0, MAX_VISIBLE_DATASETS);

  const getFilteredFields = (dataset) => {
    const query = String(datasetSearch[dataset.id] || "")
      .trim()
      .toLowerCase();

    if (!query) return dataset.columns || [];

    return (dataset.columns || []).filter((rawField) =>
      getColumnName(rawField).toLowerCase().includes(query)
    );
  };

  const toggleFeature = (feature) => {
    setCollapsedFeatures((current) => ({
      ...current,
      [feature]: !current[feature],
    }));
  };

  const featureRows = [
    {
      key: "connect",
      icon: "⇄",
      title: "Connect Data Set",
      description: "Connect datasets with JOIN relationships",
      count: joins.length,
    },
    {
      key: "calculated",
      icon: "ƒx",
      title: "Calculated Columns",
      description: "Create derived output fields",
      count: calculatedColumns.length,
    },
    {
      key: "filters",
      icon: "⌕",
      title: "Filters",
      description: "Limit rows before the final result",
      count: filters.length,
    },
    {
      key: "grouping",
      icon: "▦",
      title: "Group By",
      description: "Group records for summarized reporting",
      count: groupBy.length,
    },
    {
      key: "aggregation",
      icon: "Σ",
      title: "Aggregation",
      description: "COUNT, SUM, AVG, MIN or MAX",
      count: aggregations.length,
    },
    {
      key: "sorting",
      icon: "↕",
      title: "Sort",
      description: "Control final result order",
      count: sorts.length,
    },
  ];

  return (
    <><div className="jdx-root">
      <style>{JOIN_DESIGNER_CSS}</style>
        <section className="jdx-heading">
          <div>
            <span className="jdx-eyebrow">Visual Query Designer</span>
            <h2>Build Your Reporting Query</h2>
            <p>
              Select output fields, connect datasets with one or more JOIN
              relationships, refine the result with query rules, and preview
              the final data before sending it to Report Builder.
            </p>
          </div>

          <div className="jdx-mode">VISUAL MODE</div>
        </section>

        {message && (
          <div
            className={`jdx-message ${
              message.startsWith("Error:") ? "error" : ""
            }`}
          >
            {message}
          </div>
        )}

        {/* =====================================================
            QUERY ACTIONS
            ===================================================== */}
        <section className="jdx-card jdx-actions">
          <div className="jdx-actions-top">
            <div className="jdx-actions-title">
              <span className="jdx-eyebrow">Query Actions</span>
              <h3>Validate, preview and apply</h3>
              <p>
                Apply validates and locks the current query. Build Report is
                enabled only after an applied configuration exists.
              </p>
            </div>

            <div className="jdx-action-buttons">
              <button
                type="button"
                className="jdx-btn primary"
                onClick={applyConfiguration}
                disabled={loading || configurationLocked}
              >
                {loading ? "Applying..." : "Apply"}
              </button>

              <button
                type="button"
                className="jdx-btn"
                onClick={buildAppliedReport}
                disabled={
                  loading ||
                  !configurationLocked ||
                  !isAppliedConfigurationCurrent
                }
              >
                Build Report
              </button>

              <button
                type="button"
                className="jdx-btn"
                onClick={editConfiguration}
                disabled={loading || !configurationLocked}
              >
                Edit Configuration
              </button>

              <button
                type="button"
                className="jdx-btn"
                onClick={clearQuerySettings}
                disabled={configurationLocked}
              >
                Clear Rules
              </button>
            </div>
          </div>

          <div className="jdx-summary">
            <div className="jdx-summary-item">
              <strong>{datasets.length}</strong>
              <span>Datasets</span>
            </div>
            <div className="jdx-summary-item">
              <strong>{selectedDatasetCount}</strong>
              <span>Output Datasets</span>
            </div>
            <div className="jdx-summary-item">
              <strong>{selectedFieldCount}</strong>
              <span>Output Fields</span>
            </div>
            <div className="jdx-summary-item">
              <strong>{joins.length}</strong>
              <span>JOINs</span>
            </div>
            <div className="jdx-summary-item">
              <strong>{filters.length}</strong>
              <span>Filters</span>
            </div>
            <div className="jdx-summary-item">
              <strong>{groupBy.length}</strong>
              <span>Groups</span>
            </div>
            <div className="jdx-summary-item">
              <strong>{aggregations.length}</strong>
              <span>Aggregations</span>
            </div>
            <div className="jdx-summary-item">
              <strong>{calculatedColumns.length + sorts.length}</strong>
              <span>Other Rules</span>
            </div>
          </div>

          <div className="jdx-action-footer">
            <label className="jdx-limit">
              Preview Row Limit
              <span className="jdx-limit-note">0 = full result; browser preview remains paged</span>
              <input
                type="number"
                min="0"
                value={limit}
                onChange={(event) => {
                  setLimit(event.target.value);
                  setResult(null);
                }}
              />
            </label>

            <div className="jdx-action-state">
              <span className="jdx-dot" />
              {configurationLocked
                ? "Configuration applied and locked"
                : joins.length
                ? `${joins.length} JOIN relationship${
                    joins.length === 1 ? "" : "s"
                  } configured · Apply when ready`
                : "Add a JOIN relationship to enable Apply"}
            </div>
          </div>

          <div className="jdx-config-management">
            <div className="jdx-config-info">
              <span className="jdx-eyebrow">QUERY CONFIGURATION</span>
              <strong>
                {configurationLocked
                  ? "Applied configuration"
                  : "Draft configuration"}
              </strong>
              <small>
                {configurationLocked
                  ? "The current query is locked. Save it with a name or edit it to create a new draft."
                  : "Changes stay local to the editor until Apply Configuration is clicked."}
              </small>
            </div>

            <div className="jdx-config-controls">
              <input
                className="jdx-config-name"
                value={configurationName}
                onChange={(event) => setConfigurationName(event.target.value)}
                placeholder="Configuration name..."
                disabled={!configurationLocked}
              />

              <select
                className="jdx-config-select"
                value={selectedSavedConfigurationId}
                onChange={(event) => loadConfiguration(event.target.value)}
              >
                <option value="">Saved configurations</option>
                {savedConfigurations.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>

              <button
                type="button"
                className="jdx-btn"
                onClick={saveConfiguration}
                disabled={!configurationLocked || !isAppliedConfigurationCurrent}
              >
                Save
              </button>

              <button
                type="button"
                className="jdx-btn danger"
                onClick={deleteConfiguration}
                disabled={!selectedSavedConfigurationId}
              >
                Delete
              </button>
            </div>
          </div>
        </section>

        <fieldset
          className="jdx-lock-scope"
          disabled={configurationLocked}
        >
          <div className="jdx-workspace">
            {/* ===================================================
                LEFT — QUERY FEATURES
                =================================================== */}
          <aside className="jdx-sidebar">
            <div className="jdx-panel-title">
              <span className="jdx-eyebrow">Report Logic</span>
              <h3>Query Features</h3>
              <p>
                Rules stay compact until you expand the feature you want to
                configure.
              </p>
            </div>

            {featureRows.map((feature) => (
              <section className="jdx-card jdx-feature" key={feature.key}>
                <button
                  type="button"
                  className="jdx-feature-header"
                  onClick={() => toggleFeature(feature.key)}
                  aria-expanded={!collapsedFeatures[feature.key]}
                >
                  <span className="jdx-feature-icon">{feature.icon}</span>

                  <span className="jdx-feature-heading">
                    <strong>{feature.title}</strong>
                    <small>{feature.description}</small>
                  </span>

                  <span className="jdx-count">{feature.count}</span>

                  <span className="jdx-chevron">
                    {collapsedFeatures[feature.key] ? "▸" : "▾"}
                  </span>
                </button>

                {!collapsedFeatures[feature.key] && (
                  <div className="jdx-feature-body">
                    {feature.key === "connect" && (
                      <>
                                          {/* ============================================
                      JOIN BUILDER + PIPELINE
                      ============================================ */}
                  <div className="jdx-join-area">
                    <div className="jdx-join-heading">
                      <div>
                        <span className="jdx-eyebrow">
                          JOIN Relationships
                        </span>
                        <h4>Connect datasets</h4>
                        <p>
                          Add one relationship at a time. Every added
                          relationship becomes part of the execution
                          pipeline.
                        </p>
                      </div>

                      <span className="jdx-count">
                        {joins.length}
                      </span>
                    </div>

                    <div
                      className="jdx-join-builder jdx-connect-join-builder"
                      style={{
                        display: "block",
                        width: "100%",
                        minWidth: 0,
                        boxSizing: "border-box",
                        overflow: "visible",
                      }}
                    >
                      <div
                        className="jdx-join-fields-grid"
                        style={{
                          display: "grid",
                          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
                          gridTemplateAreas: '"dataset-a field-a" "join-type join-type" "dataset-b field-b"',
                          gap: "10px",
                          width: "100%",
                          minWidth: 0,
                          boxSizing: "border-box",
                        }}
                      >
                        <div className="jdx-control jdx-connect-control jdx-connect-dataset-a"
                          style={{ gridArea: "dataset-a", width: "100%", minWidth: 0, minHeight: 68, boxSizing: "border-box", display: "flex", flexDirection: "column" }}>
                        <span>Dataset A</span>
                        <select
                          style={{
                            display: "block",
                            width: "100%",
                            minWidth: 0,
                            maxWidth: "100%",
                            height: 42,
                            minHeight: 42,
                            boxSizing: "border-box",
                            padding: "0 34px 0 12px",
                            border: "1px solid #cbd8e8",
                            borderRadius: 8,
                            background: "#ffffff",
                            color: "#172033",
                            fontSize: 10,
                          }}
                          value={leftDataset}
                          onChange={(event) =>
                            updateJoinDraftDataset(
                              "left",
                              event.target.value
                            )
                          }
                        >
                          <option value="">
                            Select dataset
                          </option>
                          {datasets.map((dataset) => (
                            <option
                              value={dataset.id}
                              key={dataset.id}
                            >
                              {getDatasetLabel(dataset)}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div
                        className="jdx-control jdx-connect-control jdx-connect-field-a"
                        style={{ gridArea: "field-a", width: "100%", minWidth: 0, minHeight: 68, boxSizing: "border-box", display: "flex", flexDirection: "column" }}
                        onDragOver={(event) =>
                          event.preventDefault()
                        }
                        onDrop={() => dropOnJoinField("left")}
                      >
                        <span>Field A</span>
                        <select
                          style={{
                            display: "block",
                            width: "100%",
                            minWidth: 0,
                            maxWidth: "100%",
                            height: 42,
                            minHeight: 42,
                            boxSizing: "border-box",
                            padding: "0 34px 0 12px",
                            border: "1px solid #cbd8e8",
                            borderRadius: 8,
                            background: "#ffffff",
                            color: "#172033",
                            fontSize: 10,
                          }}
                          value={leftColumn}
                          onChange={(event) => {
                            setLeftColumn(event.target.value);
                            setResult(null);
                          }}
                          disabled={!leftDataset}
                        >
                          <option value="">
                            {leftDataset
                              ? "Select field"
                              : "Select dataset first"}
                          </option>
                          {leftColumns.map((rawField) => {
                            const field =
                              getColumnName(rawField);

                            return (
                              <option
                                value={field}
                                key={field}
                              >
                                {field}
                              </option>
                            );
                          })}
                        </select>
                      </div>

                      <div className="jdx-control jdx-connect-control jdx-connect-join-type"
                        style={{ gridArea: "join-type", width: "100%", minWidth: 0, minHeight: 68, boxSizing: "border-box", display: "flex", flexDirection: "column" }}>
                        <span>Join Type</span>
                        <select
                          style={{
                            display: "block",
                            width: "100%",
                            minWidth: 0,
                            maxWidth: "100%",
                            height: 42,
                            minHeight: 42,
                            boxSizing: "border-box",
                            padding: "0 34px 0 12px",
                            border: "1px solid #cbd8e8",
                            borderRadius: 8,
                            background: "#ffffff",
                            color: "#172033",
                            fontSize: 10,
                          }}
                          value={joinType}
                          onChange={(event) => {
                            setJoinType(event.target.value);
                            setResult(null);
                          }}
                        >
                          <option value="INNER">
                            INNER JOIN
                          </option>
                          <option value="LEFT">
                            LEFT JOIN
                          </option>
                          <option value="RIGHT">
                            RIGHT JOIN
                          </option>
                          <option value="FULL">
                            FULL JOIN
                          </option>
                        </select>
                      </div>

                      <div className="jdx-control jdx-connect-control jdx-connect-dataset-b"
                        style={{ gridArea: "dataset-b", width: "100%", minWidth: 0, minHeight: 68, boxSizing: "border-box", display: "flex", flexDirection: "column" }}>
                        <span>Dataset B</span>
                        <select
                          style={{
                            display: "block",
                            width: "100%",
                            minWidth: 0,
                            maxWidth: "100%",
                            height: 42,
                            minHeight: 42,
                            boxSizing: "border-box",
                            padding: "0 34px 0 12px",
                            border: "1px solid #cbd8e8",
                            borderRadius: 8,
                            background: "#ffffff",
                            color: "#172033",
                            fontSize: 10,
                          }}
                          value={rightDataset}
                          onChange={(event) =>
                            updateJoinDraftDataset(
                              "right",
                              event.target.value
                            )
                          }
                        >
                          <option value="">
                            Select dataset
                          </option>
                          {datasets.map((dataset) => (
                            <option
                              value={dataset.id}
                              key={dataset.id}
                            >
                              {getDatasetLabel(dataset)}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div
                        className="jdx-control jdx-connect-control jdx-connect-field-b"
                        style={{ gridArea: "field-b", width: "100%", minWidth: 0, minHeight: 68, boxSizing: "border-box", display: "flex", flexDirection: "column" }}
                        onDragOver={(event) =>
                          event.preventDefault()
                        }
                        onDrop={() => dropOnJoinField("right")}
                      >
                        <span>Field B</span>
                        <select
                          style={{
                            display: "block",
                            width: "100%",
                            minWidth: 0,
                            maxWidth: "100%",
                            height: 42,
                            minHeight: 42,
                            boxSizing: "border-box",
                            padding: "0 34px 0 12px",
                            border: "1px solid #cbd8e8",
                            borderRadius: 8,
                            background: "#ffffff",
                            color: "#172033",
                            fontSize: 10,
                          }}
                          value={rightColumn}
                          onChange={(event) => {
                            setRightColumn(event.target.value);
                            setResult(null);
                          }}
                          disabled={!rightDataset}
                        >
                          <option value="">
                            {rightDataset
                              ? "Select field"
                              : "Select dataset first"}
                          </option>
                          {rightColumns.map((rawField) => {
                            const field =
                              getColumnName(rawField);

                            return (
                              <option
                                value={field}
                                key={field}
                              >
                                {field}
                              </option>
                            );
                          })}
                        </select>
                      </div>

                      </div>

                      <div className="jdx-join-actions">
                        <button
                          type="button"
                          className="jdx-btn"
                          onClick={resetJoinDraft}
                        >
                          Reset
                        </button>

                        <button
                          type="button"
                          className="jdx-btn primary"
                          onClick={addJoin}
                          disabled={
                            !leftDataset ||
                            !rightDataset ||
                            !leftColumn ||
                            !rightColumn
                          }
                        >
                          {editingJoinId ? "Save Changes" : "+ Add JOIN"}
                        </button>
                      </div>
                    </div>

                    {joins.length === 0 ? (
                      <div className="jdx-empty" style={{ marginTop: "8px" }}>
                        <strong>No JOIN relationships yet</strong>
                        <span>
                          Configure Dataset A, Field A, Dataset B and Field B
                          above.
                        </span>
                      </div>
                    ) : (
                      <div className="jdx-pipeline">
                        {joins.map((join, index) => {
                          const left = datasets.find(
                            (dataset) =>
                              dataset.id === join.left_dataset
                          );
                          const right = datasets.find(
                            (dataset) =>
                              dataset.id === join.right_dataset
                          );

                          return (
                            <div
                              className="jdx-pipeline-item"
                              key={join.id || index}
                            >
                              <span className="jdx-pipeline-number">
                                {index + 1}
                              </span>

                              <div className="jdx-pipeline-side">
                                <strong>
                                  {getDatasetShortName(left) ||
                                    join.left_dataset}
                                </strong>
                                <span>
                                  {join.left_column}
                                </span>
                              </div>

                              <span className="jdx-pipeline-type">
                                {join.join_type}
                              </span>

                              <span className="jdx-pipeline-eq">
                                =
                              </span>

                              <div className="jdx-pipeline-side">
                                <strong>
                                  {getDatasetShortName(right) ||
                                    join.right_dataset}
                                </strong>
                                <span>
                                  {join.right_column}
                                </span>
                              </div>

                              <div className="jdx-pipeline-actions">
                                <button
                                  type="button"
                                  className="jdx-join-modify-button"
                                  onClick={() => editJoin(join)}
                                  title="Modify JOIN connection"
                                >
                                  ✎
                                </button>

                                <button
                                  type="button"
                                  onClick={() =>
                                    moveJoin(index, "up")
                                  }
                                  disabled={index === 0}
                                  title="Move JOIN up"
                                >
                                  ↑
                                </button>

                                <button
                                  type="button"
                                  onClick={() =>
                                    moveJoin(index, "down")
                                  }
                                  disabled={
                                    index === joins.length - 1
                                  }
                                  title="Move JOIN down"
                                >
                                  ↓
                                </button>

                                <button
                                  type="button"
                                  onClick={() =>
                                    removeJoin(join.id)
                                  }
                                  title="Remove JOIN"
                                >
                                  ×
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                      </>
                    )}

                    {feature.key === "filters" && (
                      <>
                        <div className="jdx-feature-toolbar">
                          <span>Add conditions to restrict the result.</span>
                          <button
                            type="button"
                            className="jdx-btn small"
                            onClick={addFilter}
                            disabled={!hasQueryFields}
                          >
                            + Add
                          </button>
                        </div>

                        {filters.length === 0 ? (
                          <div className="jdx-empty">
                            <strong>No filters configured</strong>
                            <span>Add a filter when the result needs row-level restrictions.</span>
                          </div>
                        ) : (
                          <div className="jdx-rule-list">
                            {filters.map((filter, index) => (
                              <div className="jdx-rule" key={filter.id}>
                                <div className="jdx-rule-top">
                                  <span>Condition {index + 1}</span>
                                  <button
                                    type="button"
                                    className="jdx-icon-button danger"
                                    onClick={() =>
                                      removeFilter(filter.id)
                                    }
                                    title="Remove filter"
                                  >
                                    ×
                                  </button>
                                </div>

                                <div className="jdx-filter-row">
                                  <div className="jdx-control">
                                    <label>Field</label>
                                    <select
                                      value={filter.field}
                                      onChange={(event) =>
                                        updateFilter(
                                          filter.id,
                                          "field",
                                          event.target.value
                                        )
                                      }
                                    >
                                      {availableQueryFields.map(
                                        (field) => (
                                          <option
                                            key={field.value}
                                            value={field.value}
                                          >
                                            {field.label}
                                          </option>
                                        )
                                      )}
                                    </select>
                                  </div>

                                  <div className="jdx-control">
                                    <label>Operator</label>
                                    <select
                                      value={filter.operator}
                                      onChange={(event) =>
                                        updateFilter(
                                          filter.id,
                                          "operator",
                                          event.target.value
                                        )
                                      }
                                    >
                                      <option value="=">=</option>
                                      <option value="!=">!=</option>
                                      <option value=">">&gt;</option>
                                      <option value=">=">&gt;=</option>
                                      <option value="<">&lt;</option>
                                      <option value="<=">&lt;=</option>
                                      <option value="CONTAINS">
                                        contains
                                      </option>
                                      <option value="STARTS_WITH">
                                        starts with
                                      </option>
                                      <option value="ENDS_WITH">
                                        ends with
                                      </option>
                                      <option value="IS_NULL">
                                        is empty
                                      </option>
                                      <option value="IS_NOT_NULL">
                                        is not empty
                                      </option>
                                      <option value="NOT_CONTAINS">
                                        does not contain
                                      </option>
                                      <option value="IN">
                                        in
                                      </option>
                                      <option value="NOT_IN">
                                        not in
                                      </option>
                                      <option value="BETWEEN">
                                        between
                                      </option>
                                    </select>
                                  </div>

                                  {![
                                    "IS_NULL",
                                    "IS_NOT_NULL",
                                  ].includes(filter.operator) && (
                                    <div className="jdx-control jdx-value">
                                      <label>Value</label>
                                      <input
                                        value={filter.value}
                                        placeholder="Enter value"
                                        onChange={(event) =>
                                          updateFilter(
                                            filter.id,
                                            "value",
                                            event.target.value
                                          )
                                        }
                                      />
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}

                    {feature.key === "grouping" && (
                      <>
                        <div className="jdx-feature-toolbar">
                          <span>Select fields that define each group.</span>
                          <button
                            type="button"
                            className="jdx-btn small"
                            onClick={addGroupBy}
                            disabled={!hasQueryFields}
                          >
                            + Add
                          </button>
                        </div>

                        {groupBy.length === 0 ? (
                          <div className="jdx-empty">
                            <strong>No GROUP BY fields</strong>
                            <span>Use this when the report should summarize rows by one or more dimensions.</span>
                          </div>
                        ) : (
                          <div className="jdx-rule-list">
                            {groupBy.map((field, index) => (
                              <div
                                className="jdx-inline-row jdx-groupby-row"
                                key={`group_${index}`}
                              >
                                <span className="jdx-index">
                                  {index + 1}
                                </span>

                                <select
                                  value={field}
                                  onChange={(event) =>
                                    updateGroupBy(
                                      index,
                                      event.target.value
                                    )
                                  }
                                >
                                  {availableQueryFields.map(
                                    (item) => (
                                      <option
                                        key={item.value}
                                        value={item.value}
                                      >
                                        {item.label}
                                      </option>
                                    )
                                  )}
                                </select>

                                <button
                                  type="button"
                                  className="jdx-icon-button danger"
                                  onClick={() =>
                                    removeGroupBy(index)
                                  }
                                  title="Remove group"
                                >
                                  ×
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}

                    {feature.key === "aggregation" && (
                      <>
                        <div className="jdx-feature-toolbar">
                          <span>Add summary functions to the query.</span>
                          <button
                            type="button"
                            className="jdx-btn small"
                            onClick={addAggregation}
                            disabled={!hasQueryFields}
                          >
                            + Add
                          </button>
                        </div>

                        {aggregations.length === 0 ? (
                          <div className="jdx-empty">
                            <strong>No aggregations configured</strong>
                            <span>Add COUNT, SUM, AVG, MIN or MAX.</span>
                          </div>
                        ) : (
                          <div className="jdx-rule-list">
                            {aggregations.map(
                              (aggregation, index) => (
                                <div
                                  className="jdx-inline-row aggregation jdx-aggregation-row"
                                  key={aggregation.id}
                                >
                                  <span className="jdx-index">
                                    {index + 1}
                                  </span>

                                  <select
                                    value={aggregation.field}
                                    onChange={(event) =>
                                      updateAggregation(
                                        aggregation.id,
                                        "field",
                                        event.target.value
                                      )
                                    }
                                  >
                                    {availableQueryFields.map(
                                      (item) => (
                                        <option
                                          key={item.value}
                                          value={item.value}
                                        >
                                          {item.label}
                                        </option>
                                      )
                                    )}
                                  </select>

                                  <select
                                    value={aggregation.function}
                                    onChange={(event) =>
                                      updateAggregation(
                                        aggregation.id,
                                        "function",
                                        event.target.value
                                      )
                                    }
                                  >
                                    <option value="COUNT">
                                      COUNT
                                    </option>
                                    <option value="SUM">SUM</option>
                                    <option value="AVG">AVG</option>
                                    <option value="MIN">MIN</option>
                                    <option value="MAX">MAX</option>
                                  </select>

                                  <button
                                    type="button"
                                    className="jdx-icon-button danger"
                                    onClick={() =>
                                      removeAggregation(
                                        aggregation.id
                                      )
                                    }
                                    title="Remove aggregation"
                                  >
                                    ×
                                  </button>
                                </div>
                              )
                            )}
                          </div>
                        )}
                      </>
                    )}

                    {feature.key === "calculated" && (
                      <>
                        <div className="jdx-feature-toolbar">
                          <span>Create derived fields from existing fields or values.</span>
                          <button
                            type="button"
                            className="jdx-btn small"
                            onClick={addCalculatedColumn}
                            disabled={!hasQueryFields}
                          >
                            + Add
                          </button>
                        </div>

                        {calculatedColumns.length === 0 ? (
                          <div className="jdx-empty">
                            <strong>No calculated columns</strong>
                            <span>Add a formula-style output field when the report needs a derived value.</span>
                          </div>
                        ) : (
                          <div className="jdx-rule-list">
                            {calculatedColumns.map(
                              (item, index) => (
                                <div
                                  className="jdx-rule"
                                  key={item.id}
                                >
                                  <div className="jdx-rule-top">
                                    <span>
                                      Calculated field {index + 1}
                                    </span>
                                    <button
                                      type="button"
                                      className="jdx-icon-button danger"
                                      onClick={() =>
                                        removeCalculatedColumn(
                                          item.id
                                        )
                                      }
                                      title="Remove calculated column"
                                    >
                                      ×
                                    </button>
                                  </div>

                                  <div className="jdx-calculated-grid">
                                    <div className="jdx-control">
                                      <label>Column Name</label>
                                      <input
                                        value={item.alias}
                                        placeholder="Calculated_Total"
                                        onChange={(event) =>
                                          updateCalculatedColumn(
                                            item.id,
                                            "alias",
                                            event.target.value
                                          )
                                        }
                                      />
                                    </div>

                                    <div className="jdx-control">
                                      <label>Left Field</label>
                                      <select
                                        value={item.left_field}
                                        onChange={(event) =>
                                          updateCalculatedColumn(
                                            item.id,
                                            "left_field",
                                            event.target.value
                                          )
                                        }
                                      >
                                        {availableQueryFields.map(
                                          (field) => (
                                            <option
                                              key={field.value}
                                              value={field.value}
                                            >
                                              {field.label}
                                            </option>
                                          )
                                        )}
                                      </select>
                                    </div>

                                    <div className="jdx-control">
                                      <label>Operation</label>
                                      <select
                                        value={item.operation}
                                        onChange={(event) =>
                                          updateCalculatedColumn(
                                            item.id,
                                            "operation",
                                            event.target.value
                                          )
                                        }
                                      >
                                        <option value="ADD">
                                          ADD (+)
                                        </option>
                                        <option value="SUBTRACT">
                                          SUBTRACT (-)
                                        </option>
                                        <option value="MULTIPLY">
                                          MULTIPLY (×)
                                        </option>
                                        <option value="DIVIDE">
                                          DIVIDE (÷)
                                        </option>
                                        <option value="CONCAT">
                                          CONCAT
                                        </option>
                                        <option value="IF_NULL">
                                          IF NULL
                                        </option>
                                        <option value="COALESCE">
                                          COALESCE
                                        </option>
                                      </select>
                                    </div>

                                    <div className="jdx-control">
                                      <label>Right Field</label>
                                      <select
                                        value={item.right_field}
                                        onChange={(event) =>
                                          updateCalculatedColumn(
                                            item.id,
                                            "right_field",
                                            event.target.value
                                          )
                                        }
                                      >
                                        <option value="">
                                          Use fixed value
                                        </option>
                                        {availableQueryFields.map(
                                          (field) => (
                                            <option
                                              key={field.value}
                                              value={field.value}
                                            >
                                              {field.label}
                                            </option>
                                          )
                                        )}
                                      </select>
                                    </div>

                                    <div className="jdx-control">
                                      <label>Fixed Value</label>
                                      <input
                                        value={item.right_value}
                                        disabled={Boolean(
                                          item.right_field
                                        )}
                                        placeholder="Optional"
                                        onChange={(event) =>
                                          updateCalculatedColumn(
                                            item.id,
                                            "right_value",
                                            event.target.value
                                          )
                                        }
                                      />
                                    </div>
                                  </div>
                                </div>
                              )
                            )}
                          </div>
                        )}
                      </>
                    )}

                    {feature.key === "sorting" && (
                      <>
                        <div className="jdx-feature-toolbar">
                          <span>Rules are applied in the order shown.</span>
                          <button
                            type="button"
                            className="jdx-btn small"
                            onClick={addSort}
                            disabled={!hasQueryFields}
                          >
                            + Add
                          </button>
                        </div>

                        {sorts.length === 0 ? (
                          <div className="jdx-empty">
                            <strong>No sorting configured</strong>
                            <span>Add a field and choose ascending or descending order.</span>
                          </div>
                        ) : (
                          <div className="jdx-rule-list">
                            {sorts.map((sort, index) => (
                              <div
                                className="jdx-inline-row jdx-sort-row"
                                key={sort.id}
                                style={{
                                  display: "grid",
                                  gridTemplateColumns: "28px minmax(0, 1fr) 82px 40px",
                                  gap: "8px",
                                  alignItems: "center",
                                  width: "100%",
                                  minWidth: 0,
                                  boxSizing: "border-box",
                                }}
                              >
                                <span className="jdx-index">
                                  {index + 1}
                                </span>

                                <select
                                  style={{
                                    display: "block",
                                    width: "100%",
                                    minWidth: 0,
                                    maxWidth: "100%",
                                    height: 40,
                                    minHeight: 40,
                                    boxSizing: "border-box",
                                  }}
                                  value={sort.field}
                                  onChange={(event) =>
                                    updateSort(
                                      sort.id,
                                      "field",
                                      event.target.value
                                    )
                                  }
                                >
                                  {availableQueryFields.map(
                                    (field) => (
                                      <option
                                        key={field.value}
                                        value={field.value}
                                      >
                                        {field.label}
                                      </option>
                                    )
                                  )}
                                </select>

                                <select
                                  style={{
                                    display: "block",
                                    width: "100%",
                                    minWidth: 0,
                                    maxWidth: "100%",
                                    height: 40,
                                    minHeight: 40,
                                    boxSizing: "border-box",
                                  }}
                                  value={sort.direction}
                                  onChange={(event) =>
                                    updateSort(
                                      sort.id,
                                      "direction",
                                      event.target.value
                                    )
                                  }
                                >
                                  <option value="ASC">
                                    ASC
                                  </option>
                                  <option value="DESC">
                                    DESC
                                  </option>
                                </select>

                                <button
                                  type="button"
                                  className="jdx-icon-button danger"
                                  onClick={() =>
                                    removeSort(sort.id)
                                  }
                                  title="Remove sort"
                                >
                                  ×
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </section>
            ))}
          </aside>

          {/* ===================================================
              RIGHT — QUERY CANVAS
              =================================================== */}
          <main className="jdx-canvas">
        {/* =====================================================
            CONNECT DATASETS — ROW 2
            Existing datasets come from Data Sources. This section
            lets the user review and modify reporting datasets.
            ===================================================== */}
        <section className="jdx-card jdx-connect-datasets-section">
          <div className="jdx-canvas-header jdx-connect-datasets-header">
            <div className="jdx-canvas-title">
              <span className="jdx-eyebrow">REPORTING DATASETS</span>
              <h3>Select Dataset</h3>
              <p>
                Datasets already added in Data Sources remain available here.
                Review the reporting datasets already added in Data Sources and choose the output fields for this report.
              </p>
            </div>

            <div className="jdx-connect-datasets-header-actions">
              <div className="jdx-canvas-stats">
                <strong>{datasets.length}</strong>
                <span>datasets available</span>
              </div>
            </div>
          </div>

          {datasets.length === 0 ? (
            <div className="jdx-empty jdx-dataset-empty">
              <strong>No reporting datasets available</strong>
              <span>
                Add tables or collections from the Data Sources manager.
                Reporting datasets are synchronized here automatically.
              </span>
            </div>
          ) : (
            <div className="jdx-connect-dataset-list">
              {visibleDatasets.map((dataset, index) => {
                const selected = selectedFields[dataset.id] || [];
                const fields = dataset.columns || [];
                const expanded = expandedDatasets[dataset.id] ?? false;
                const filteredFields = getFilteredFields(dataset);
                const connection = resolveDatasetConnection(dataset);
                const connectionName =
                  dataset.connection_name || connection?.name || "Saved Connection";
                const sourceType = String(
                  dataset.source_type || dataset.sourceType || connection?.source_type || ""
                ).toUpperCase();
                const databaseName = dataset.database || dataset.schema || "";
                const objectName = getDatasetShortName(dataset);

                return (
                  <article
                    className={`jdx-connect-dataset-row ${expanded ? "expanded" : ""}`}
                    key={dataset.id}
                  >
                    <div className="jdx-connect-dataset-row-head">
                      <button
                        type="button"
                        className="jdx-connect-dataset-row-toggle"
                        onClick={() => toggleDatasetExpanded(dataset.id)}
                        aria-expanded={expanded}
                        disabled={!fields.length}
                      >
                        <span className="jdx-connect-dataset-index">
                          {String.fromCharCode(65 + index)}
                        </span>

                        <span className="jdx-connect-dataset-info">
                          <strong>{objectName}</strong>
                          <small>
                            {connectionName} · {databaseName} · {fields.length} columns
                          </small>
                        </span>

                        <span className="jdx-connect-dataset-status">
                          <b>{selected.length}</b>
                          <span>selected</span>
                        </span>

                        <span className="jdx-chevron" aria-hidden="true">
                          {expanded ? "▾" : "▸"}
                        </span>
                      </button>

                    </div>

                    {expanded && (
                      <div className="jdx-connect-dataset-body">
                        <div className="jdx-connect-dataset-meta">
                          <div>
                            <span>{sourceType || "DATABASE"}</span>
                            <span>{databaseName || "Schema not specified"}</span>
                            <span>{objectName}</span>
                          </div>

                          <div className="jdx-dataset-tool-links">
                            <button
                              type="button"
                              className="jdx-link"
                              onClick={() => selectAllFields(dataset)}
                              disabled={configurationLocked || !fields.length}
                            >
                              All
                            </button>
                            <button
                              type="button"
                              className="jdx-link"
                              onClick={() => clearDatasetFields(dataset.id)}
                              disabled={configurationLocked || !selected.length}
                            >
                              Clear
                            </button>
                          </div>
                        </div>

                        <div className="jdx-connect-dataset-toolbar">
                          <input
                            className="jdx-search"
                            placeholder="Search output columns..."
                            value={datasetSearch[dataset.id] || ""}
                            onChange={(event) =>
                              setDatasetSearch((current) => ({
                                ...current,
                                [dataset.id]: event.target.value,
                              }))
                            }
                            disabled={configurationLocked}
                          />
                          <span>
                            {selected.length} of {fields.length} selected for output
                          </span>
                        </div>

                        {filteredFields.length === 0 ? (
                          <div className="jdx-empty">
                            <strong>No columns available</strong>
                            <span>
                              The selected reporting dataset does not currently
                              expose any columns.
                            </span>
                          </div>
                        ) : (
                          <div className="jdx-connect-dataset-fields">
                            {filteredFields.map((rawField) => {
                              const field = getColumnName(rawField);
                              const isSelected = selected.includes(field);

                              return (
                                <button
                                  type="button"
                                  className={`jdx-connect-field ${
                                    isSelected ? "selected" : ""
                                  }`}
                                  key={`${dataset.id}-${field}`}
                                  draggable={!configurationLocked}
                                  onDragStart={() =>
                                    startDragField(dataset.id, field)
                                  }
                                  onClick={() => toggleField(dataset.id, field)}
                                  disabled={configurationLocked}
                                  title="Click to include in output. Drag to a JOIN field."
                                >
                                  <span className="jdx-connect-field-check">
                                    {isSelected ? "✓" : "○"}
                                  </span>
                                  <span className="jdx-connect-field-name">
                                    {getSemanticFieldLabel(dataset, field)}
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        )}

                        <div className="jdx-selected-note">
                          {selected.length
                            ? `${selected.length} field${
                                selected.length === 1 ? "" : "s"
                              } selected for the final report output`
                            : "No output fields selected from this dataset"}
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}

          {datasets.length > MAX_VISIBLE_DATASETS && (
            <div className="jdx-connect-datasets-limit-note">
              Showing the first {MAX_VISIBLE_DATASETS} datasets. Additional
              datasets remain managed in Data Sources.
            </div>
          )}
        </section>



            {/* =================================================
                QUERY PREVIEW
                ================================================= */}
            <section className="jdx-card jdx-preview">
              <div className="jdx-preview-header">
                <div className="jdx-preview-title">
                  <span className="jdx-eyebrow">Query Result</span>
                  <h3>Live Preview</h3>
                  <p>
                    Live Preview is generated when a configuration is
                    applied. Refresh here only after Apply.
                  </p>
                </div>

                <div className="jdx-preview-header-actions">
                  {result && (
                    <div className="jdx-preview-meta">
                      <strong>{result.returned_rows || 0}</strong>
                      <span>rows returned</span>
                    </div>
                  )}

                  <button
                    type="button"
                    className="jdx-btn"
                    onClick={refreshLivePreview}
                    disabled={
                      loading ||
                      !configurationLocked ||
                      !isAppliedConfigurationCurrent
                    }
                  >
                    {loading ? "Refreshing..." : "↻ Refresh Preview"}
                  </button>
                </div>
              </div>

              {!result ? (
                <div className="jdx-preview-empty">
                  <div className="jdx-preview-empty-icon">▤</div>
                  <strong>No preview generated yet</strong>
                  <span>
                    Select output fields, add at least one JOIN and click
                    Apply Configuration.
                  </span>
                </div>
              ) : (result.rows || []).length === 0 ? (
                <div className="jdx-preview-empty">
                  <div className="jdx-preview-empty-icon">∅</div>
                  <strong>Query executed with no rows</strong>
                  <span>
                    The query was successful, but no matching records were
                    returned.
                  </span>
                </div>
              ) : (
                <div className="jdx-result-wrap">
                  <VirtualizedTable className="jdx-result-wrap" tableClassName="jdx-result-table" rows={result.rows || []} columns={result.columns || []} viewportHeight={420} rowHeight={32} columnKey={(column) => column} renderHeader={(column) => column} renderCell={(row, column) => getResultCellValue(row[column])} />
                  <div className="jdx-preview-pagination" style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,padding:"8px 10px",borderTop:"1px solid #e9eef5",fontSize:8,color:"#667085"}}>
                    <span>Showing {(Number(result.page_offset || 0) + 1).toLocaleString()}–{(Number(result.page_offset || 0) + (result.rows || []).length).toLocaleString()} of {Number(result.total_rows || 0).toLocaleString()}</span>
                    <div style={{display:"flex",gap:6}}>
                      <button type="button" className="jdx-btn small" onClick={() => void loadPreviewPage(previewPage - 1)} disabled={previewPageLoading || previewPage === 0}>Previous</button>
                      <button type="button" className="jdx-btn small" onClick={() => void loadPreviewPage(previewPage + 1)} disabled={previewPageLoading || !result.has_more}>Next</button>
                    </div>
                  </div>
                </div>
              )}
            </section>
          </main>
        </div>
        </fieldset>


      </div>
    </>
  );
}
