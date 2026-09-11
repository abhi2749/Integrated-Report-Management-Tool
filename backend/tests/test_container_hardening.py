from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


def _compose_text() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def test_backend_runtime_drops_capabilities_and_disables_privilege_escalation():
    text = _compose_text()
    backend = text.split("  frontend:", 1)[0]
    assert "init: true" in backend
    assert "no-new-privileges:true" in backend
    assert "cap_drop:" in backend
    assert "      - ALL" in backend
    assert 'published: "0"' in backend


def test_frontend_runtime_keeps_only_required_bind_capability():
    text = _compose_text()
    frontend = text.split("  frontend:", 1)[1].split("volumes:", 1)[0]
    assert "init: true" in frontend
    assert "no-new-privileges:true" in frontend
    assert "cap_drop:" in frontend
    assert "cap_add:" in frontend
    assert "      - NET_BIND_SERVICE" in frontend
    assert 'target: 80' in frontend and 'published: "0"' in frontend


def test_previous_keys_remain_optional_and_are_not_hardcoded():
    text = _compose_text()
    assert 'SECRET_KEY_PREVIOUS: "${SECRET_KEY_PREVIOUS:-}"' in text
    assert 'ENCRYPTION_KEY_PREVIOUS: "${ENCRYPTION_KEY_PREVIOUS:-}"' in text
    assert "CHANGE_ME" not in text
