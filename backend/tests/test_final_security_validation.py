from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_production_compose_is_localhost_bound_and_privilege_restricted():
    compose = read("docker-compose.yml")
    assert 'published: "0"' in compose
    assert "no-new-privileges:true" in compose
    assert compose.count("cap_drop:") >= 2
    assert 'cap_add:' in compose and 'NET_BIND_SERVICE' in compose
    assert "init: true" in compose


def test_production_automatic_secrets_and_previous_keys_are_supported():
    compose = read("docker-compose.yml")
    env_example = read("backend/.env.example")
    startup = read("backend/startup_validation.py")
    assert 'ENCRYPTION_KEY: "${ENCRYPTION_KEY:-}"' in compose
    assert 'SECRET_KEY: "${SECRET_KEY:-}"' in compose
    config = read("backend/config.py")
    assert "ensure_keys" in config
    assert "SECRET_KEY_PREVIOUS" in compose
    assert "ENCRYPTION_KEY_PREVIOUS" in compose
    assert "SECRET_KEY_PREVIOUS" in startup
    assert "ENCRYPTION_KEY_PREVIOUS" in startup
    assert "Never print or commit real key values." in env_example


def test_container_image_does_not_include_backend_env_or_test_artifacts():
    dockerfile = read("backend/Dockerfile")
    assert "rm -rf" in dockerfile
    assert ".env" in dockerfile
    assert "tests" in dockerfile
