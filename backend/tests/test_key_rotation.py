from cryptography.fernet import Fernet


def test_encryption_previous_key_fallback(monkeypatch):
    from security import decrypt_secret, encrypt_secret

    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", old_key)
    monkeypatch.delenv("ENCRYPTION_KEY_PREVIOUS", raising=False)
    token = encrypt_secret("db-password")

    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("ENCRYPTION_KEY_PREVIOUS", old_key)
    assert decrypt_secret(token) == "db-password"


def test_new_encryption_writes_use_active_key(monkeypatch):
    from security import decrypt_secret, encrypt_secret

    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("ENCRYPTION_KEY_PREVIOUS", old_key)
    token = encrypt_secret("new-password")

    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.delenv("ENCRYPTION_KEY_PREVIOUS", raising=False)
    assert decrypt_secret(token) == "new-password"


def test_auth_previous_key_accepts_existing_token(monkeypatch, tmp_path):
    monkeypatch.setenv("KEYRING_ALLOW_ENV_OVERRIDE", "true")
    monkeypatch.setenv("KEYRING_FILE", str(tmp_path / "keyring.json"))
    old_key = "old-secret-key-for-step-7b-rotation-123456789"
    new_key = "new-secret-key-for-step-7b-rotation-123456789"
    monkeypatch.setenv("SECRET_KEY", old_key)
    monkeypatch.delenv("SECRET_KEY_PREVIOUS", raising=False)
    import importlib
    import key_manager
    importlib.reload(key_manager)
    import auth
    importlib.reload(auth)
    from auth import create_access_token, verify_access_token

    token = create_access_token("u1", "user1")

    monkeypatch.setenv("SECRET_KEY", new_key)
    monkeypatch.setenv("SECRET_KEY_PREVIOUS", old_key)
    claims = verify_access_token(token)
    assert claims["user_id"] == "u1"


def test_registry_rotation_reencrypts_without_exposing_secret(monkeypatch, tmp_path):
    import connection_registry as registry
    from security import decrypt_secret, encrypt_secret

    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("ENCRYPTION_KEY_PREVIOUS", old_key)

    monkeypatch.setenv("ENCRYPTION_KEY", old_key)
    old_token = encrypt_secret("password-1")
    monkeypatch.setenv("ENCRYPTION_KEY", new_key)

    items = [{"id": "c1", "password": old_token, "name": "test"}]
    written = []
    monkeypatch.setattr(registry, "_read_raw", lambda: items)
    monkeypatch.setattr(registry, "_write_raw", lambda value: written.append(value))
    monkeypatch.setattr(registry, "_ensure_file", lambda: None)
    monkeypatch.setattr(registry, "REGISTRY_FILE", tmp_path / "connections.json")
    monkeypatch.setattr(registry, "REGISTRY_DIR", tmp_path)

    result = registry.rotate_encrypted_passwords()
    assert result == {"total_connections": 1, "rotated_passwords": 1}
    assert len(written) == 1
    rotated = written[0][0]["password"]
    assert decrypt_secret(rotated) == "password-1"
    assert rotated != old_token
