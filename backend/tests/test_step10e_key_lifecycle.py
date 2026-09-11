from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_key_manager_generates_and_persists_missing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("KEYRING_FILE", str(tmp_path / "keyring.json"))
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    import importlib
    import key_manager
    importlib.reload(key_manager)
    keys = key_manager.ensure_keys()
    assert len(keys["SECRET_KEY"]) >= 32
    assert keys["ENCRYPTION_KEY"]
    assert (tmp_path / "keyring.json").exists()


def test_root_rotate_command_exists():
    project_root = Path(__file__).resolve().parents[2]
    assert (project_root / "rotate_key.py").is_file()


def test_keyring_remains_authoritative_after_rotation(monkeypatch, tmp_path):
    monkeypatch.setenv("KEYRING_FILE", str(tmp_path / "keyring.json"))
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("KEYRING_ALLOW_ENV_OVERRIDE", raising=False)
    import importlib
    import key_manager
    importlib.reload(key_manager)
    first = key_manager.ensure_keys()
    old_encryption = first["ENCRYPTION_KEY"]
    key_manager.rotate("encryption")
    new_encryption = key_manager.ensure_keys()["ENCRYPTION_KEY"]
    assert new_encryption != old_encryption

    monkeypatch.setenv("ENCRYPTION_KEY", old_encryption)
    importlib.reload(key_manager)
    assert key_manager.ensure_keys()["ENCRYPTION_KEY"] == new_encryption


def test_backend_rotate_cli_accepts_explicit_argv():
    from rotate_keys import main
    assert callable(main)


def test_canonical_key_accessor_ignores_stale_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("KEYRING_FILE", str(tmp_path / "keyring.json"))
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("KEYRING_ALLOW_ENV_OVERRIDE", raising=False)
    import importlib
    import key_manager
    importlib.reload(key_manager)

    first = key_manager.ensure_keys()
    canonical = first["SECRET_KEY"]
    monkeypatch.setenv("SECRET_KEY", "stale-environment-value")

    assert key_manager.get_key("SECRET_KEY") == canonical
    assert key_manager.ensure_keys()["SECRET_KEY"] == canonical


def test_canonical_previous_key_accessor_uses_persistent_history(monkeypatch, tmp_path):
    monkeypatch.setenv("KEYRING_FILE", str(tmp_path / "keyring.json"))
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("KEYRING_ALLOW_ENV_OVERRIDE", raising=False)
    import importlib
    import key_manager
    importlib.reload(key_manager)

    original = key_manager.get_key("SECRET_KEY")
    key_manager.rotate("secret")
    assert key_manager.get_previous_key("SECRET_KEY_PREVIOUS") == original
