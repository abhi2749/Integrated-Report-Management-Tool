"""
Custom Reporting Tool
Security Phase - Step 4: Custom User Permissions / RBAC

Backend-enforced permission catalogue. UI visibility is not relied upon
for security; every protected application route checks the permission
associated with the request.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import AuthenticationTokenError, verify_access_token
from api_security import sanitize_error_message


PERMISSION_DEFINITIONS = [
    {
        "key": "users.view",
        "label": "View Users",
        "description": "View users and their permission assignments.",
        "group": "User Management",
    },
    {
        "key": "users.create",
        "label": "Create Users",
        "description": "Create new users and assign custom permissions.",
        "group": "User Management",
    },
    {
        "key": "users.edit",
        "label": "Edit Users",
        "description": "Change user role, status, password, or permissions.",
        "group": "User Management",
    },
    {
        "key": "users.delete",
        "label": "Delete Users",
        "description": "Delete users while preserving the last active admin.",
        "group": "User Management",
    },
    {
        "key": "connections.view",
        "label": "View Connections",
        "description": "View saved database connections.",
        "group": "Data Sources",
    },
    {
        "key": "connections.create",
        "label": "Create Connections",
        "description": "Save new database connections.",
        "group": "Data Sources",
    },
    {
        "key": "connections.edit",
        "label": "Edit Connections",
        "description": "Modify saved database connections.",
        "group": "Data Sources",
    },
    {
        "key": "connections.delete",
        "label": "Delete Connections",
        "description": "Delete saved database connections.",
        "group": "Data Sources",
    },
    {
        "key": "connections.test",
        "label": "Test Connections",
        "description": "Test and discover databases, tables, columns, and previews.",
        "group": "Data Sources",
    },
    {
        "key": "datasets.view",
        "label": "View Datasets",
        "description": "View saved reporting datasets.",
        "group": "Datasets",
    },
    {
        "key": "datasets.create",
        "label": "Create Datasets",
        "description": "Create reporting datasets.",
        "group": "Datasets",
    },
    {
        "key": "datasets.edit",
        "label": "Edit Datasets",
        "description": "Modify reporting datasets.",
        "group": "Datasets",
    },
    {
        "key": "datasets.delete",
        "label": "Delete Datasets",
        "description": "Delete reporting datasets.",
        "group": "Datasets",
    },
    {
        "key": "data.preview",
        "label": "Preview Data",
        "description": "Preview source and dataset records.",
        "group": "Data Access",
    },
    {
        "key": "query.execute",
        "label": "Execute Queries",
        "description": "Execute reporting queries against permitted data sources.",
        "group": "Data Access",
    },
    {
        "key": "joins.execute",
        "label": "Execute Joins",
        "description": "Combine multiple reporting datasets.",
        "group": "Reporting",
    },
    {
        "key": "visualizations.use",
        "label": "Use Visualizations",
        "description": "Build and preview report charts.",
        "group": "Reporting",
    },
    {
        "key": "reports.view",
        "label": "View Reports",
        "description": "View saved report configurations.",
        "group": "Reports",
    },
    {
        "key": "reports.create",
        "label": "Create Reports",
        "description": "Save new report configurations.",
        "group": "Reports",
    },
    {
        "key": "reports.edit",
        "label": "Edit Reports",
        "description": "Modify saved report configurations.",
        "group": "Reports",
    },
    {
        "key": "reports.delete",
        "label": "Delete Reports",
        "description": "Delete saved report configurations.",
        "group": "Reports",
    },
    {
        "key": "reports.export",
        "label": "Export Reports",
        "description": "Export report results.",
        "group": "Reports",
    },
    {
        "key": "reports.print",
        "label": "Print Reports",
        "description": "Print report output.",
        "group": "Reports",
    },
    {
        "key": "profiling.use",
        "label": "Use Data Profiling",
        "description": "Use data profiling/field analysis features.",
        "group": "Data Access",
    },
]

ALL_PERMISSIONS = {item["key"] for item in PERMISSION_DEFINITIONS}

# Existing report_user accounts retain the full existing application workflow.
DEFAULT_REPORT_USER_PERMISSIONS = ALL_PERMISSIONS - {
    "users.view",
    "users.create",
    "users.edit",
    "users.delete",
}

ADMIN_ROLE = "admin"


def normalize_permissions(value) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, (list, tuple, set)):
        raise ValueError("Permissions must be a list.")

    normalized = []
    for item in value:
        key = str(item).strip()
        if key and key not in ALL_PERMISSIONS:
            raise ValueError(f"Unknown permission: {key}")
        if key and key not in normalized:
            normalized.append(key)

    return normalized


def permissions_for_user(user: dict) -> set[str]:
    if str(user.get("role", "")).strip().lower() == ADMIN_ROLE:
        return set(ALL_PERMISSIONS)

    stored = user.get("permissions")
    if stored is None:
        return set(DEFAULT_REPORT_USER_PERMISSIONS)

    return set(normalize_permissions(stored))


def has_permission(user: dict, permission: str) -> bool:
    return permission in permissions_for_user(user)


bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    auto_error=False,
)


def _authenticated_user_from_request(
    credentials: HTTPAuthorizationCredentials | None,
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = verify_access_token(credentials.credentials)
    except AuthenticationTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=sanitize_error_message(exc, "Authentication failed."),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    from user_registry import get_user_by_id
    user = get_user_by_id(claims["user_id"])
    if not user or not bool(user.get("active", True)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive or no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_permission(permission: str):
    def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> dict:
        user = _authenticated_user_from_request(credentials)
        if not has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}",
            )
        return user

    return dependency


def _permission_for_request(method: str, path: str) -> str | None:
    method = method.upper()

    # User management is exposed by auth_api and handles its own admin checks.
    if path.startswith("/auth/"):
        return None

    if path == "/datasource/connectors":
        return "connections.view"

    if path.startswith("/datasource/connections"):
        if path.endswith("/test") or "/databases" in path or "/tables" in path or path.endswith("/preview"):
            return "connections.test"
        if method == "GET":
            return "connections.view"
        if method == "POST":
            return "connections.create"
        if method == "PUT":
            return "connections.edit"
        if method == "DELETE":
            return "connections.delete"

    if path.startswith("/datasource/"):
        return "connections.test"

    if path == "/datasets" or path.startswith("/datasets/"):
        if method == "GET":
            return "datasets.view"
        if method == "POST":
            return "datasets.create"
        if method == "PUT":
            return "datasets.edit"
        if method == "DELETE":
            return "datasets.delete"

    if path in {"/dataset/preview"}:
        return "data.preview"

    if path.startswith("/report/visualization/"):
        return "visualizations.use"

    if path == "/join/execute":
        return "joins.execute"

    if path == "/report/query":
        return "query.execute"

    # Background report execution uses the same query-execution permission.
    # Authentication and authorization are enforced at the API boundary;
    # the existing ExecutionManager remains unchanged.
    if path == "/execution/jobs" or path.startswith("/execution/jobs/"):
        return "query.execute"

    if path == "/reports" or path.startswith("/reports/"):
        if method == "GET":
            return "reports.view"
        if method == "POST":
            return "reports.create"
        if method == "PUT":
            return "reports.edit"
        if method == "DELETE":
            return "reports.delete"

    if path == "/report/export/csv":
        return "reports.export"

    return None


def require_app_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    user = _authenticated_user_from_request(credentials)
    request.state.user = user
    permission = _permission_for_request(request.method, request.url.path)

    if permission is not None and not has_permission(user, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {permission}",
        )

    return user
