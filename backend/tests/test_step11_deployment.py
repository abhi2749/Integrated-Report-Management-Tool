from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_compose_uses_docker_managed_loopback_ports():
    compose = read("docker-compose.yml")
    assert 'target: 8000' in compose
    assert 'target: 80' in compose
    assert 'published: "0"' in compose
    assert '127.0.0.1:8000:8000' not in compose
    assert '8080:80' not in compose


def test_compose_uses_same_origin_frontend_proxy_without_fixed_cors_origin():
    compose = read("docker-compose.yml")
    assert 'CORS_ORIGINS: "${CORS_ORIGINS:-}"' in compose
    nginx = read("frontend-ui/nginx.conf")
    assert 'proxy_pass http://backend:8000;' in nginx
    assert 'proxy_read_timeout 300s;' in nginx


def test_launchers_are_repository_relative_and_use_docker_compose():
    ps1 = read("scripts/start.ps1")
    sh = read("scripts/start.sh")
    assert "'compose', 'up', '-d'" in ps1
    assert 'docker compose port frontend 80' in ps1
    assert 'docker compose up -d' in sh
    assert 'docker compose port frontend 80' in sh
    assert 'C:\\' not in ps1


def test_launchers_validate_required_files_and_compose():
    ps1 = read("scripts/start.ps1")
    sh = read("scripts/start.sh")
    assert "Require-File 'docker-compose.yml'" in ps1
    assert "Require-File 'backend/Dockerfile'" in ps1
    assert "Require-File 'frontend-ui/Dockerfile'" in ps1
    assert "docker compose version" in ps1
    assert "for required in docker-compose.yml backend/Dockerfile frontend-ui/Dockerfile frontend-ui/nginx.conf" in sh
    assert "docker compose version" in sh


def test_launchers_wait_for_health_before_publishing_url():
    ps1 = read("scripts/start.ps1")
    sh = read("scripts/start.sh")
    assert ".State.Health.Status" in ps1
    assert "did not become healthy within 3 minutes" in ps1
    assert ".State.Health.Status" in sh
    assert "did not become healthy within 3 minutes" in sh


def test_launchers_support_safe_rebuild_and_browser_options():
    ps1 = read("scripts/start.ps1")
    sh = read("scripts/start.sh")
    assert '[switch]$NoBrowser' in ps1
    assert '[switch]$Rebuild' in ps1
    assert 'if ($Rebuild) { $args += \'--build\' }' in ps1
    assert '--rebuild' in sh
    assert '--no-browser' in sh
    assert 'docker compose up -d --build' in sh
    assert 'Unknown launcher option' in sh


def test_product_branding_is_correct_and_sidebar_is_icon_only():
    app = read("frontend-ui/src/App.jsx")
    index = read("frontend-ui/index.html")
    config = read("backend/config.py")
    compose = read("docker-compose.yml")
    assert 'Integrated Report Management Tool' in app
    assert 'Integrated Report Management Tool' in index
    assert 'Integrated Report Management Tool' in config
    assert 'Integrated Report Management Tool' in compose
    assert 'app-sidebar-brand-mark"\n              src="/favicon.svg"' in app
    assert 'Intergrated Report Management Tool' not in app


def test_dependency_manifests_are_present_and_docker_uses_locked_python_requirements():
    assert (ROOT / "backend" / "requirements.lock").is_file()
    assert (ROOT / "frontend-ui" / "package-lock.json").is_file()
    dockerfile = read("backend/Dockerfile")
    assert 'requirements.lock' in dockerfile
    frontend = read("frontend-ui/Dockerfile")
    assert 'npm ci' in frontend
