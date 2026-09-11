"""Persistent automatic application key lifecycle for ReportingTool."""
from __future__ import annotations

import base64
import json
import os
import secrets
from pathlib import Path
from threading import RLock

from cryptography.fernet import Fernet

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
KEYRING_FILE = Path(os.getenv("KEYRING_FILE", str(DATA_DIR / "keyring.json"))).resolve()
_LOCK = RLock()


def _generate(kind: str) -> str:
    if kind == "encryption":
        return Fernet.generate_key().decode("utf-8")
    if kind == "secret":
        return secrets.token_urlsafe(48)
    raise ValueError(f"Unsupported key type: {kind}")


def _read() -> dict:
    if not KEYRING_FILE.exists():
        return {}
    try:
        value = json.loads(KEYRING_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Persistent keyring is unreadable; refusing to generate replacement keys.") from exc


def _write(value: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = KEYRING_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    temp.replace(KEYRING_FILE)


def ensure_keys() -> dict[str, str]:
    """Ensure stable application keys exist and expose them through process env.

    The persistent keyring is authoritative once initialized. Environment
    values are used only to seed a missing keyring entry, or when the caller
    explicitly enables KEYRING_ALLOW_ENV_OVERRIDE. This prevents a rotated
    key from being silently reverted on container restart because Compose
    still contains the pre-rotation environment value.
    """
    with _LOCK:
        ring = _read()
        changed = False
        allow_override = os.getenv("KEYRING_ALLOW_ENV_OVERRIDE", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        mapping = {
            "SECRET_KEY": "secret",
            "ENCRYPTION_KEY": "encryption",
        }
        for env_name, kind in mapping.items():
            ring_value = str(ring.get(env_name, "")).strip()
            env_value = os.getenv(env_name, "").strip()

            if ring_value and not allow_override:
                value = ring_value
            elif env_value:
                value = env_value
            elif ring_value:
                value = ring_value
            else:
                value = _generate(kind)

            if ring.get(env_name) != value:
                ring[env_name] = value
                changed = True
            os.environ[env_name] = value

        for name in ("SECRET_KEY_PREVIOUS", "ENCRYPTION_KEY_PREVIOUS"):
            ring_previous = str(ring.get(name, "")).strip()
            env_previous = os.getenv(name, "").strip()
            previous = ring_previous or env_previous
            if previous:
                if ring.get(name) != previous:
                    ring[name] = previous
                    changed = True
                os.environ[name] = previous

        if changed or not KEYRING_FILE.exists():
            _write(ring)
        return {
            key: str(value)
            for key, value in ring.items()
            if key.endswith("KEY") or key.endswith("KEY_PREVIOUS")
        }

def get_key(name: str) -> str:
    """Return the canonical active application key from the persistent keyring.

    Environment variables remain a compatibility/bootstrap surface, but runtime
    consumers should use this accessor so an external environment mutation cannot
    silently replace the persistent active key.
    """
    if name not in {"SECRET_KEY", "ENCRYPTION_KEY"}:
        raise ValueError(f"Unsupported key name: {name}")
    keys = ensure_keys()
    value = str(keys.get(name, "")).strip()
    if not value:
        raise RuntimeError(f"Persistent keyring does not contain {name}.")
    return value


def get_previous_key(name: str) -> str | None:
    """Return the canonical retained previous key, when one exists."""
    if name not in {"SECRET_KEY_PREVIOUS", "ENCRYPTION_KEY_PREVIOUS"}:
        raise ValueError(f"Unsupported previous key name: {name}")
    keys = ensure_keys()
    value = str(keys.get(name, "")).strip()
    return value or None

def rotate(kind: str) -> dict[str, str]:
    """Generate and persist a new key while retaining the old key as previous."""
    env_name = "ENCRYPTION_KEY" if kind == "encryption" else "SECRET_KEY"
    previous_name = f"{env_name}_PREVIOUS"
    with _LOCK:
        ensure_keys()
        old = os.getenv(env_name, "").strip()
        new = _generate(kind)
        ring = _read()
        ring[previous_name] = old
        ring[env_name] = new
        _write(ring)
        os.environ[env_name] = new
        os.environ[previous_name] = old
        return {"active": new, "previous": old}


def rollback(kind: str) -> None:
    env_name = "ENCRYPTION_KEY" if kind == "encryption" else "SECRET_KEY"
    previous_name = f"{env_name}_PREVIOUS"
    with _LOCK:
        ring = _read()
        old = str(ring.get(previous_name, "")).strip()
        if not old:
            raise RuntimeError(f"No previous {env_name} is available for rollback.")
        current = str(ring.get(env_name, "")).strip()
        ring[env_name] = old
        if current:
            ring[previous_name] = current
        else:
            ring.pop(previous_name, None)
        _write(ring)
        os.environ[env_name] = old
        if current:
            os.environ[previous_name] = current
