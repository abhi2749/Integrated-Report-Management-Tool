from __future__ import annotations

from production_security import validate_runtime
from logging_config import audit_event, configure_logging, get_logger, AUDIT_LOG_FILE
from backup_manager import create_backup, list_backups, validate_backup, validate_and_stage_backup, apply_retention, copy_to_external
from large_data_policy import POLICY
from query_pushdown import build_plan
from query_model import QueryDefinition
from semantic_model import SemanticModel
from semantic_registry import list_semantic_models, get_semantic_model, save_semantic_model, delete_semantic_model
from semantic_metadata_service import build_semantic_model, dataset_semantic_payload, consistency_report
from query_planner import plan_query
from execution_contract import prepare_execution
from execution_engine import execute_prepared_execution
from query_contract import canonical_query_from_payload
from execution_manager import EXECUTION_MANAGER
from export_manager import ExportJobManager
from streaming import stream_fetchmany
from export_service import csv_stream, json_stream, csv_stream_rows, json_stream_rows, safe_export_filename
from report_export_service import write_csv as write_report_csv, write_json as write_report_json, write_xlsx as write_report_xlsx, write_pdf as write_report_pdf, write_package as write_report_package
from dashboard_export import build_dashboard_xlsx, build_dashboard_pdf
from fastapi import Depends, FastAPI, HTTPException, Request, File, UploadFile
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse, StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, TableStyle, SimpleDocTemplate, Paragraph
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any
from pathlib import Path
from datetime import datetime, timezone
import json
import csv
import io
import zipfile
import uuid
import os

from config import (
    MAX_PREVIEW_ROWS,
    APP_NAME,
    APP_VERSION,
    APP_DEBUG,
    APP_ENV,
    APP_HOST,
    APP_PORT,
    CORS_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    REPORTS_FILE,
    DATA_DIR,
    MAX_QUERY_ROWS,
    QUERY_TIMEOUT_SECONDS,
    MAX_REQUEST_BODY_MB,
    MAX_JOIN_OPERATIONS,
    LOG_LEVEL,
    QUERY_PUSHDOWN_ENABLED,
)

from services.datasource_service import (
    connector_catalog,
    datasource_test,
    datasource_databases,
    datasource_tables,
    datasource_columns,
    datasource_preview,
    saved_connection_test,
    saved_connection_databases,
    saved_connection_tables,
    saved_connection_columns,
    saved_connection_preview,
)

from connection_registry import list_connections, create_connection, update_connection, delete_connection, get_connection
from dataset_registry import list_datasets, create_dataset, update_dataset, delete_dataset, get_dataset

from database import (
    test_mysql_connection,
    get_mysql_tables,
    get_mysql_columns,
    test_mongodb_connection,
    get_mongodb_collections,
    get_mongodb_fields,
    execute_report_query,
    execute_join_request,
    preview_dataset,
    test_clickhouse_connection,
    get_clickhouse_databases,
    get_clickhouse_tables,
    get_clickhouse_columns,
    get_clickhouse_preview,
)

from services.visualization_service import build_visualization_response, build_visualization_from_row_stream, visualization_fields
from auth_api import get_current_user, router as auth_router
from report_registry import REPORT_REGISTRY
from dashboard_registry import DASHBOARD_REGISTRY
from lineage_service import LINEAGE_REGISTRY, lineage_from_payload
from permissions import require_app_access, has_permission
from auth_api import require_admin
from user_registry import get_user_by_id, list_users
from import_service import IMPORTED_DATA_REGISTRY, import_file, preview_import

from startup_validation import validate_environment
from api_security import public_exception_message

from connection_access import (
    can_access_connection,
    grant_new_connection_to_user,
    public_access_record,
    remove_connection_access,
    require_connection_access,
    set_connection_access,
)

configure_logging(LOG_LEVEL)


@asynccontextmanager
async def application_lifespan(_app: FastAPI):
    """Validate production configuration and gracefully stop workers."""
    validation = validate_environment()
    if not validation["ok"]:
        raise RuntimeError("Invalid application environment: " + "; ".join(validation["errors"]))
    try:
        yield
    finally:
        # Wait for in-flight report workers so shutdown does not leave
        # partially persisted results or orphaned execution threads.
        EXECUTION_MANAGER.shutdown(wait=True)
        EXPORT_MANAGER.shutdown(wait=True)


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Multi-source visual reporting engine with multi-dataset JOINs.",
    debug=APP_DEBUG,
    lifespan=application_lifespan,
)

EXPORT_MANAGER = ExportJobManager(DATA_DIR / "exports")

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    get_logger().exception(
        "Unhandled API exception",
        extra={"audit_data": {"event_type": "error", "request_id": request_id, "method": request.method, "path": request.url.path}},
    )
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error.", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if APP_ENV in {"production", "prod"}:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response


@app.middleware("http")
async def audit_request_middleware(request: Request, call_next):
    response = await call_next(request)
    user = getattr(request.state, "user", None)
    audit_event(
        "api_request",
        user=user if isinstance(user, dict) else None,
        success=response.status_code < 400,
        detail=f"{request.method} {request.url.path}",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
    )
    return response


@app.middleware("http")
async def request_size_guard(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
        except ValueError:
            size = 0
        if MAX_REQUEST_BODY_MB > 0:
            max_bytes = MAX_REQUEST_BODY_MB * 1024 * 1024
            if size > max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "message": "Request payload is too large.",
                    },
                )
    return await call_next(request)


@app.get("/system/capacity", summary="Report Capacity Configuration")
def report_capacity(user: dict = Depends(require_app_access)):
    return {
        "success": True,
        "report_row_limit": MAX_QUERY_ROWS,
        "report_row_limit_mode": "dynamic" if MAX_QUERY_ROWS == 0 else "configured",
        "query_timeout_seconds": QUERY_TIMEOUT_SECONDS,
        "max_request_body_mb": MAX_REQUEST_BODY_MB,
        "large_data_policy": POLICY.summary(),
        "query_pushdown_enabled": QUERY_PUSHDOWN_ENABLED,
        "max_join_operations": MAX_JOIN_OPERATIONS,
        "preview_rows": MAX_PREVIEW_ROWS,
        "visualization_rows": 500,
        "note": (
            "Report processing has no artificial row ceiling when "
            "MAX_QUERY_ROWS=0. Interactive preview/visualization remain "
            "bounded to protect the browser."
        ),
    }



def _prepare_report_query(payload: dict[str, Any]) -> QueryDefinition:
    """Canonicalize and plan a query before it reaches the existing executor."""
    prepared = prepare_execution(payload, planner=plan_query)
    # A value of 0 means unlimited, consistent with the other
    # report-size safety settings.
    if MAX_JOIN_OPERATIONS > 0 and prepared.plan.join_count > MAX_JOIN_OPERATIONS:
        raise ValueError(
            f"Query contains {prepared.plan.join_count} JOIN operations; "
            f"maximum allowed is {MAX_JOIN_OPERATIONS}."
        )
    return prepared.query


def _execute_report_payload(payload: dict[str, Any], cancel_event=None):
    """Prepare once, then execute through the unified execution engine."""
    prepared = prepare_execution(payload, planner=plan_query)
    if MAX_JOIN_OPERATIONS > 0 and prepared.plan.join_count > MAX_JOIN_OPERATIONS:
        raise ValueError(
            f"Query contains {prepared.plan.join_count} JOIN operations; "
            f"maximum allowed is {MAX_JOIN_OPERATIONS}."
        )
    return execute_prepared_execution(prepared, cancel_event=cancel_event)



def _execute_report_with_timeout(request: ReportQueryRequest):
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="report-query") as executor:
        future = executor.submit(
            _execute_report_payload,
            request.model_dump(),
        )
        try:
            return future.result() if QUERY_TIMEOUT_SECONDS <= 0 else future.result(timeout=QUERY_TIMEOUT_SECONDS)
        except FutureTimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail=f"Report query exceeded the {QUERY_TIMEOUT_SECONDS}-second execution limit.",
            ) from exc


@app.post("/admin/backups", summary="Create Application Backup")
def create_application_backup(user: dict = Depends(require_admin)):
    archive = create_backup()
    audit_event(
        "backup_created",
        user=user,
        resource_type="backup",
        resource_id=archive.name,
        detail="Application state backup created.",
    )
    return {"success": True, "backup": {
        "file": archive.name,
        "path": str(archive),
        "size_bytes": archive.stat().st_size,
    }}


@app.post("/admin/backups/recovery-test", summary="Validate and Stage Backup")
def test_application_backup_recovery(
    archive: str,
    user: dict = Depends(require_admin),
):
    archive_path = BACKUP_DIR / Path(archive).name
    try:
        result = validate_and_stage_backup(archive_path)
    except (FileNotFoundError, ValueError, OSError, tarfile.TarError) as exc:
        audit_event(
            "backup_recovery_test",
            user=user,
            success=False,
            resource_type="backup",
            resource_id=archive_path.name,
            detail=str(exc),
        )
        raise HTTPException(status_code=400, detail="Backup recovery validation failed.") from exc

    audit_event(
        "backup_recovery_test",
        user=user,
        success=result["valid"],
        resource_type="backup",
        resource_id=archive_path.name,
        detail="Backup validated and staged without modifying live data.",
    )
    return {"success": True, "recovery_test": result}


@app.post("/admin/backups/retention", summary="Apply Backup Retention")
def apply_backup_retention(user: dict = Depends(require_admin)):
    removed = apply_retention()
    audit_event(
        "backup_retention_applied",
        user=user,
        success=True,
        resource_type="backup",
        detail=f"Removed {len(removed)} old backup(s).",
        removed_count=len(removed),
    )
    return {"success": True, "removed": removed}


