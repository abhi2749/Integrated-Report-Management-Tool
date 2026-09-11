from __future__ import annotations

import io
import json
import math
from collections import defaultdict
from typing import Any

from execution_manager import EXECUTION_MANAGER


EXCEL_MAX_ROWS = 1_048_576


def _excel_dependencies():
    try:
        from openpyxl import Workbook
        from openpyxl.chart import BarChart, LineChart, PieChart, Reference
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Excel export requires openpyxl. Install it with: python -m pip install openpyxl"
        ) from exc
    return Workbook, BarChart, LineChart, PieChart, Reference, Font, PatternFill, Alignment, get_column_letter


def _pdf_dependencies():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
        from reportlab.graphics.shapes import Drawing, Rect, String, Circle, PolyLine
        from reportlab.graphics.charts.barcharts import VerticalBarChart
        from reportlab.graphics.charts.linecharts import HorizontalLineChart
        from reportlab.graphics.charts.piecharts import Pie
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PDF export requires reportlab. Install it with: python -m pip install reportlab"
        ) from exc
    return (colors, landscape, A4, getSampleStyleSheet, ParagraphStyle, mm,
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
            KeepTogether, Drawing, Rect, String, Circle, PolyLine,
            VerticalBarChart, HorizontalLineChart, Pie)


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    try:
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        value = float(text)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _safe(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _result_from_job(job: dict[str, Any]) -> dict[str, Any]:
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    if result.get("columns") or result.get("rows"):
        return result
    job_id = job.get("id") or job.get("execution_job_id")
    if job_id:
        live = EXECUTION_MANAGER.get(str(job_id)) or {}
        live_result = live.get("result") if isinstance(live.get("result"), dict) else {}
        columns = live.get("result_columns") or live_result.get("columns") or []
        total_rows = live.get("result_total_rows") or live_result.get("total_rows") or live.get("rows") or 0
        return {
            "columns": list(columns) if isinstance(columns, list) else [],
            "total_rows": int(total_rows or 0),
            "returned_rows": int(live.get("result_returned_rows") or live_result.get("returned_rows") or 0),
            "result_available": bool(live.get("result_available") or total_rows),
        }
    return result


def _result_rows(job: dict[str, Any]):
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    rows = result.get("rows")
    if isinstance(rows, list):
        return iter(rows)
    job_id = job.get("id") or job.get("execution_job_id")
    if job_id:
        rows = EXECUTION_MANAGER.iter_result_rows(str(job_id))
        return rows if rows is not None else iter(())
    return iter(())


def _result_columns(job: dict[str, Any]) -> list[str]:
    result = _result_from_job(job)
    columns = result.get("columns") if isinstance(result.get("columns"), list) else []
    return [str(column) for column in columns]


def _result_total_rows(job: dict[str, Any]) -> int:
    result = _result_from_job(job)
    rows = result.get("rows")
    if isinstance(rows, list):
        return int(result.get("total_rows") or len(rows))
    return int(result.get("total_rows") or job.get("result_total_rows") or job.get("rows") or 0)


def _sample_rows(job: dict[str, Any], limit: int = 5000) -> list[dict[str, Any]]:
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    rows = result.get("rows")
    if isinstance(rows, list):
        return rows[:limit]
    return [row for _, row in zip(range(limit), _result_rows(job)) if isinstance(row, dict)]


def _widget_points(widget: dict[str, Any], rows: list[dict[str, Any]]) -> list[tuple[str, float]]:
    x_field = widget.get("x")
    y_field = widget.get("y")
    grouped: dict[str, float] = defaultdict(float)
    for row in rows:
        label = _safe(row.get(x_field)) if x_field else ""
        value = _num(row.get(y_field)) if y_field else None
        if value is None:
            continue
        grouped[label] += value
    points = list(grouped.items())
    return points[:30]


def _kpi_value(widget: dict[str, Any], rows: list[dict[str, Any]]) -> float | None:
    field = widget.get("y")
    values = [_num(row.get(field)) for row in rows] if field else []
    values = [v for v in values if v is not None]
    return sum(values) if values else None


def build_dashboard_xlsx(item: dict[str, Any], job: dict[str, Any]) -> bytes:
    (Workbook, BarChart, LineChart, PieChart, Reference, Font, PatternFill, Alignment, get_column_letter) = _excel_dependencies()
    definition = item.get("definition") if isinstance(item.get("definition"), dict) else {}
    columns = _result_columns(job)
    total_rows = _result_total_rows(job)
    sample_rows = _sample_rows(job, 5000)
    widgets = definition.get("widgets") if isinstance(definition.get("widgets"), list) else []
    filters = definition.get("filters") if isinstance(definition.get("filters"), list) else []
    disk_backed = not isinstance((job.get("result") or {}).get("rows"), list) and bool(job.get("id") or job.get("execution_job_id"))

    if disk_backed or total_rows + 1 > EXCEL_MAX_ROWS:
        from openpyxl.cell import WriteOnlyCell
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("Dashboard")
        ws.append([item.get("name") or "Dashboard"])
        ws.append([f"Owner: {item.get('owner_username', '')}    Version: {item.get('version', 1)}    Rows: {total_rows:,}    Columns: {len(columns):,}"])
        ws.append(["Filters: " + ("; ".join(_safe(f.get("field")) + " " + _safe(f.get("operator")) + " " + _safe(f.get("value")) for f in filters) if filters else "None")])
        ws.append([])
        ws.append(["Large-result export: dashboard visualizations use a bounded 5,000-row sample; the Data sheets contain the complete ResultStore-backed result."])
        for widget in widgets:
            ws.append([_safe(widget.get("title")) or "Widget", _safe(widget.get("type"))])
            if _safe(widget.get("type")).lower() == "kpi":
                value = _kpi_value(widget, sample_rows)
                ws.append(["Sample KPI value", "—" if value is None else value])
        row_iter = _result_rows(job)
        sheet_index = 1
        data = wb.create_sheet("Data")
        data.append(columns)
        data_rows = 0
        for row in row_iter:
            if data_rows >= EXCEL_MAX_ROWS - 1:
                sheet_index += 1
                data = wb.create_sheet(f"Data_{sheet_index}")
                data.append(columns)
                data_rows = 0
            data.append([_safe(row.get(column)) if isinstance(row, dict) else "" for column in columns])
            data_rows += 1
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    wb = Workbook()
    ws = wb.active
    ws.title = "Dashboard"
    ws.freeze_panes = "A4"
    ws["A1"] = item.get("name") or "Dashboard"
    ws["A1"].font = Font(size=20, bold=True)
    ws["A2"] = f"Owner: {item.get('owner_username', '')}    Version: {item.get('version', 1)}    Rows: {total_rows:,}    Columns: {len(columns):,}"
    ws["A2"].font = Font(size=10, italic=True)
    ws["A3"] = "Filters: " + ("; ".join(_safe(f.get("field")) + " " + _safe(f.get("operator")) + " " + _safe(f.get("value")) for f in filters) if filters else "None")
    ws["A3"].alignment = Alignment(wrap_text=True)

    row_cursor = 5
    for idx, widget in enumerate(widgets, start=1):
        wtype = _safe(widget.get("type", "widget"))
        title = _safe(widget.get("title")) or f"Widget {idx}"
        ws.cell(row_cursor, 1, title).font = Font(size=13, bold=True)
        ws.cell(row_cursor + 1, 1, f"Type: {wtype}")
        if wtype.lower() == "kpi":
            value = _kpi_value(widget, sample_rows)
            ws.cell(row_cursor + 2, 1, "—" if value is None else value).font = Font(size=18, bold=True)
            ws.cell(row_cursor + 3, 1, _safe(widget.get("y")))
            row_cursor += 6
            continue
        if wtype.lower() == "table":
            ws.cell(row_cursor + 2, 1, f"Table widget uses the Data sheet ({total_rows:,} rows).")
            row_cursor += 5
            continue
        points = _widget_points(widget, sample_rows)
        if not points:
            ws.cell(row_cursor + 2, 1, "No numeric data available for this visualization.")
            row_cursor += 5
            continue
        data_col, cat_col, start = 1, 2, row_cursor + 2
        ws.cell(start, data_col, "Category")
        ws.cell(start, cat_col, "Value")
        for offset, (label, value) in enumerate(points, start=1):
            ws.cell(start + offset, data_col, label)
            ws.cell(start + offset, cat_col, value)
        chart = PieChart() if wtype.lower() == "pie" else LineChart() if wtype.lower() == "line" else BarChart()
        if wtype.lower() == "pie":
            chart.add_data(Reference(ws, min_col=cat_col, min_row=start, max_row=start + len(points)), titles_from_data=True)
            chart.set_categories(Reference(ws, min_col=data_col, min_row=start + 1, max_row=start + len(points)))
        else:
            chart.add_data(Reference(ws, min_col=cat_col, min_row=start, max_row=start + len(points)), titles_from_data=True)
            chart.set_categories(Reference(ws, min_col=data_col, min_row=start + 1, max_row=start + len(points)))
            chart.height, chart.width = 7, 12
        chart.title = title
        ws.add_chart(chart, f"D{row_cursor}")
        row_cursor += 20

    data = wb.create_sheet("Data")
    for col_idx, column in enumerate(columns, start=1):
        cell = data.cell(1, col_idx, column)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="EAF2FF")
    max_data_rows = EXCEL_MAX_ROWS - 1
    for row_idx, row in enumerate(_result_rows(job), start=2):
        if row_idx > EXCEL_MAX_ROWS:
            break
        for col_idx, column in enumerate(columns, start=1):
            data.cell(row_idx, col_idx, _safe(row.get(column)) if isinstance(row, dict) else "")
    data.freeze_panes = "A2"
    data.auto_filter.ref = f"A1:{get_column_letter(max(1, len(columns)))}{min(total_rows, max_data_rows) + 1}"
    for col_idx, column in enumerate(columns, start=1):
        data.column_dimensions[get_column_letter(col_idx)].width = min(40, max(10, len(str(column)) + 2))

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

