from semantic_metadata_service import build_semantic_model, consistency_report, normalize_data_type


def test_semantic_metadata_covers_all_physical_columns():
    dataset = {
        "id": "d1", "name": "Meter Data",
        "columns": [
            {"name": "ZONE", "data_type": "varchar"},
            {"name": "KWH", "data_type": "decimal"},
            {"name": "READING_DATE", "data_type": "datetime"},
        ],
    }
    model = build_semantic_model(dataset)
    item = model.datasets[0]
    assert item.id == "semantic_d1"
    assert {f.physical_field for f in item.dimensions + item.measures} == {"ZONE", "KWH", "READING_DATE"}
    assert {f.physical_field for f in item.measures} == {"KWH"}


def test_data_types_normalize_to_semantic_vocabulary():
    assert normalize_data_type("varchar") == "string"
    assert normalize_data_type("BIGINT") == "integer"
    assert normalize_data_type("double") == "decimal"
    assert normalize_data_type("timestamp") == "datetime"


def test_semantic_consistency_detects_stale_fields():
    dataset = {"id": "d1", "columns": [{"name": "a", "data_type": "string"}]}
    model = build_semantic_model(dataset)
    model.datasets[0].dimensions[0].physical_field = "missing"
    report = consistency_report(dataset, model)
    assert report["consistent"] is False
    assert report["missing_semantic_fields"] == ["a"]
    assert report["stale_semantic_fields"] == ["missing"]