@app.post("/admin/backups/external-copy", summary="Copy Backup to External Target")
def copy_backup_external(
    archive: str,
    user: dict = Depends(require_admin),
):
    archive_path = BACKUP_DIR / Path(archive).name
    if not archive_path.exists():
        raise HTTPException(status_code=404, detail="Backup archive not found.")
    try:
        result = copy_to_external(archive_path)
    except Exception as exc:
        audit_event(
            "backup_external_copy",
            user=user,
            success=False,
            resource_type="backup",
            resource_id=archive_path.name,
            detail=str(exc),
        )
        raise HTTPException(status_code=500, detail="External backup copy failed.") from exc
    audit_event(
        "backup_external_copy",
        user=user,
        success=result.get("copied", False),
        resource_type="backup",
        resource_id=archive_path.name,
        detail=result.get("message") or result.get("destination"),
    )
    return {"success": True, "result": result}


@app.get("/admin/backups", summary="List Application Backups")
def list_application_backups(user: dict = Depends(require_admin)):
    return {"success": True, "backups": list_backups()}


@app.get("/admin/audit-log", summary="Read Audit Log")
def read_audit_log(user: dict = Depends(require_admin)):
    audit_file = AUDIT_LOG_FILE
    if not audit_file.exists():
        return {"success": True, "events": []}

    lines = audit_file.read_text(encoding="utf-8").splitlines()
    events = []
    for line in lines[-200:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {"success": True, "events": events}


# ============================================================
# AUTHENTICATION API
# ============================================================
# Step 3D: authentication router remains outside the protected reporting
# routes so login can be performed without an existing access token.
# All existing application/reporting routes below require authentication.
app.include_router(auth_router)


class GenericDataSourceRequest(BaseModel):
    source_type: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None


class GenericDataSourceTableRequest(GenericDataSourceRequest):
    database: str


class GenericDataSourceColumnRequest(GenericDataSourceTableRequest):
    table: str


class GenericDataSourcePreviewRequest(GenericDataSourceColumnRequest):
    sample_limit: int = 25


class MySQLConnection(BaseModel):
    host: str
    port: int
    username: str
    password: str


class MySQLTableRequest(MySQLConnection):
    database: str


class MySQLColumnRequest(MySQLTableRequest):
    table: str


class MongoDBConnection(BaseModel):
    host: str
    port: int
    username: str | None = None
    password: str | None = None


class MongoDBCollectionRequest(MongoDBConnection):
    database: str


class MongoDBFieldRequest(MongoDBCollectionRequest):
    collection: str


class DatasetPreviewRequest(BaseModel):
    source_type: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    database: str
    table: str
    sample_limit: int = 25


class DatasetDefinition(BaseModel):
    id: str
    # Preferred saved-connection reference.
    connection_id: str | None = None

    # Legacy fields remain optional for backward compatibility.
    source_type: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None

    database: str
    table: str | None = None
    object_name: str | None = None
    semantic_dataset_id: str | None = None


class JoinDefinition(BaseModel):
    left_dataset: str
    right_dataset: str
    left_column: str
    right_column: str
    join_type: str = "INNER"


class ReportColumn(BaseModel):
    field: str
    alias: str | None = None


class ReportFilter(BaseModel):
    field: str
    operator: str
    value: Any = None
    logic: str = "AND"


class ReportSort(BaseModel):
    field: str
    direction: str = "ASC"


class ReportAggregation(BaseModel):
    function: str
    field: str
    alias: str | None = None


class CalculatedColumn(BaseModel):
    alias: str
    left_field: str
    operation: str
    right_field: str | None = None
    right_value: Any = None


class SavedDashboard(BaseModel):
    id: str
    name: str
    definition: dict[str, Any]


class DashboardExportRequest(BaseModel):
    name: str = Field(default="Dashboard", min_length=1, max_length=200)
    definition: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class DashboardShareRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)


class SavedReport(BaseModel):
    id: str
    name: str
    definition: dict[str, Any]
    created_at: str | None = None
    updated_at: str | None = None


class SavedConnectionRequest(BaseModel):
    name: str
    source_type: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    status: str = "saved"
    server_version: str = ""


class SavedDatasetRequest(BaseModel):
    name: str | None = None
    connection_id: str
    database: str
    object_name: str
    object_type: str = "table"
    columns: list[dict[str, Any]] = Field(default_factory=list)


class ImportedDatasetUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class VisualizationFieldsRequest(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    column_profiles: list[dict[str, Any]] = Field(default_factory=list)


class VisualizationRequest(BaseModel):
    result: dict[str, Any]
    visualization: str = "table"
    category_field: str | None = None
    value_field: str | None = None
    aggregation: str = "SUM"
    limit: int = 20
    bins: int = 6
    sort_direction: str | None = None


class ClickHouseConnection(BaseModel):
    host: str
    port: int = 8123
    username: str | None = None
    password: str | None = None


class ClickHouseTableRequest(ClickHouseConnection):
    database: str


class ClickHouseColumnRequest(ClickHouseTableRequest):
    table: str


class ReportQueryRequest(BaseModel):
    datasets: list[DatasetDefinition] = Field(default_factory=list)
    joins: list[JoinDefinition] = Field(default_factory=list)
    columns: list[ReportColumn] = Field(default_factory=list)
    filters: list[ReportFilter] = Field(default_factory=list)
    sorts: list[ReportSort] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[ReportAggregation] = Field(default_factory=list)
    calculated_columns: list[CalculatedColumn] = Field(default_factory=list)
    limit: int = 0  # 0 = no application row ceiling


def _report_datasets_for_execution(
    datasets: list[DatasetDefinition],
) -> list[dict[str, Any]]:
    """Normalize report datasets while preserving connection_id."""
    prepared = []

    for dataset in datasets:
        item = dataset.model_dump(exclude_none=True)

        if not item.get("table") and item.get("object_name"):
            item["table"] = item["object_name"]

        prepared.append(item)

    return prepared


@app.get("/")
def home():
    return {"message": "Integrated Report Management Tool Backend is running!"}


@app.get("/health")
def health():
    """Liveness probe: the process is running and serving requests."""
    return {"status": "healthy"}


@app.get("/ready")
def readiness():
    """Readiness probe for load balancers and container orchestrators."""
    data_dir = DATA_DIR
    result_store_path = EXECUTION_MANAGER.result_store.path
    checks = {
        "data_dir": data_dir.is_dir(),
        "data_dir_writable": os.access(data_dir, os.W_OK) if data_dir.is_dir() else False,
        "result_store_parent": result_store_path.parent.is_dir(),
    }
    ready = all(checks.values())
    if not ready:
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}


@app.get("/datasource/connectors", dependencies=[Depends(require_app_access)])
def datasource_connectors():
    """List connector types available to the reporting engine."""
    return connector_catalog()


@app.post("/datasource/test", dependencies=[Depends(require_app_access)])
def datasource_test_endpoint(request: GenericDataSourceRequest):
    return datasource_test(
        source_type=request.source_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
    )


@app.post("/datasource/databases", dependencies=[Depends(require_app_access)])
def datasource_databases_endpoint(request: GenericDataSourceRequest):
    return datasource_databases(
        source_type=request.source_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
    )


@app.post("/datasource/tables", dependencies=[Depends(require_app_access)])
def datasource_tables_endpoint(request: GenericDataSourceTableRequest):
    return datasource_tables(
        source_type=request.source_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        database=request.database,
    )


@app.post("/datasource/columns", dependencies=[Depends(require_app_access)])
def datasource_columns_endpoint(request: GenericDataSourceColumnRequest):
    return datasource_columns(
        source_type=request.source_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        database=request.database,
        table=request.table,
    )


@app.post("/datasource/preview", dependencies=[Depends(require_app_access)])
def datasource_preview_endpoint(request: GenericDataSourcePreviewRequest):
    return datasource_preview(
        source_type=request.source_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        database=request.database,
        table=request.table,
        sample_limit=max(1, int(request.sample_limit)),
    )


@app.get("/datasource/connections")
def saved_connections(user: dict = Depends(require_app_access)):
    connections = [
        item for item in list_connections()
        if can_access_connection(user, item.get("id", ""))
    ]
    return {"success": True, "connections": connections}


@app.post("/datasource/connections")
def create_saved_connection(
    request: SavedConnectionRequest,
    user: dict = Depends(require_app_access),
):
    item = create_connection(request.model_dump())
    grant_new_connection_to_user(item["id"], user)
    return {"success": True, "connection": item}


@app.put("/datasource/connections/{connection_id}", dependencies=[Depends(require_app_access)])
def update_saved_connection(
    connection_id: str,
    request: SavedConnectionRequest,
    user: dict = Depends(require_app_access),
):
    require_connection_access(user, connection_id)
    item = update_connection(connection_id, request.model_dump())
    if not item:
        return {"success": False, "message": "Saved connection not found."}
    return {"success": True, "connection": item}


@app.delete("/datasource/connections/{connection_id}", dependencies=[Depends(require_app_access)])
def delete_saved_connection(
    connection_id: str,
    user: dict = Depends(require_app_access),
):
    require_connection_access(user, connection_id)
    if not delete_connection(connection_id):
        return {"success": False, "message": "Saved connection not found."}
    remove_connection_access(connection_id)
    return {"success": True, "message": "Connection deleted successfully."}