def _pdf_chart(widget: dict[str, Any], rows: list[dict[str, Any]], width=None, height=None):
    (colors, landscape, A4, getSampleStyleSheet, ParagraphStyle, mm,
     SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
     KeepTogether, Drawing, Rect, String, Circle, PolyLine,
     VerticalBarChart, HorizontalLineChart, Pie) = _pdf_dependencies()
    if width is None:
        width = 125 * mm
    if height is None:
        height = 65 * mm
    drawing = Drawing(width, height)
    title = _safe(widget.get("title")) or "Visualization"
    drawing.add(String(4, height - 10, title, fontSize=9, fontName="Helvetica-Bold"))
    points = _widget_points(widget, rows)
    if not points:
        drawing.add(String(4, height / 2, "No numeric data", fontSize=9))
        return drawing
    values = [v for _, v in points]
    labels = [x[:16] for x, _ in points]
    kind = _safe(widget.get("type")).lower()
    if kind == "pie":
        pie = Pie()
        pie.x = width / 2 - 25 * mm
        pie.y = 5
        pie.width = 45 * mm
        pie.height = 45 * mm
        pie.data = [max(v, 0) for v in values]
        pie.labels = labels
        drawing.add(pie)
        return drawing
    chart_w = width - 18
    chart_h = height - 25
    if kind == "line":
        chart = HorizontalLineChart()
        chart.x = 8
        chart.y = 8
        chart.width = chart_w
        chart.height = chart_h
        chart.data = [values]
        chart.categoryAxis.categoryNames = labels
        chart.valueAxis.valueMin = min(0, min(values))
        chart.valueAxis.valueMax = max(values) if max(values) else 1
        chart.lines[0].strokeWidth = 2
        drawing.add(chart)
    else:
        chart = VerticalBarChart()
        chart.x = 8
        chart.y = 8
        chart.width = chart_w
        chart.height = chart_h
        chart.data = [values]
        chart.categoryAxis.categoryNames = labels
        chart.valueAxis.valueMin = min(0, min(values))
        chart.valueAxis.valueMax = max(values) if max(values) else 1
        chart.barSpacing = 2
        drawing.add(chart)
    return drawing


