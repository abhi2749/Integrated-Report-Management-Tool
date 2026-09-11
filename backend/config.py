"""Custom Reporting Tool - centralized production configuration foundation."""
from __future__ import annotations
import os
from pathlib import Path

from key_manager import ensure_keys, get_key
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")

# Automatically recover/generate stable application keys before configuration
# values are read. Explicit environment values remain authoritative.
ensure_keys()

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc

def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]

APP_NAME = os.getenv("APP_NAME", "Integrated Report Management Tool")
APP_VERSION = os.getenv("APP_VERSION", "0.8.0")
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
APP_DEBUG = _env_bool("APP_DEBUG", APP_ENV == "development")
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = _env_int("APP_PORT", 8000)
CORS_ORIGINS = _env_list("CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"])
CORS_ALLOW_CREDENTIALS = _env_bool("CORS_ALLOW_CREDENTIALS", True)
SECURE_COOKIES = _env_bool("SECURE_COOKIES", APP_ENV == "production")
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
REPORTS_FILE = Path(os.getenv("REPORTS_FILE", str(DATA_DIR / "saved_reports.json"))).resolve()
METADATA_BACKEND = os.getenv("METADATA_BACKEND", "sqlite").strip().lower()
METADATA_DB_FILE = Path(os.getenv("METADATA_DB_FILE", str(DATA_DIR / "metadata.db"))).resolve()
if METADATA_BACKEND not in {"sqlite", "json"}:
    raise RuntimeError("METADATA_BACKEND must be either sqlite or json.")
SECRET_KEY = get_key("SECRET_KEY")
ENCRYPTION_KEY = get_key("ENCRYPTION_KEY")
AUTH_PBKDF2_ITERATIONS = _env_int("AUTH_PBKDF2_ITERATIONS", 600000)
AUTH_TOKEN_EXPIRE_SECONDS = _env_int("AUTH_TOKEN_EXPIRE_SECONDS", 3600)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

IMPORT_DATA_DIR = Path(os.getenv("IMPORT_DATA_DIR", str(DATA_DIR / "imports"))).resolve()
MAX_IMPORT_FILE_MB = _env_int("MAX_IMPORT_FILE_MB", 0)
IMPORT_PREVIEW_ROWS = max(1, min(_env_int("IMPORT_PREVIEW_ROWS", 25), 100))
EXECUTION_INLINE_RESULT_ROWS = _env_int("EXECUTION_INLINE_RESULT_ROWS", 5000)
EXECUTION_INLINE_RESULT_BYTES = _env_int("EXECUTION_INLINE_RESULT_BYTES", 8 * 1024 * 1024)
EXECUTION_RESULT_DB_PATH = Path(os.getenv("EXECUTION_RESULT_DB_PATH", str(DATA_DIR / "execution_results.sqlite3"))).expanduser().resolve()
EXECUTION_JOB_DB_PATH = Path(os.getenv("EXECUTION_JOB_DB_PATH", str(DATA_DIR / "execution_jobs.sqlite3"))).expanduser().resolve()
LOG_DIR = Path(os.getenv("LOG_DIR", str(BASE_DIR / "logs"))).expanduser().resolve()

MAX_QUERY_ROWS = _env_int("MAX_QUERY_ROWS", 0)  # 0 = no artificial report-row ceiling
QUERY_TIMEOUT_SECONDS = _env_int("QUERY_TIMEOUT_SECONDS", 0)  # 0 = no artificial execution-time ceiling
QUERY_CHUNK_SIZE = _env_int("QUERY_CHUNK_SIZE", 5000)
QUERY_PUSHDOWN_ENABLED = os.getenv("QUERY_PUSHDOWN_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
MAX_CONCURRENT_REPORTS = _env_int("MAX_CONCURRENT_REPORTS", 0)  # 0 = adaptive runtime sizing
REPORT_RESOURCE_WAIT_SECONDS = _env_int("REPORT_RESOURCE_WAIT_SECONDS", 30)
REPORT_JOB_RETENTION_SECONDS = _env_int("REPORT_JOB_RETENTION_SECONDS", 3600)
EXECUTION_WORKERS = _env_int("EXECUTION_WORKERS", 0)  # 0 = adaptive runtime sizing

MAX_EXPORT_FILE_MB = _env_int("MAX_EXPORT_FILE_MB", 0)  # 0 = no artificial export-size ceiling
MAX_JOIN_MEMORY_MB = _env_int("MAX_JOIN_MEMORY_MB", 1024)

MAX_REQUEST_BODY_MB = _env_int("MAX_REQUEST_BODY_MB", 0)  # 0 = no artificial request-body ceiling
MAX_JOIN_OPERATIONS = _env_int("MAX_JOIN_OPERATIONS", 0)  # 0 = no artificial JOIN-operation ceiling
BACKUP_RETENTION_COUNT = _env_int("BACKUP_RETENTION_COUNT", 10)
BACKUP_EXTERNAL_DIR = os.getenv("BACKUP_EXTERNAL_DIR", "").strip()
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(BASE_DIR / "backups"))).expanduser().resolve()

