from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_backend_port_is_host_local_only_in_production_compose():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'published: "0"' in compose
    assert '"8000:8000"' not in compose


def test_frontend_nginx_has_baseline_security_headers():
    nginx = (ROOT / "frontend-ui" / "nginx.conf").read_text(encoding="utf-8")
    required = [
        'server_tokens off;',
        'add_header X-Content-Type-Options "nosniff" always;',
        'add_header X-Frame-Options "DENY" always;',
        'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
        'add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;',
        'add_header Cross-Origin-Opener-Policy "same-origin" always;',
        'add_header Cross-Origin-Resource-Policy "same-origin" always;',
    ]
    for header in required:
        assert header in nginx


def test_frontend_nginx_blocks_hidden_files():
    nginx = (ROOT / "frontend-ui" / "nginx.conf").read_text(encoding="utf-8")
    assert 'location ~ /\\.' in nginx
    assert 'deny all;' in nginx
