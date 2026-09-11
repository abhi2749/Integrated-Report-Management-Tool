from pathlib import Path

from metadata_repository import SqliteMetadataRepository, create_metadata_repository


def test_sqlite_repository_migrates_legacy_json(tmp_path: Path):
    legacy = tmp_path / "users.json"
    legacy.write_text('[{"id":"user_1","username":"admin","active":true}]', encoding="utf-8")
    db = tmp_path / "metadata.db"

    repo = create_metadata_repository(
        legacy,
        backend="sqlite",
        collection="users",
        db_path=db,
    )

    assert repo.read() == [{"id": "user_1", "username": "admin", "active": True}]
    assert db.exists()
    assert (tmp_path / "users.json.pre_sqlite.bak").exists()


def test_sqlite_repository_preserves_item_order_and_replaces_atomically(tmp_path: Path):
    repo = SqliteMetadataRepository(tmp_path / "metadata.db", "datasets")

    first = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    repo.write(first)
    assert repo.read() == first

    second = [{"id": "c", "name": "C"}]
    repo.write(second)
    assert repo.read() == second


def test_json_backend_remains_available(tmp_path: Path):
    legacy = tmp_path / "connections.json"
    repo = create_metadata_repository(legacy, backend="json")
    repo.write([{"id": "conn_1"}])
    assert repo.read() == [{"id": "conn_1"}]
