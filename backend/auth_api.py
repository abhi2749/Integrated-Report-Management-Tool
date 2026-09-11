"""
Custom Reporting Tool
Security Phase - Step 3C/3D Authentication API
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from permissions import (
    ALL_PERMISSIONS,
    PERMISSION_DEFINITIONS,
    normalize_permissions,
)

from auth import (
    AuthenticationTokenError,
    TOKEN_EXPIRE_SECONDS,
    create_access_token,
    revoke_access_token,
    verify_access_token,
)
from auth_session_registry import register_token, revoke_user_tokens
from api_security import sanitize_error_message

from user_registry import (
    authenticate_user,
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    safe_user,
    update_user,
)


router = APIRouter(prefix="/auth", tags=["authentication"])

bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    auto_error=False,
)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str
    expires_in: int
    user: dict



class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=1024)
    role: str = Field(default="custom", min_length=1, max_length=30)
    permissions: list[str] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, min_length=1, max_length=30)
    password: str | None = Field(default=None, min_length=8, max_length=1024)
    permissions: list[str] | None = None
    active: bool | None = None


def _unauthorized(detail: str = "Authentication required.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise _unauthorized()

    try:
        claims = verify_access_token(credentials.credentials)
    except AuthenticationTokenError as exc:
        raise _unauthorized(sanitize_error_message(exc, "Authentication failed.")) from exc

    user = get_user_by_id(claims["user_id"])

    if not user or not bool(user.get("active", True)):
        raise _unauthorized("User is inactive or no longer exists.")

    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if str(user.get("role", "")).lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permission required.",
        )
    return user


@router.post("/login", response_model=LoginResponse, summary="Login")
def login(payload: LoginRequest):
    user = authenticate_user(payload.username, payload.password)

    if not user:
        raise _unauthorized("Invalid username or password.")

    token = create_access_token(
        user_id=str(user["id"]),
        username=str(user["username"]),
        role=str(user.get("role", "report_user")),
    )

    register_token(token, str(user["id"]), int(time.time()) + TOKEN_EXPIRE_SECONDS)

    return LoginResponse(
        success=True,
        access_token=token,
        token_type="bearer",
        expires_in=TOKEN_EXPIRE_SECONDS,
        user=safe_user(user),
    )


@router.get("/permissions", summary="Available Permissions")
def available_permissions(user: dict = Depends(require_admin)):
    return {
        "success": True,
        "permissions": PERMISSION_DEFINITIONS,
        "all_permissions": sorted(ALL_PERMISSIONS),
    }


@router.get("/users", summary="List Users")
def users_list(user: dict = Depends(require_admin)):
    return {"success": True, "users": list_users()}


@router.post("/users", summary="Create User")
def users_create(payload: UserCreateRequest, user: dict = Depends(require_admin)):
    try:
        permissions = normalize_permissions(payload.permissions)

        if payload.role == "admin":
            permissions = None

        created = create_user(
            payload.username,
            payload.password,
            payload.role,
            permissions,
        )
        return {"success": True, "user": created}
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=400, detail=sanitize_error_message(error, "Invalid user request.")) from error


@router.put("/users/{user_id}", summary="Update User")
def users_update(
    user_id: str,
    payload: UserUpdateRequest,
    user: dict = Depends(require_admin),
):
    if user_id == user.get("id") and payload.active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")

    try:
        permissions = None if payload.permissions is None else normalize_permissions(payload.permissions)
        updated = update_user(
            user_id,
            role=payload.role,
            permissions=permissions,
            password=payload.password,
            active=payload.active,
        )
        if updated and (payload.password is not None or payload.active is not None):
            revoke_user_tokens(user_id)
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=400, detail=sanitize_error_message(error, "Invalid user request.")) from error

    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")

    return {"success": True, "user": updated}


@router.delete("/users/{user_id}", summary="Delete User")
def users_delete(user_id: str, user: dict = Depends(require_admin)):
    if user_id == user.get("id"):
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if target.get("role") == "admin":
        from user_registry import _read as _read_users
        admins = [item for item in _read_users() if item.get("role") == "admin" and item.get("active", True)]
        if len(admins) <= 1:
            raise HTTPException(status_code=400, detail="The last active administrator cannot be deleted.")

    revoke_user_tokens(user_id)
    delete_user(user_id)
    return {"success": True, "message": "User deleted successfully."}


@router.get("/me", summary="Current User")
def current_user(user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "user": safe_user(user),
    }


@router.post("/logout", summary="Logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None:
        raise _unauthorized()

    token = credentials.credentials

    try:
        claims = verify_access_token(token)
    except AuthenticationTokenError as exc:
        raise _unauthorized(sanitize_error_message(exc, "Authentication failed.")) from exc

    revoke_access_token(
        token,
        int(claims["expires_at"]),
    )

    return {
        "success": True,
        "message": "Logout successful.",
        "user_id": claims["user_id"],
    }