def build_dashboard_pdf(item: dict[str, Any], job: dict[str, Any]) -> bytes:
    (colors, landscape, A4, getSampleStyleSheet, ParagraphStyle, mm,
     SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
     KeepTogether, Drawing, Rect, String, Circle, PolyLine,
     VerticalBarChart, HorizontalLineChart, Pie) = _pdf_dependencies()
    definition = item.get("definition") if isinstance(item.get("definition"), dict) else {}
    result = _result_from_job(job)
    columns = _result_columns(job)
    total_rows = _result_total_rows(job)
    rows = _sample_rows(job, 5000)
    widgets = definition.get("widgets") if isinstance(definition.get("widgets"), list) else []
    filters = definition.get("filters") if isinstance(definition.get("filters"), list) else []

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("DashboardTitle", parent=styles["Title"], fontSize=20, leading=24, spaceAfter=6)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, leading=10)
    story = [Paragraph(_safe(item.get("name")) or "Dashboard", title), Paragraph(f"Owner: {_safe(item.get('owner_username'))} · Version: {_safe(item.get('version', 1))} · {total_rows:,} rows · {len(columns):,} columns", small), Spacer(1, 5 * mm)]
    filter_text = "Filters: " + ("; ".join(_safe(f.get("field")) + " " + _safe(f.get("operator")) + " " + _safe(f.get("value")) for f in filters) if filters else "None")
    story.append(Paragraph(filter_text, small))
    story.append(Spacer(1, 5 * mm))

    for start in range(0, len(widgets), 2):
        row_flow = []
        for widget in widgets[start:start + 2]:
            wtype = _safe(widget.get("type")).lower()
            if wtype == "kpi":
                value = _kpi_value(widget, rows)
                content = [[Paragraph(_safe(widget.get("title")) or "KPI", styles["Heading3"])], [Paragraph("—" if value is None else f"{value:,.2f}", title)], [Paragraph(_safe(widget.get("y")), small)]]
                t = Table(content, colWidths=[125 * mm], rowHeights=[8 * mm, 22 * mm, 8 * mm])
                t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 1), (-1, 1), "CENTER")]))
                row_flow.append(t)
            elif wtype == "table":
                drawing = Drawing(125 * mm, 65 * mm)
                drawing.add(String(4, 52 * mm, _safe(widget.get("title")) or "Table", fontSize=9, fontName="Helvetica-Bold"))
                drawing.add(Rect(2, 8, 120 * mm, 38 * mm, strokeColor=colors.HexColor("#D0D5DD"), fillColor=colors.white))
                drawing.add(String(7, 36 * mm, f"Data table: {len(rows):,} rows × {len(columns):,} columns", fontSize=8))
                drawing.add(String(7, 29 * mm, "Full raw result is included in the Excel export.", fontSize=7))
                row_flow.append(drawing)
            else:
                row_flow.append(_pdf_chart(widget, rows))
        while len(row_flow) < 2:
            row_flow.append(Spacer(125 * mm, 1))
        outer = Table([row_flow], colWidths=[130 * mm, 130 * mm])
        outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
        story.append(outer)
        story.append(Spacer(1, 6 * mm))

    story.append(PageBreak())
    story.append(Paragraph("Dashboard Data", styles["Heading2"]))
    display_cols = columns[:12]
    data = [[_safe(c) for c in display_cols]] + [[_safe(r.get(c))[:50] for c in display_cols] for r in rows[:100]]
    if data:
        t = Table(data, repeatRows=1, colWidths=[21 * mm] * len(display_cols))
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2FF")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 5.5), ("GRID", (0, 0), (-1, -1), .2, colors.HexColor("#D0D5DD"))]))
        story.append(t)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Dashboard export contains the dashboard definition, visual widgets and a readable data section. Raw complete result data is available in the Excel export. PDF tables are intentionally paginated for readability.", small))
    doc.build(story)
    return out.getvalue()


def build_dashboard_package(item: dict[str, Any], job: dict[str, Any]) -> bytes:
    """Build a portable ZIP while reading raw rows from the durable result store."""
    import zipfile

    dashboard_id = _safe(item.get("id")) or "dashboard"
    columns = _result_columns(job)
    total_rows = _result_total_rows(job)
    json_payload = json.dumps({"success": True, "dashboard": item}, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    csv_buffer = io.StringIO(newline="")
    import csv
    writer = csv.writer(csv_buffer)
    writer.writerow(columns)
    for row in _result_rows(job):
        writer.writerow([_safe(row.get(column)) if isinstance(row, dict) else "" for column in columns])
    csv_payload = csv_buffer.getvalue().encode("utf-8-sig")
    xlsx_payload = build_dashboard_xlsx(item, job)
    pdf_payload = build_dashboard_pdf(item, job)

    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"dashboard-{dashboard_id}.json", json_payload)
        archive.writestr(f"dashboard-{dashboard_id}.csv", csv_payload)
        archive.writestr(f"dashboard-{dashboard_id}.xlsx", xlsx_payload)
        archive.writestr(f"dashboard-{dashboard_id}.pdf", pdf_payload)
    return package.getvalue()

