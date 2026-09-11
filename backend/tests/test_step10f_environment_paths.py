import importlib


def test_core_persistent_stores_follow_configured_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "portable-data"))

    import config
    import result_store
    import persistent_job_store
    import connection_registry
    import dataset_registry
    import user_registry
    import connection_access
    import auth_session_registry

    importlib.reload(config)
    for module in (result_store, persistent_job_store, connection_registry, dataset_registry, user_registry, connection_access, auth_session_registry):
        importlib.reload(module)

    expected = config.DATA_DIR.resolve()
    assert result_store._default_db_path().parent == expected
    assert persistent_job_store._default_path().parent == expected
    assert connection_registry.REGISTRY_DIR == expected
    assert dataset_registry.REGISTRY_DIR == expected
    assert user_registry.DATA_DIR == expected
    assert connection_access.DATA_DIR == expected
    assert auth_session_registry.DATA_DIR == expected