@app.post("/datasource/connections/{connection_id}/test", dependencies=[Depends(require_app_access)])
def test_saved_connection(connection_id: str, user: dict = Depends(require_app_access)):
    require_connection_access(user, connection_id)
    try:
        return saved_connection_test(connection_id)
    except Exception as error:
        return {"success": False, "connection_id": connection_id, "message": str(error)}


@app.get("/datasource/connections/{connection_id}/databases", dependencies=[Depends(require_app_access)])
def saved_connection_database_list(connection_id: str, user: dict = Depends(require_app_access)):
    require_connection_access(user, connection_id)
    try:
        return saved_connection_databases(connection_id)
    except Exception as error:
        return {"success": False, "connection_id": connection_id, "message": str(error), "databases": []}


@app.get("/datasource/connections/{connection_id}/databases/{database}/tables", dependencies=[Depends(require_app_access)])
def saved_connection_table_list(connection_id: str, database: str, user: dict = Depends(require_app_access)):
    require_connection_access(user, connection_id)
    try:
        return saved_connection_tables(connection_id, database)
    except Exception as error:
        return {"success": False, "connection_id": connection_id, "database": database, "message": str(error), "tables": []}


@app.get("/datasource/connections/{connection_id}/databases/{database}/tables/{table}/columns", dependencies=[Depends(require_app_access)])
def saved_connection_column_list(connection_id: str, database: str, table: str, user: dict = Depends(require_app_access)):
    require_connection_access(user, connection_id)
    try:
        return saved_connection_columns(connection_id, database, table)
    except Exception as error:
        return {"success": False, "connection_id": connection_id, "database": database, "table": table, "message": str(error), "columns": []}


class SavedConnectionPreviewRequest(BaseModel):
    database: str
    table: str
    sample_limit: int = 25


@app.post("/datasource/connections/{connection_id}/preview", dependencies=[Depends(require_app_access)])
def saved_connection_table_preview(connection_id: str, request: SavedConnectionPreviewRequest, user: dict = Depends(require_app_access)):
    require_connection_access(user, connection_id)
    try:
        return saved_connection_preview(connection_id, request.database, request.table, max(1, int(request.sample_limit)))
    except Exception as error:
        return {"success": False, "connection_id": connection_id, "database": request.database, "table": request.table, "message": str(error), "rows": [], "columns": []}


class ConnectionAccessRequest(BaseModel):
    mode: str = "all"
    user_ids: list[str] = Field(default_factory=list)


@app.get("/datasource/connections/access", summary="List Connection Access")
def list_connection_access_endpoint(user: dict = Depends(require_admin)):
    return {
        "success": True,
        "access": [public_access_record(item["id"]) for item in list_connections()],
    }


@app.get("/datasource/connections/{connection_id}/access", summary="Get Connection Access")
def get_connection_access_endpoint(
    connection_id: str,
    user: dict = Depends(require_admin),
):
    if not get_connection(connection_id):
        raise HTTPException(status_code=404, detail="Saved connection not found.")
    return {"success": True, "access": public_access_record(connection_id)}


@app.put("/datasource/connections/{connection_id}/access", summary="Set Connection Access")
def set_connection_access_endpoint(
    connection_id: str,
    request: ConnectionAccessRequest,
    user: dict = Depends(require_admin),
):
    if not get_connection(connection_id):
        raise HTTPException(status_code=404, detail="Saved connection not found.")

    from user_registry import get_user_by_id

    for user_id in request.user_ids:
        if not get_user_by_id(user_id):
            raise HTTPException(status_code=400, detail=f"User not found: {user_id}")

    try:
        access = set_connection_access(
            connection_id,
            request.mode,
            request.user_ids,
            str(user.get("id")),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=public_exception_message(error, "Invalid request.")) from error

    return {"success": True, "access": access}


# ============================================================
# REPORTING DATASET REGISTRY
# ============================================================

def _visible_saved_datasets(user: dict) -> list[dict[str, Any]]:
    return [
        item
        for item in list_datasets()
        if not item.get("connection_id") or can_access_connection(user, str(item.get("connection_id")))
    ]


@app.get("/datasets", dependencies=[Depends(require_app_access)])
def list_saved_datasets(user: dict = Depends(require_app_access)):
    datasets = []
    for item in _visible_saved_datasets(user):
        enriched = dict(item)
        generated = build_semantic_model(item)
        enriched.update(dataset_semantic_payload(item, generated))
        datasets.append(enriched)
    return {"success": True, "datasets": datasets}


@app.get("/datasets/catalog", dependencies=[Depends(require_app_access)])
def list_dataset_catalog(user: dict = Depends(require_app_access)):
    """Return connector-backed and imported datasets in one query-builder catalog."""
    if not has_permission(user, "datasets.view"):
        raise HTTPException(status_code=403, detail="Permission required: datasets.view")
    datasets = _visible_saved_datasets(user)
    for item in IMPORTED_DATA_REGISTRY.list(user):
        normalized = dict(item)
        normalized.setdefault("source_type", "imported")
        normalized.setdefault("database", "local_imports")
        normalized.setdefault("object_name", normalized.get("name") or normalized.get("id"))
        normalized.setdefault("object_type", "file")
        datasets.append(normalized)
    return {"success": True, "datasets": datasets}


@app.get("/datasets/{dataset_id}", dependencies=[Depends(require_app_access)])
def get_saved_dataset(dataset_id: str, user: dict = Depends(require_app_access)):
    item = get_dataset(dataset_id)
    if not item:
        return {"success": False, "message": "Dataset not found."}
    if item.get("connection_id") and not can_access_connection(user, str(item.get("connection_id"))):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return {"success": True, "dataset": item}


