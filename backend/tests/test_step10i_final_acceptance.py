"""Step 10I final production acceptance checks.

These checks intentionally avoid external database credentials. They validate
production-facing contracts that must remain true after Steps 10A-10H.
"""
from pathlib import Path
import os
import sys


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_liveness_and_readiness_contract():
    main_text = _read("backend/main.py")
    assert '@app.get("/health")' in main_text
    assert '@app.get("/ready")' in main_text
    assert '"status": "healthy"' in main_text
    assert '"status": "ready"' in main_text


def test_execution_manager_has_no_client_result_ceiling():
    manager = _read("backend/execution_manager.py")
    client = _read("frontend-ui/src/executionClient.js")
    assert "ResultStore" in manager
    assert "ThreadPoolExecutor" in manager
    assert "DEFAULT_TIMEOUT_MS = 0" in client
    assert "timeoutMs" in client
    assert "timedOut" in client or "setTimeout" in client


def test_result_store_and_export_are_disk_backed():
    result_store = _read("backend/result_store.py")
    export_manager = _read("backend/export_manager.py")
    assert "sqlite3" in result_store
    assert "WAL" in result_store
    assert "ThreadPoolExecutor" in export_manager
    assert "submit" in export_manager


def test_persistent_job_store_and_keyring_are_present():
    assert (BACKEND / "persistent_job_store.py").is_file()
    assert (BACKEND / "key_manager.py").is_file()
    assert (BACKEND / "data" / "keyring.json").is_file() or os.getenv("APP_ENV") != "production"


def test_production_docker_contract_files_are_present():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    backend_dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    frontend_dockerfile = (ROOT / "frontend-ui" / "Dockerfile").read_text(encoding="utf-8")
    assert "/ready" in compose
    assert "healthcheck:" in compose
    assert "requirements.lock" in backend_dockerfile
    assert "npm ci" in frontend_dockerfile
    assert (BACKEND / ".dockerignore").is_file()
    assert (ROOT / "frontend-ui" / ".dockerignore").is_file()


def test_frontend_production_contracts_are_present():
    frontend = ROOT / "frontend-ui" / "src"
    execution_client = (frontend / "executionClient.js").read_text(encoding="utf-8")
    cache = (frontend / "resultWindowCache.js").read_text(encoding="utf-8")
    report_builder = (frontend / "ReportBuilder.jsx").read_text(encoding="utf-8")
    assert "signal" in execution_client
    assert "cancelExecutionJob" in execution_client
    assert "runExecutionExportJob" in execution_client
    assert "maxBytes" in cache
    assert "cachedBytes" in cache
    assert "runExecutionExportJob" in report_builder


def test_no_runtime_secret_values_are_committed_in_docker_contexts():
    for rel in ("backend/.dockerignore", "frontend-ui/.dockerignore"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert ".env" in text
    assert ".env" in (ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8")
