from __future__ import annotations

import json

import pytest

from metadata_repository import (
    JsonMetadataRepository,
    create_metadata_repository,
)


def test_json_repository_round_trip_and_atomic_write(tmp_path):
    path = tmp_path / "metadata.json"
    repository = JsonMetadataRepository(path)

    assert repository.read() == []

    items = [{"id": "one", "name": "First"}]
    repository.write(items)

    assert json.loads(path.read_text(encoding="utf-8")) == items
    assert repository.read() == items
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_factory_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("METADATA_BACKEND", raising=False)

    repository = create_metadata_repository(
        tmp_path / "metadata.json",
        collection="test_collection",
        db_path=tmp_path / "metadata.db",
    )

    from metadata_repository import SqliteMetadataRepository
    assert isinstance(repository, SqliteMetadataRepository)


def test_factory_can_select_json(tmp_path):
    repository = create_metadata_repository(tmp_path / "metadata.json", backend="json")
    assert isinstance(repository, JsonMetadataRepository)


def test_factory_rejects_unknown_backend(tmp_path):
    with pytest.raises(RuntimeError, match="Unsupported METADATA_BACKEND"):
        create_metadata_repository(tmp_path / "metadata.json", backend="unknown")