MAX_PREVIEW_ROWS = _env_int("MAX_PREVIEW_ROWS", 0)  # 0 = no artificial preview-row ceiling; browser uses bounded windows
MAX_VISUALIZATION_ROWS = _env_int("MAX_VISUALIZATION_ROWS", 0)  # 0 = no artificial visualization-data ceiling
MAX_JOIN_DATASETS = _env_int("MAX_JOIN_DATASETS", 0)  # 0 = no artificial JOIN-dataset ceiling

def configuration_summary() -> dict:
    return {
        "app_name": APP_NAME, "app_version": APP_VERSION, "app_env": APP_ENV,
        "app_debug": APP_DEBUG, "app_host": APP_HOST, "app_port": APP_PORT,
        "cors_origins": CORS_ORIGINS, "data_dir": str(DATA_DIR),
        "reports_file": str(REPORTS_FILE),
        "metadata_backend": METADATA_BACKEND,
        "metadata_db_file": str(METADATA_DB_FILE),
        "secret_key_configured": bool(SECRET_KEY),
        "encryption_key_configured": bool(ENCRYPTION_KEY),
        "auth_pbkdf2_iterations": AUTH_PBKDF2_ITERATIONS,
        "auth_token_expire_seconds": AUTH_TOKEN_EXPIRE_SECONDS,
        "cors_allow_credentials": CORS_ALLOW_CREDENTIALS,
        "secure_cookies": SECURE_COOKIES,
        "log_level": LOG_LEVEL,
        "import_data_dir": str(IMPORT_DATA_DIR),
        "max_import_file_mb": MAX_IMPORT_FILE_MB,
        "import_preview_rows": IMPORT_PREVIEW_ROWS,
        "execution_inline_result_rows": EXECUTION_INLINE_RESULT_ROWS,
        "execution_inline_result_bytes": EXECUTION_INLINE_RESULT_BYTES,
        "execution_result_db_path": str(EXECUTION_RESULT_DB_PATH),
        "execution_job_db_path": str(EXECUTION_JOB_DB_PATH),
        "log_dir": str(LOG_DIR),
    "backup_retention_count": BACKUP_RETENTION_COUNT,
    "backup_external_dir": BACKUP_EXTERNAL_DIR, "backup_dir": str(BACKUP_DIR), "max_query_rows": MAX_QUERY_ROWS,
    "query_timeout_seconds": QUERY_TIMEOUT_SECONDS,
    "query_chunk_size": QUERY_CHUNK_SIZE,
    "query_pushdown_enabled": QUERY_PUSHDOWN_ENABLED,
    "max_concurrent_reports": MAX_CONCURRENT_REPORTS,
    "report_resource_wait_seconds": REPORT_RESOURCE_WAIT_SECONDS,
    "report_job_retention_seconds": REPORT_JOB_RETENTION_SECONDS,
    "execution_workers": EXECUTION_WORKERS,

    "max_export_file_mb": MAX_EXPORT_FILE_MB,
    "max_join_memory_mb": MAX_JOIN_MEMORY_MB,
    "max_request_body_mb": MAX_REQUEST_BODY_MB,
    "max_join_operations": MAX_JOIN_OPERATIONS,
        "max_preview_rows": MAX_PREVIEW_ROWS,
        "max_visualization_rows": MAX_VISUALIZATION_ROWS,
        "max_join_datasets": MAX_JOIN_DATASETS,
    }