@app.get("/datasets/{dataset_id}/semantic", dependencies=[Depends(require_app_access)])
def get_dataset_semantic_metadata(dataset_id: str, user: dict = Depends(require_app_access)):
    item = get_dataset(dataset_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if item.get("connection_id") and not can_access_connection(user, str(item.get("connection_id"))):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    generated = build_semantic_model(item)
    return {"success": True, **dataset_semantic_payload(item, generated), "generated": True}


@app.put("/datasets/{dataset_id}/semantic", dependencies=[Depends(require_app_access)])
def save_dataset_semantic_metadata(dataset_id: str, model: SemanticModel, user: dict = Depends(require_app_access)):
    item = get_dataset(dataset_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if item.get("connection_id") and not can_access_connection(user, str(item.get("connection_id"))):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    matches = [dataset for dataset in model.datasets if dataset.physical_dataset_id == dataset_id]
    if len(matches) != 1:
        raise HTTPException(status_code=400, detail="Semantic model must contain exactly one dataset mapped to the requested physical dataset.")
    payload = save_semantic_model(f"semantic_{dataset_id}", model)
    return {"success": True, "model": payload["model"], "consistency": consistency_report(item, model)}


@app.get("/semantic/models", dependencies=[Depends(require_app_access)])
def list_semantic_model_metadata(user: dict = Depends(require_app_access)):
    return {"success": True, "models": list_semantic_models()}


@app.get("/semantic/models/{model_id}", dependencies=[Depends(require_app_access)])
def get_semantic_model_metadata(model_id: str, user: dict = Depends(require_app_access)):
    model = get_semantic_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Semantic model not found.")
    return {"success": True, "model": model.model_dump(mode="json")}


@app.put("/semantic/models/{model_id}", dependencies=[Depends(require_app_access)])
def put_semantic_model_metadata(model_id: str, model: SemanticModel, user: dict = Depends(require_app_access)):
    try:
        payload = save_semantic_model(model_id, model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "model": payload["model"]}


@app.delete("/semantic/models/{model_id}", dependencies=[Depends(require_app_access)])
def delete_semantic_model_metadata(model_id: str, user: dict = Depends(require_app_access)):
    if not delete_semantic_model(model_id):
        raise HTTPException(status_code=404, detail="Semantic model not found.")
    return {"success": True}


@app.post("/datasets", dependencies=[Depends(require_app_access)])
def create_saved_dataset(request: SavedDatasetRequest, user: dict = Depends(require_app_access)):
    require_connection_access(user, request.connection_id)
    # Validate that the referenced connection exists before persisting the dataset.
    connection = get_connection(request.connection_id)
    if not connection:
        return {
            "success": False,
            "message": "Connection not found.",
            "connection_id": request.connection_id,
        }

    try:
        item = create_dataset(request.model_dump())
        return {"success": True, "dataset": item}
    except (ValueError, KeyError) as error:
        return {"success": False, "message": str(error)}


@app.put("/datasets/{dataset_id}", dependencies=[Depends(require_app_access)])
def update_saved_dataset(dataset_id: str, request: SavedDatasetRequest, user: dict = Depends(require_app_access)):
    require_connection_access(user, request.connection_id)
    if not get_connection(request.connection_id):
        return {
            "success": False,
            "message": "Connection not found.",
            "connection_id": request.connection_id,
        }

    item = update_dataset(dataset_id, request.model_dump())
    if not item:
        return {"success": False, "message": "Dataset not found."}

    return {"success": True, "dataset": item}


@app.delete("/datasets/{dataset_id}", dependencies=[Depends(require_app_access)])
def delete_saved_dataset(dataset_id: str, user: dict = Depends(require_app_access)):
    item = get_dataset(dataset_id)
    if not item:
        return {"success": False, "message": "Dataset not found."}
    if item.get("connection_id"):
        require_connection_access(user, str(item.get("connection_id")))
    if not delete_dataset(dataset_id):
        return {"success": False, "message": "Dataset not found."}

    return {"success": True, "message": "Dataset deleted successfully."}


@app.get("/report/capabilities", dependencies=[Depends(require_app_access)])
def capabilities():
    return {
        "success": True,
        "version": "0.8.0",
        "sources": ["mysql", "mongodb", "clickhouse"],
        "planned_sources": [],
        "features": {
            "multi_dataset_join": True,
            "multi_dataset_max_datasets": "unlimited by API design",
            "filters": True,
            "sorting": True,
            "grouping": True,
            "aggregations": True,
            "calculated_columns": True,
            "saved_reports": True,
            "export_csv": True,
            "export_json": True,
            "print_pdf": True,
            "export": True,
            "data_preview": True,
            "data_profiling": True,
            "generic_datasource_api": True,
            "connector_registry": True,
            "visualization": True,
            "visualization_fields": True,
            "chart_bar": True,
            "chart_pie": True,
            "chart_line": True,
            "chart_histogram": True,
        },
        "filter_operators": [
            "=",
            "!=",
            ">",
            "<",
            ">=",
            "<=",
            "CONTAINS",
            "STARTS_WITH",
            "IS_NULL",
            "IS_NOT_NULL",
            "ENDS_WITH",
            "NOT_CONTAINS",
            "IN",
            "NOT_IN",
            "BETWEEN",
        ],
        "sort_directions": ["ASC", "DESC"],
    }



@app.post("/report/visualization/fields", dependencies=[Depends(require_app_access)])
def report_visualization_fields(request: VisualizationFieldsRequest):
    try:
        return visualization_fields(
            columns=request.columns,
            rows=request.rows,
            supplied_profiles=request.column_profiles,
        )
    except Exception as error:
        return {"success": False, "message": str(error), "columns": [], "numeric_fields": [], "categorical_fields": []}


@app.post("/report/visualization/preview", dependencies=[Depends(require_app_access)])
def report_visualization_preview(request: VisualizationRequest):
    try:
        return build_visualization_response(
            result=request.result,
            visualization=request.visualization,
            category_field=request.category_field,
            value_field=request.value_field,
            aggregation=request.aggregation,
            limit=max(1, min(request.limit, 500)),
            bins=max(1, min(request.bins, 100)),
            sort_direction=request.sort_direction,
        )
    except Exception as error:
        return {"success": False, "message": str(error)}


@app.post("/dataset/preview", dependencies=[Depends(require_app_access)])
def dataset_preview(request: DatasetPreviewRequest):
    return preview_dataset(
        source_type=request.source_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        database=request.database,
        table=request.table,
        sample_limit=request.sample_limit,
    )


@app.post("/data/import", dependencies=[Depends(require_app_access)])
async def import_data_endpoint(file: UploadFile = File(...), user: dict = Depends(require_app_access)):
    if not has_permission(user, "datasets.create"):
        raise HTTPException(status_code=403, detail="Permission required: datasets.create")
    try:
        item = import_file(file.file, file.filename or "upload", None, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc
    except Exception as exc:
        get_logger().exception("Data import failed")
        raise HTTPException(status_code=500, detail=public_exception_message(exc, "Data import failed.")) from exc
    return {"success": True, "dataset": item, "preview": preview_import(item)}


@app.get("/data/imported", dependencies=[Depends(require_app_access)])
def list_imported_data(user: dict = Depends(require_app_access)):
    if not has_permission(user, "datasets.view"):
        raise HTTPException(status_code=403, detail="Permission required: datasets.view")
    return {"success": True, "datasets": IMPORTED_DATA_REGISTRY.list(user)}


@app.get("/data/imported/{dataset_id}", dependencies=[Depends(require_app_access)])
def get_imported_data(dataset_id: str, user: dict = Depends(require_app_access)):
    if not has_permission(user, "datasets.view"):
        raise HTTPException(status_code=403, detail="Permission required: datasets.view")
    item = IMPORTED_DATA_REGISTRY.get(dataset_id, user)
    if item is None:
        raise HTTPException(status_code=404, detail="Imported dataset not found.")
    return {"success": True, "dataset": item, "preview": preview_import(item)}


@app.put("/data/imported/{dataset_id}", dependencies=[Depends(require_app_access)])
def update_imported_data(dataset_id: str, request: ImportedDatasetUpdateRequest, user: dict = Depends(require_app_access)):
    if not has_permission(user, "datasets.edit"):
        raise HTTPException(status_code=403, detail="Permission required: datasets.edit")
    try:
        item = IMPORTED_DATA_REGISTRY.update(dataset_id, request.model_dump(), user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Imported dataset not found.")
    return {"success": True, "dataset": item}


@app.delete("/data/imported/{dataset_id}", dependencies=[Depends(require_app_access)])
def delete_imported_data(dataset_id: str, user: dict = Depends(require_app_access)):
    if not has_permission(user, "datasets.delete"):
        raise HTTPException(status_code=403, detail="Permission required: datasets.delete")
    try:
        deleted = IMPORTED_DATA_REGISTRY.delete(dataset_id, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Imported dataset not found.")
    return {"success": True, "message": "Imported dataset deleted successfully."}


@app.get("/reports", dependencies=[Depends(require_app_access)])
def list_reports(user: dict = Depends(require_app_access)):
    reports = REPORT_REGISTRY.list(user)
    return {
        "success": True,
        "reports": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "version": item.get("version", 1),
                "owner_id": item.get("owner_id"),
            }
            for item in reports
        ],
    }


@app.get("/reports/{report_id}", dependencies=[Depends(require_app_access)])
def get_report(report_id: str, user: dict = Depends(require_app_access)):
    report = REPORT_REGISTRY.get(report_id, user)
    if report is None:
        return {"success": False, "message": "Saved report not found."}
    return {"success": True, "report": report}


@app.post("/reports", dependencies=[Depends(require_app_access)])
def save_report(report: SavedReport, user: dict = Depends(require_app_access)):
    try:
        item = REPORT_REGISTRY.save(report.model_dump(), user)
        try:
            definition = item.get("definition") or {}
            graph = lineage_from_payload(
                definition,
                target_type="report",
                target_id=str(item.get("id")),
                target_label=str(item.get("name") or item.get("id")),
                owner=user,
            )
            LINEAGE_REGISTRY.save(graph, user)
        except Exception as lineage_error:
            get_logger().warning("Report saved but lineage recording failed: %s", lineage_error)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=public_exception_message(exc, "Permission denied.")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc

    return {
        "success": True,
        "message": "Report saved successfully.",
        "report": item,
    }


@app.delete("/reports/{report_id}", dependencies=[Depends(require_app_access)])
def delete_report(report_id: str, user: dict = Depends(require_app_access)):
    try:
        deleted = REPORT_REGISTRY.delete(report_id, user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=public_exception_message(exc, "Permission denied.")) from exc

    if not deleted:
        return {"success": False, "message": "Saved report not found."}
    return {"success": True, "message": "Report deleted successfully."}


@app.post("/reports/{report_id}/duplicate", dependencies=[Depends(require_app_access)])
def duplicate_report(report_id: str, user: dict = Depends(require_app_access), name: str | None = None):
    try:
        item = REPORT_REGISTRY.duplicate(report_id, user, name=name)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=public_exception_message(exc, "Permission denied.")) from exc

    if item is None:
        return {"success": False, "message": "Saved report not found."}
    return {
        "success": True,
        "message": "Report duplicated successfully.",
        "report": item,
    }


@app.get("/dashboards", dependencies=[Depends(require_app_access)])
def list_dashboards(user: dict = Depends(require_app_access)):
    return {"success": True, "dashboards": DASHBOARD_REGISTRY.list(user)}

@app.get("/dashboards/{dashboard_id}", dependencies=[Depends(require_app_access)])
def get_dashboard(dashboard_id: str, user: dict = Depends(require_app_access)):
    item = DASHBOARD_REGISTRY.get(dashboard_id, user)
    if item is None: return {"success": False, "message": "Saved dashboard not found."}
    return {"success": True, "dashboard": item}

@app.post("/dashboards", dependencies=[Depends(require_app_access)])
def save_dashboard(request: SavedDashboard, user: dict = Depends(require_app_access)):
    try: item=DASHBOARD_REGISTRY.save(request.id, request.name, request.definition, user)
    except PermissionError as exc: raise HTTPException(status_code=403, detail=public_exception_message(exc, "Permission denied.")) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc
    return {"success": True, "message": "Dashboard saved successfully.", "dashboard": item}

@app.delete("/dashboards/{dashboard_id}", dependencies=[Depends(require_app_access)])
def delete_dashboard(dashboard_id: str, user: dict = Depends(require_app_access)):
    try: deleted=DASHBOARD_REGISTRY.delete(dashboard_id,user)
    except PermissionError as exc: raise HTTPException(status_code=403, detail=public_exception_message(exc, "Permission denied.")) from exc
    if not deleted: return {"success": False, "message": "Saved dashboard not found."}
    return {"success": True, "message": "Dashboard deleted successfully."}


@app.get("/dashboards/{dashboard_id}/shares", dependencies=[Depends(require_app_access)])
def list_dashboard_shares(dashboard_id: str, user: dict = Depends(require_app_access)):
    try:
        shares = DASHBOARD_REGISTRY.list_shares(dashboard_id, user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=public_exception_message(exc, "Permission denied.")) from exc
    if shares is None:
        return {"success": False, "message": "Saved dashboard not found."}
    return {"success": True, "shares": shares}


@app.post("/dashboards/{dashboard_id}/shares", dependencies=[Depends(require_app_access)])
def add_dashboard_share(dashboard_id: str, request: DashboardShareRequest, user: dict = Depends(require_app_access)):
    target = next((item for item in list_users() if str(item.get("username", "")).lower() == request.username.strip().lower()), None)
    if target is None:
        return {"success": False, "message": "Target user was not found."}
    if str(target.get("id")) == str(user.get("id")):
        return {"success": False, "message": "The dashboard is already available to its owner."}
    try:
        shares = DASHBOARD_REGISTRY.add_share(dashboard_id, target.get("id"), target.get("username"), user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=public_exception_message(exc, "Permission denied.")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc
    if shares is None:
        return {"success": False, "message": "Saved dashboard not found."}
    return {"success": True, "message": "Dashboard shared successfully.", "shares": shares}


@app.delete("/dashboards/{dashboard_id}/shares/{shared_with_id}", dependencies=[Depends(require_app_access)])
def remove_dashboard_share(dashboard_id: str, shared_with_id: str, user: dict = Depends(require_app_access)):
    try:
        deleted = DASHBOARD_REGISTRY.remove_share(dashboard_id, shared_with_id, user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=public_exception_message(exc, "Permission denied.")) from exc
    if not deleted:
        return {"success": False, "message": "Dashboard share not found."}
    return {"success": True, "message": "Dashboard share removed."}


@app.post("/dashboards/export/{format}", dependencies=[Depends(require_app_access)])
def export_current_dashboard(format: str, request: DashboardExportRequest, user: dict = Depends(require_app_access)):
    """Export the dashboard currently open in the editor without requiring it to be saved first."""
    allowed = {"json", "csv", "xlsx", "pdf", "package"}
    if format not in allowed:
        raise HTTPException(status_code=404, detail="Unsupported dashboard export format.")

    definition = request.definition if isinstance(request.definition, dict) else {}
    result = request.result if isinstance(request.result, dict) else {}
    item = {
        "id": "current",
        "name": request.name.strip() or "Dashboard",
        "definition": definition,
        "owner_username": user.get("username", ""),
        "version": 1,
    }
    # An execution job is the authoritative source whenever one is supplied.
    # Do not silently fall back to browser-provided rows/results: large results
    # are persisted in ResultStore and the browser payload is only a page/window.
    execution_job_id = definition.get("execution_job_id") or result.get("execution_job_id")
    if execution_job_id:
        job = _require_job_access(str(execution_job_id), user)
        if job.get("status") != "completed":
            raise HTTPException(status_code=409, detail="Dashboard execution result is not completed.")
        result = {}
    else:
        job = {"status": "completed", "result": result}
    filename = safe_export_filename(request.name.strip() or "dashboard", format if format != "package" else "zip")

    if format == "json":
        payload = json.dumps({"success": True, "dashboard": item}, ensure_ascii=False).encode("utf-8")
        return StreamingResponse(iter([payload]), media_type="application/json; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    source_result = job.get("result") if isinstance(job.get("result"), dict) else result
    columns = job.get("result_columns") if isinstance(job.get("result_columns"), list) else source_result.get("columns") if isinstance(source_result.get("columns"), list) else []
    total_rows = int(job.get("result_total_rows") or source_result.get("total_rows") or len(source_result.get("rows", [])) if isinstance(source_result.get("rows"), list) else 0)
    if not columns and total_rows <= 0:
        raise HTTPException(status_code=409, detail="Run a report before exporting dashboard data.")

    try:
        if format == "csv":
            columns = job.get("result_columns") if isinstance(job.get("result_columns"), list) else source_result.get("columns", [])
            rows = (
                EXECUTION_MANAGER.iter_result_rows(str(execution_job_id))
                if execution_job_id
                else (source_result.get("rows", []) if isinstance(source_result.get("rows"), list) else [])
            )
            # Keep the response genuinely streaming. Never join the complete
            # CSV into one bytes object, which defeats ResultStore paging and
            # can exhaust server memory on large dashboards.
            return StreamingResponse(
                csv_stream_rows(columns, rows or iter(())),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        elif format == "xlsx":
            payload = build_dashboard_xlsx(item, job)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif format == "pdf":
            payload = build_dashboard_pdf(item, job)
            media_type = "application/pdf"
        else:
            from dashboard_export import build_dashboard_package
            payload = build_dashboard_package(item, job)
            media_type = "application/zip"
    except Exception as exc:
        raise HTTPException(status_code=500, detail=public_exception_message(exc, "Unable to create dashboard export.")) from exc

    return StreamingResponse(iter([payload]), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/dashboards/{dashboard_id}/export/json", dependencies=[Depends(require_app_access)])
def export_saved_dashboard_json(dashboard_id: str, user: dict = Depends(require_app_access)):
    item = DASHBOARD_REGISTRY.get(dashboard_id, user)
    if item is None:
        raise HTTPException(status_code=404, detail="Saved dashboard not found.")
    payload = json.dumps({"success": True, "dashboard": item}, ensure_ascii=False).encode("utf-8")
    return StreamingResponse(iter([payload]), media_type="application/json; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="dashboard-{dashboard_id}.json"'})


@app.get("/dashboards/{dashboard_id}/export/xlsx", dependencies=[Depends(require_app_access)])
def export_saved_dashboard_xlsx(dashboard_id: str, user: dict = Depends(require_app_access)):
    item = DASHBOARD_REGISTRY.get(dashboard_id, user)
    if item is None:
        raise HTTPException(status_code=404, detail="Saved dashboard not found.")
    definition = item.get("definition") if isinstance(item.get("definition"), dict) else {}
    job_id = definition.get("execution_job_id")
    if not job_id:
        raise HTTPException(status_code=409, detail="This dashboard has no saved execution result to export.")
    job = _require_job_access(str(job_id), user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Dashboard execution result is not completed.")
    try:
        payload = build_dashboard_xlsx(item, job)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=public_exception_message(exc, "Unable to create Excel dashboard export.")) from exc
    return StreamingResponse(iter([payload]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="dashboard-{dashboard_id}.xlsx"'})


@app.get("/dashboards/{dashboard_id}/export/pdf", dependencies=[Depends(require_app_access)])
def export_saved_dashboard_pdf(dashboard_id: str, user: dict = Depends(require_app_access)):
    item = DASHBOARD_REGISTRY.get(dashboard_id, user)
    if item is None:
        raise HTTPException(status_code=404, detail="Saved dashboard not found.")
    definition = item.get("definition") if isinstance(item.get("definition"), dict) else {}
    job_id = definition.get("execution_job_id")
    if not job_id:
        raise HTTPException(status_code=409, detail="This dashboard has no saved execution result to export.")
    job = _require_job_access(str(job_id), user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Dashboard execution result is not completed.")
    try:
        payload = build_dashboard_pdf(item, job)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=public_exception_message(exc, "Unable to create PDF dashboard export.")) from exc
    return StreamingResponse(iter([payload]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="dashboard-{dashboard_id}.pdf"'})


@app.get("/dashboards/{dashboard_id}/export/package", dependencies=[Depends(require_app_access)])
def export_saved_dashboard_package(dashboard_id: str, user: dict = Depends(require_app_access)):
    item = DASHBOARD_REGISTRY.get(dashboard_id, user)
    if item is None:
        raise HTTPException(status_code=404, detail="Saved dashboard not found.")
    definition = item.get("definition") if isinstance(item.get("definition"), dict) else {}
    job_id = definition.get("execution_job_id")
    if not job_id:
        raise HTTPException(status_code=409, detail="This dashboard has no saved execution result to export.")
    job = _require_job_access(str(job_id), user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Dashboard execution result is not completed.")
    try:
        from dashboard_export import build_dashboard_package
        package_payload = build_dashboard_package(item, job)
        return StreamingResponse(iter([package_payload]), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="dashboard-{dashboard_id}-package.zip"'})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=public_exception_message(exc, "Unable to create dashboard download package.")) from exc


@app.get("/dashboards/{dashboard_id}/export/csv", dependencies=[Depends(require_app_access)])
def export_saved_dashboard_csv(dashboard_id: str, user: dict = Depends(require_app_access)):
    item = DASHBOARD_REGISTRY.get(dashboard_id, user)
    if item is None:
        raise HTTPException(status_code=404, detail="Saved dashboard not found.")
    definition = item.get("definition") if isinstance(item.get("definition"), dict) else {}
    job_id = definition.get("execution_job_id")
    if not job_id:
        raise HTTPException(status_code=409, detail="This dashboard has no saved execution result to export.")
    job = _require_job_access(str(job_id), user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Dashboard execution result is not completed.")
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    columns = job.get("result_columns") if isinstance(job.get("result_columns"), list) else result.get("columns") if isinstance(result.get("columns"), list) else []
    rows = EXECUTION_MANAGER.iter_result_rows(str(job_id))
    if rows is None:
        rows = iter(())
    return StreamingResponse(csv_stream_rows(columns, rows), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="dashboard-{dashboard_id}.csv"'})


@app.post("/report/export/csv", dependencies=[Depends(require_app_access)])
def export_csv(request: ReportQueryRequest, user: dict = Depends(require_app_access)):
    """Legacy CSV endpoint using the canonical job/result pipeline."""
    payload = request.model_dump()
    payload["limit"] = 0
    canonical = _prepare_report_query(payload)
    for dataset in canonical.datasets:
        _require_dataset_access(dataset, user)
    job_id = EXECUTION_MANAGER.submit(
        _execute_report_payload, canonical.normalized(),
        owner_user_id=str(user.get("id")), owner_username=str(user.get("username", "")),
        query_payload=canonical.normalized(),
    )
    return StreamingResponse(
        _stream_job_export(job_id, "csv", "report.csv"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="report.csv"'},
    )


@app.post("/datasource/mysql/test", dependencies=[Depends(require_app_access)])
def test_mysql(connection: MySQLConnection):
    return test_mysql_connection(
        connection.host,
        connection.port,
        connection.username,
        connection.password,
    )


@app.post("/datasource/mysql/tables", dependencies=[Depends(require_app_access)])
def mysql_tables(request: MySQLTableRequest):
    return get_mysql_tables(
        request.host,
        request.port,
        request.username,
        request.password,
        request.database,
    )


@app.post("/datasource/mysql/columns", dependencies=[Depends(require_app_access)])
def mysql_columns(request: MySQLColumnRequest):
    return get_mysql_columns(
        request.host,
        request.port,
        request.username,
        request.password,
        request.database,
        request.table,
    )


@app.post("/datasource/mongodb/test", dependencies=[Depends(require_app_access)])
def test_mongodb(connection: MongoDBConnection):
    return test_mongodb_connection(
        connection.host,
        connection.port,
        connection.username,
        connection.password,
    )


@app.post("/datasource/mongodb/collections", dependencies=[Depends(require_app_access)])
def mongodb_collections(request: MongoDBCollectionRequest):
    return get_mongodb_collections(
        request.host,
        request.port,
        request.database,
        request.username,
        request.password,
    )


@app.post("/datasource/mongodb/fields", dependencies=[Depends(require_app_access)])
def mongodb_fields(request: MongoDBFieldRequest):
    return get_mongodb_fields(
        request.host,
        request.port,
        request.database,
        request.collection,
        request.username,
        request.password,
    )


@app.post("/datasource/clickhouse/test", dependencies=[Depends(require_app_access)])
def test_clickhouse(connection: ClickHouseConnection):
    return test_clickhouse_connection(connection.host, connection.port, connection.username, connection.password)


@app.post("/datasource/clickhouse/databases", dependencies=[Depends(require_app_access)])
def clickhouse_databases(connection: ClickHouseConnection):
    return get_clickhouse_databases(connection.host, connection.port, connection.username, connection.password)


@app.post("/datasource/clickhouse/tables", dependencies=[Depends(require_app_access)])
def clickhouse_tables(request: ClickHouseTableRequest):
    return get_clickhouse_tables(request.host, request.port, request.username, request.password, request.database)


@app.post("/datasource/clickhouse/columns", dependencies=[Depends(require_app_access)])
def clickhouse_columns(request: ClickHouseColumnRequest):
    return get_clickhouse_columns(request.host, request.port, request.username, request.password, request.database, request.table)


@app.post("/datasource/clickhouse/preview", dependencies=[Depends(require_app_access)])
def clickhouse_preview(request: DatasetPreviewRequest):
    return get_clickhouse_preview(request.host, request.port, request.username, request.password, request.database, request.table, request.sample_limit)


@app.post("/join/execute", dependencies=[Depends(require_app_access)])
def legacy_join_execute(request: dict):
    """Backward-compatible two-dataset JOIN endpoint."""
    return execute_join_request(request)


def _require_dataset_access(dataset: Any, user: dict) -> None:
    dataset_id = str(getattr(dataset, "id", "") or (dataset.get("id", "") if isinstance(dataset, dict) else ""))
    source_type = str(getattr(dataset, "source_type", None) or (dataset.get("source_type", "") if isinstance(dataset, dict) else "")).lower()
    connection_id = getattr(dataset, "connection_id", None) or (dataset.get("connection_id") if isinstance(dataset, dict) else None)
    if source_type == "imported" or dataset_id.startswith("import_"):
        if not has_permission(user, "datasets.view"):
            raise HTTPException(status_code=403, detail="Permission required: datasets.view")
        if not IMPORTED_DATA_REGISTRY.get(dataset_id, user):
            raise HTTPException(status_code=403, detail="You do not have access to this imported dataset.")
    elif connection_id:
        require_connection_access(user, connection_id)


@app.post("/report/query", dependencies=[Depends(require_app_access)])
def report_query(request: ReportQueryRequest, user: dict = Depends(require_app_access)):
    # Keep the existing request model for frontend compatibility, but make the
    # canonical QueryDefinition the internal contract from this point onward.
    canonical = canonical_query_from_payload(request.model_dump())
    plan = plan_query(canonical)
    if plan.join_count > MAX_JOIN_OPERATIONS:
        raise HTTPException(status_code=400, detail=(
            f"Query contains {plan.join_count} JOIN operations; maximum allowed is {MAX_JOIN_OPERATIONS}."
        ))
    for dataset in canonical.datasets:
        _require_dataset_access(dataset, user)
    canonical_payload = canonical.normalized()
    job_id = EXECUTION_MANAGER.submit(
        _run_report_job_payload,
        canonical_payload,
        owner_user_id=str(user.get("id")),
        owner_username=str(user.get("username", "")),
        query_payload=canonical_payload,
    )
    job = EXECUTION_MANAGER.get(job_id) or {}
    # Preserve the legacy response shape while exposing the first persisted
    # result page when the short-lived worker completes before the response is
    # returned. The normal queued path remains page-bounded and asynchronous.
    page = EXECUTION_MANAGER.result_page(job_id, offset=0, limit=5000)
    if page and page.get("ready"):
        return {
            "success": True,
            "execution_job_id": job_id,
            "status": job.get("status", "completed"),
            "rows": page.get("rows", []),
            "columns": page.get("columns") or [item.name for item in canonical.columns],
            "total_rows": page.get("total_rows", 0),
            "returned_rows": page.get("returned_rows", len(page.get("rows", []))),
            "has_more": page.get("has_more", False),
            "execution_in_progress": False,
        }
    return {
        "success": True,
        "execution_job_id": job_id,
        "status": job.get("status", "queued"),
        "rows": [],
        "columns": [item.name for item in canonical.columns],
        "total_rows": 0,
        "execution_in_progress": True,
    }


@app.post("/report/query/plan", dependencies=[Depends(require_app_access)])
def report_query_plan(payload: dict[str, Any], user: dict = Depends(require_app_access)):
    """Return the canonical execution plan after validating dataset access."""
    try:
        canonical = canonical_query_from_payload(payload)
        for dataset in canonical.datasets:
            _require_dataset_access(dataset, user)
        return {"success": True, "query": canonical.model_dump(exclude_none=True), "plan": plan_query(canonical).summary()}
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))



def _run_report_job_payload(payload):
    """Execute an execution-job payload through QueryDefinition normalization."""
    canonical = canonical_query_from_payload(payload)
    plan = plan_query(canonical)
    if plan.join_count > MAX_JOIN_OPERATIONS:
        raise ValueError(
            f"Query contains {plan.join_count} JOIN operations; maximum allowed is {MAX_JOIN_OPERATIONS}."
        )
    data = canonical.normalized()
    return execute_report_query(
        _report_datasets_for_execution([DatasetDefinition(**item) for item in data.get("datasets", [])]),
        data.get("joins", []),
        data.get("columns", []),
        data.get("filters", []),
        data.get("sorts", []),
        data.get("group_by", []),
        data.get("aggregations", []),
        data.get("calculated_columns", []),
        data.get("limit", 0),
    )



# ---------------------------------------------------------------------------
# Step 10: production execution controls
# ---------------------------------------------------------------------------

@app.get("/lineage/reports/{report_id}", dependencies=[Depends(require_app_access)])
def get_report_lineage(report_id: str, user: dict = Depends(require_app_access)):
    """Return lineage for a saved report after ownership/access validation."""
    report = REPORT_REGISTRY.get(report_id, user)
    if report is None:
        raise HTTPException(status_code=404, detail="Saved report not found.")
    record = LINEAGE_REGISTRY.get("report", report_id)
    if record is None:
        try:
            graph = lineage_from_payload(
                report.get("definition") or {},
                target_type="report",
                target_id=report_id,
                target_label=str(report.get("name") or report_id),
                owner=user,
            )
            record = LINEAGE_REGISTRY.save(graph, user)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=public_exception_message(exc, "Unable to build report lineage.")) from exc
    return {"success": True, "lineage": record.get("graph", record)}


@app.get("/lineage/jobs/{job_id}", dependencies=[Depends(require_app_access)])
def get_execution_job_lineage(job_id: str, user: dict = Depends(require_app_access)):
    """Return lineage for an execution job after job ACL validation."""
    _require_job_access(job_id, user)
    record = LINEAGE_REGISTRY.get("execution_job", job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution job lineage not found.")
    return {"success": True, "lineage": record.get("graph", record)}



def _job_is_visible_to_user(job: dict[str, Any] | None, user: dict) -> bool:
    """Return whether an authenticated user may access an execution job.

    Administrators can inspect all jobs. Non-admin users can only access jobs
    created by their own account. Legacy unowned jobs are intentionally
    inaccessible to non-admin users so job ids cannot become a data-access
    bypass.
    """
    if not job:
        return False
    if str(user.get("role", "")).lower() == "admin":
        return True
    owner_id = job.get("owner_user_id")
    return owner_id is not None and str(owner_id) == str(user.get("id"))


def _require_job_access(job_id: str, user: dict) -> dict:
    job = EXECUTION_MANAGER.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Report job not found.")
    if not _job_is_visible_to_user(job, user):
        raise HTTPException(status_code=403, detail="You do not have access to this report job.")
    return job


def _execute_full_export(job_id: str, user: dict) -> dict[str, Any]:
    """Re-execute the job's canonical query without the interactive row limit.

    Interactive execution intentionally materializes only the configured preview
    window. Export must not reuse that materialized page, otherwise CSV/JSON
    downloads inherit the 100/1000/5000-row browser limits. The original query
    definition is kept privately on the execution job, so export can rebuild the
    exact query while re-checking current dataset access.
    """
    payload = EXECUTION_MANAGER.get_query_payload(job_id)
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=409,
            detail="This execution job has no stored query definition. Re-run the report before exporting all rows.",
        )

    export_payload = dict(payload)
    export_payload["limit"] = 0

    canonical = _prepare_report_query(export_payload)
    for dataset in canonical.datasets:
        _require_dataset_access(dataset, user)

    result = _execute_report_payload(canonical.normalized())
    if not isinstance(result, dict) or result.get("success") is False:
        message = (result or {}).get("message") if isinstance(result, dict) else None
        raise HTTPException(status_code=500, detail=message or "Unable to generate the complete report export.")
    return result



@app.post("/execution/jobs", dependencies=[Depends(require_app_access)])
def create_report_job(payload: dict, user: dict = Depends(require_app_access)):
    """Queue a canonical report query and record its execution lineage."""
    try:
        canonical = _prepare_report_query(payload)
        for dataset in canonical.datasets:
            _require_dataset_access(dataset, user)
        canonical_payload = canonical.normalized()
        job_id = EXECUTION_MANAGER.submit(
            _execute_report_payload,
            canonical_payload,
            owner_user_id=str(user.get("id")),
            owner_username=str(user.get("username", "")),
            query_payload=canonical_payload,
        )
        try:
            graph = lineage_from_payload(
                canonical_payload,
                target_type="execution_job",
                target_id=job_id,
                target_label=f"Execution {job_id}",
                owner=user,
            )
            LINEAGE_REGISTRY.save(graph, user)
        except Exception as lineage_error:
            get_logger().warning("Execution job created but lineage recording failed: %s", lineage_error)
        return {
            "success": True,
            "job_id": job_id,
            "status": "queued",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=public_exception_message(exc, "Service temporarily unavailable.")) from exc


@app.get("/execution/jobs", dependencies=[Depends(require_app_access)])
def list_report_jobs(user: dict = Depends(require_app_access)):
    jobs = EXECUTION_MANAGER.list()
    if str(user.get("role", "")).lower() != "admin":
        jobs = [job for job in jobs if _job_is_visible_to_user(job, user)]
    return {
        "success": True,
        "jobs": jobs,
    }


@app.get("/execution/jobs/{job_id}", dependencies=[Depends(require_app_access)])
def get_report_job(job_id: str, user: dict = Depends(require_app_access)):
    job = _require_job_access(job_id, user)
    return {
        "success": True,
        "job": job,
    }


@app.get("/execution/jobs/{job_id}/result", dependencies=[Depends(require_app_access)])
def get_report_job_result(job_id: str, offset: int = 0, limit: int = 5000, user: dict = Depends(require_app_access)):
    """Return a bounded page of rows from a completed report job.

    This endpoint is additive and does not change the existing job-status
    response. It is intended for large result sets so clients can consume
    rows incrementally instead of requesting the complete result at once.
    """
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be non-negative.")
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be at least 1.")
    _require_job_access(job_id, user)
    page = EXECUTION_MANAGER.result_page(job_id, offset=offset, limit=limit)
    if page is None:
        raise HTTPException(status_code=404, detail="Report job not found.")
    return {"success": True, "job_id": job_id, **page}


class ExecutionTransformRequest(BaseModel):
    """Operations that can be applied to an existing canonical execution.

    The source datasets, JOIN graph and selected columns stay attached to the
    original job. Only relational operations are replaced, so the browser does
    not need to resend connection metadata for every filter/sort interaction.
    """
    filters: list[ReportFilter] | None = None
    sorts: list[ReportSort] | None = None
    group_by: list[str] | None = None
    aggregations: list[ReportAggregation] | None = None
    limit: int | None = None


@app.post("/execution/jobs/{job_id}/transform", dependencies=[Depends(require_app_access)])
def transform_report_job(
    job_id: str,
    request: ExecutionTransformRequest,
    user: dict = Depends(require_app_access),
):
    """Queue a derived execution while reusing the original QueryDefinition.

    This keeps interactive Filter/Sort/Group operations server-side and avoids
    sending the original dataset/connection definition back from the browser.
    """
    _require_job_access(job_id, user)
    payload = EXECUTION_MANAGER.get_query_payload(job_id)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=409, detail="This execution job has no stored query definition.")

    transformed = dict(payload)
    updates = request.model_dump(exclude_none=True)
    transformed.update(updates)
    canonical = _prepare_report_query(transformed)
    for dataset in canonical.datasets:
        _require_dataset_access(dataset, user)

    canonical_payload = canonical.normalized()
    new_job_id = EXECUTION_MANAGER.submit(
        _execute_report_payload,
        canonical_payload,
        owner_user_id=str(user.get("id")),
        owner_username=str(user.get("username", "")),
        query_payload=canonical_payload,
    )
    return {
        "success": True,
        "job_id": new_job_id,
        "source_job_id": job_id,
        "status": "queued",
    }


def _stream_job_export(job_id: str, fmt: str, filename: str):
    """Stream a completed ResultStore-backed job without rebuilding its rows."""
    import time
    while True:
        job = EXECUTION_MANAGER.get(job_id)
        if not job:
            raise RuntimeError("Report execution job not found.")
        status = job.get("status")
        if status == "completed":
            columns = [str(c) for c in (job.get("result_columns") or job.get("columns") or [])]
            total_rows = int(job.get("result_total_rows") or job.get("rows") or 0)
            rows = EXECUTION_MANAGER.iter_result_rows(job_id) or iter(())
            if fmt == "csv":
                yield from csv_stream_rows(columns, rows)
            else:
                yield from json_stream_rows(columns, rows, total_rows)
            return
        if status in {"failed", "cancelled"}:
            raise RuntimeError(job.get("error") or f"Report execution {status}.")
        time.sleep(0.1)


@app.post("/execution/jobs/{job_id}/export", dependencies=[Depends(require_app_access)])
def create_report_export_job(
    job_id: str,
    format: str = "csv",
    filename: str = "report",
    user: dict = Depends(require_app_access),
):
    """Queue a complete CSV/JSON export from the completed execution result."""
    job = _require_job_access(job_id, user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Report job is not completed.")
    normalized = str(format).lower()
    if normalized not in {"csv", "json", "xlsx", "pdf", "package"}:
        raise HTTPException(status_code=400, detail="Unsupported export format.")

    extension = "zip" if normalized == "package" else normalized
    safe_name = safe_export_filename(filename, extension)
    columns = [str(c) for c in (job.get("result_columns") or job.get("columns") or [])]
    total_rows = max(0, int(job.get("result_total_rows") or job.get("rows") or 0))

    def row_factory():
        rows = EXECUTION_MANAGER.iter_result_rows(job_id)
        return rows if rows is not None else iter(())

    writer = None
    if normalized == "xlsx":
        writer = lambda path, cols, factory, export_job, cancelled: write_report_xlsx(path, cols, factory(), cancelled)
    elif normalized == "pdf":
        writer = lambda path, cols, factory, export_job, cancelled: write_report_pdf(path, safe_name.rsplit(".", 1)[0], cols, factory(), cancelled)
    elif normalized == "package":
        writer = lambda path, cols, factory, export_job, cancelled: write_report_package(path, safe_name.rsplit(".", 1)[0], cols, factory, total_rows, cancelled)

    try:
        export_id = EXPORT_MANAGER.submit(
            source_job_id=job_id,
            owner_user_id=str(user.get("id")),
            owner_username=str(user.get("username", "")),
            fmt=normalized,
            filename=safe_name,
            columns=columns,
            row_iterator_factory=row_factory,
            total_rows=total_rows,
            writer=writer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc

    return {"success": True, "export_id": export_id, "status": "queued"}


@app.get("/execution/exports/{export_id}", dependencies=[Depends(require_app_access)])
def get_report_export_job(export_id: str, user: dict = Depends(require_app_access)):
    export = EXPORT_MANAGER.get(export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export job not found.")
    if str(user.get("role", "")).lower() != "admin" and str(export.get("owner_user_id")) != str(user.get("id")):
        raise HTTPException(status_code=403, detail="You do not have access to this export job.")
    return {"success": True, "export": export}


@app.post("/execution/exports/{export_id}/cancel", dependencies=[Depends(require_app_access)])
def cancel_report_export_job(export_id: str, user: dict = Depends(require_app_access)):
    export = EXPORT_MANAGER.get(export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export job not found.")
    if str(user.get("role", "")).lower() != "admin" and str(export.get("owner_user_id")) != str(user.get("id")):
        raise HTTPException(status_code=403, detail="You do not have access to this export job.")
    if not EXPORT_MANAGER.cancel(export_id):
        raise HTTPException(status_code=409, detail="Export job cannot be cancelled.")
    return {"success": True, "export_id": export_id, "status": "cancelled"}


@app.get("/execution/exports/{export_id}/download", dependencies=[Depends(require_app_access)])
def download_report_export_job(export_id: str, user: dict = Depends(require_app_access)):
    export = EXPORT_MANAGER.get(export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export job not found.")
    if str(user.get("role", "")).lower() != "admin" and str(export.get("owner_user_id")) != str(user.get("id")):
        raise HTTPException(status_code=403, detail="You do not have access to this export job.")
    completed = EXPORT_MANAGER.path_for_completed(export_id)
    if not completed:
        if export.get("status") in {"queued", "running"}:
            raise HTTPException(status_code=409, detail="Export job is not completed.")
        raise HTTPException(status_code=410, detail=export.get("error") or "Export file is unavailable.")
    metadata, path = completed
    from fastapi.responses import FileResponse
    media_types = {
        "csv": "text/csv; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "package": "application/zip",
    }
    return FileResponse(
        path,
        media_type=media_types.get(metadata["format"], "application/octet-stream"),
        filename=metadata["filename"],
    )


@app.get("/execution/jobs/{job_id}/export/csv", dependencies=[Depends(require_app_access)])
def export_report_job_csv(job_id: str, filename: str = "report", user: dict = Depends(require_app_access)):
    job = _require_job_access(job_id, user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Report job is not completed.")
    download_name = safe_export_filename(filename, "csv")
    # csv_stream is the legacy serializer; _stream_job_export uses the row-iterator variant.
    return StreamingResponse(
        _stream_job_export(job_id, "csv", download_name),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@app.get("/execution/jobs/{job_id}/export/json", dependencies=[Depends(require_app_access)])
def export_report_job_json(job_id: str, filename: str = "report", user: dict = Depends(require_app_access)):
    job = _require_job_access(job_id, user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Report job is not completed.")
    download_name = safe_export_filename(filename, "json")
    # json_stream is the legacy serializer; _stream_job_export uses the row-iterator variant.
    return StreamingResponse(
        _stream_job_export(job_id, "json", download_name),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


def _build_report_pdf(result: dict[str, Any], title: str) -> bytes:
    """Build a complete report PDF from the unbounded export result.

    This is intentionally separate from the browser print view: browser print
    only knows about the currently loaded page, while this endpoint receives
    the complete server-side export result.
    """
    columns = result.get("columns") if isinstance(result.get("columns"), list) else []
    rows = result.get("rows") if isinstance(result.get("rows"), list) else []
    column_names = [
        str(column.get("name") or column.get("field") or column.get("alias") or "")
        if isinstance(column, dict) else str(column)
        for column in columns
    ]
    if not column_names and rows:
        column_names = [str(item) for item in rows[0].keys()] if isinstance(rows[0], dict) else []
    if not column_names:
        raise ValueError("The report contains no columns to export.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=8 * mm,
        leftMargin=8 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=title,
    )
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.fontSize = 13
    title_style.leading = 16

    data = [[Paragraph(name.replace("&", "&amp;"), styles["Heading5"]) for name in column_names]]
    for row in rows:
        data.append([
            str(row.get(column, "") if isinstance(row, dict) else "")
            for column in column_names
        ])

    table = LongTable(data, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172033")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d5dd")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    doc.build([Paragraph(title, title_style), table])
    return buffer.getvalue()


@app.get("/execution/jobs/{job_id}/export/pdf", dependencies=[Depends(require_app_access)])
def export_report_job_pdf(job_id: str, filename: str = "report", user: dict = Depends(require_app_access)):
    """Backward-compatible PDF endpoint backed by the durable export job pipeline."""
    job = _require_job_access(job_id, user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Report job is not completed.")
    safe_name = safe_export_filename(filename, "pdf")
    columns = [str(c) for c in (job.get("result_columns") or job.get("columns") or [])]
    total_rows = max(0, int(job.get("result_total_rows") or job.get("rows") or 0))

    def row_factory():
        rows = EXECUTION_MANAGER.iter_result_rows(job_id)
        return rows if rows is not None else iter(())

    try:
        export_id = EXPORT_MANAGER.submit(
            source_job_id=job_id,
            owner_user_id=str(user.get("id")),
            owner_username=str(user.get("username", "")),
            fmt="pdf",
            filename=safe_name,
            columns=columns,
            row_iterator_factory=row_factory,
            total_rows=total_rows,
            writer=lambda path, cols, factory, export_job, cancelled: write_report_pdf(path, safe_name.rsplit(".", 1)[0], cols, factory(), cancelled),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc
    return {"success": True, "export_id": export_id, "status": "queued"}


@app.post("/reports/{report_id}/export/{format}", dependencies=[Depends(require_app_access)])
def export_saved_report(report_id: str, format: str, user: dict = Depends(require_app_access)):
    """Create a durable export job for a saved report's committed execution."""
    report = REPORT_REGISTRY.get(report_id, user)
    if report is None:
        raise HTTPException(status_code=404, detail="Saved report not found.")
    execution_job_id = (report.get("definition") or {}).get("execution_job_id")
    if not execution_job_id:
        raise HTTPException(status_code=409, detail="Saved report has no committed execution result. Re-run and save the report before exporting.")
    normalized = str(format).lower()
    if normalized not in {"csv", "json", "xlsx", "pdf", "package"}:
        raise HTTPException(status_code=400, detail="Unsupported report export format.")
    job = _require_job_access(str(execution_job_id), user)
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Saved report execution result is not completed.")
    extension = "zip" if normalized == "package" else normalized
    safe_name = safe_export_filename(report.get("name") or "report", extension)
    columns = [str(c) for c in (job.get("result_columns") or job.get("columns") or [])]
    total_rows = max(0, int(job.get("result_total_rows") or job.get("rows") or 0))
    def row_factory():
        rows = EXECUTION_MANAGER.iter_result_rows(str(execution_job_id))
        return rows if rows is not None else iter(())
    writer = None
    if normalized == "xlsx":
        writer = lambda path, cols, factory, export_job, cancelled: write_report_xlsx(path, cols, factory(), cancelled)
    elif normalized == "pdf":
        writer = lambda path, cols, factory, export_job, cancelled: write_report_pdf(path, safe_name.rsplit(".", 1)[0], cols, factory(), cancelled)
    elif normalized == "package":
        writer = lambda path, cols, factory, export_job, cancelled: write_report_package(path, safe_name.rsplit(".", 1)[0], cols, factory, total_rows, cancelled)
    try:
        export_id = EXPORT_MANAGER.submit(
            source_job_id=str(execution_job_id), owner_user_id=str(user.get("id")), owner_username=str(user.get("username", "")),
            fmt=normalized, filename=safe_name, columns=columns, row_iterator_factory=row_factory, total_rows=total_rows, writer=writer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=public_exception_message(exc, "Invalid request.")) from exc
    return {"success": True, "export_id": export_id, "status": "queued", "report_id": report_id}


@app.get("/execution/jobs/{job_id}/dashboard", dependencies=[Depends(require_app_access)])
def report_job_dashboard(
    job_id: str,
    visualization: str = "table",
    category_field: str | None = None,
    value_field: str | None = None,
    aggregation: str = "SUM",
    limit: int = 0,
    user: dict = Depends(require_app_access),
):
    """Build a bounded visualization payload from a completed job result.

    This is the dashboard integration boundary for Change #12. It deliberately
    uses a bounded page so dashboard rendering never transfers an unbounded
    result set to the browser.
    """
    if limit < 0:
        raise HTTPException(status_code=400, detail="limit must be 0 or greater.")
    _require_job_access(job_id, user)
    if visualization in {"kpi", "bar", "pie", "line", "histogram"}:
        columns = (EXECUTION_MANAGER.get(job_id) or {}).get("result_columns", [])
        rows = EXECUTION_MANAGER.iter_result_rows(job_id)
        if rows is None:
            job = EXECUTION_MANAGER.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Report job not found.")
            raise HTTPException(status_code=409, detail="Report job is not completed.")
        data = build_visualization_from_row_stream(
            rows=rows,
            columns=columns,
            visualization=visualization,
            category_field=category_field,
            value_field=value_field,
            aggregation=aggregation,
            limit=limit,
            bins=6,
        )
        job = EXECUTION_MANAGER.get(job_id) or {}
        return {
            "success": True,
            "source_result": {
                "total_rows": job.get("result_total_rows", 0),
                "returned_rows": job.get("result_returned_rows", 0),
            },
            "columns": columns,
            **data,
        }
    page = EXECUTION_MANAGER.result_page(job_id, offset=0, limit=limit)
    if page is None:
        raise HTTPException(status_code=404, detail="Report job not found.")
    if not page.get("ready"):
        raise HTTPException(status_code=409, detail="Report job is not completed.")
    result = {"success": True, "columns": page.get("columns", []), "rows": page.get("rows", []), "returned_rows": len(page.get("rows", [])), "total_rows": page.get("total_rows", 0)}
    return build_visualization_response(result=result, visualization=visualization, category_field=category_field, value_field=value_field, aggregation=aggregation, limit=limit)


@app.post("/execution/jobs/{job_id}/cancel", dependencies=[Depends(require_app_access)])
def cancel_report_job(job_id: str, user: dict = Depends(require_app_access)):
    _require_job_access(job_id, user)
    cancelled = EXECUTION_MANAGER.cancel(job_id)
    if not cancelled:
        job = EXECUTION_MANAGER.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Report job not found.")
        return {
            "success": False,
            "message": "Job cannot be cancelled in its current state.",
            "job": job,
        }
    return {
        "success": True,
        "message": "Report job cancellation requested.",
        "job": EXECUTION_MANAGER.get(job_id),
    }


@app.get("/system/security", summary="Security Runtime Status")
def security_runtime_status(user: dict = Depends(require_admin)):
    """Return non-secret security configuration for administrators."""
    return {
        "success": True,
        "security": validate_runtime(),
    }
