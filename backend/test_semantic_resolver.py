from query_model import QueryDefinition
from semantic_model import SemanticDataset, SemanticDimension, SemanticMeasure, SemanticModel
from semantic_resolver import resolve_semantic_query


def model():
    return SemanticModel(datasets=[SemanticDataset(
        id="meter",
        name="Meter",
        physical_dataset_id="dataset_1",
        dimensions=[SemanticDimension(name="Zone", physical_field="ZONE")],
        measures=[SemanticMeasure(name="Energy", physical_field="KWH", data_type="decimal")],
    )])


def test_resolves_qualified_semantic_fields():
    query = QueryDefinition.model_validate({
        "datasets": [{"id": "d1", "database": "pspcl", "semantic_dataset_id": "meter"}],
        "columns": [{"field": "d1.Zone"}, {"field": "d1.Energy"}],
        "group_by": ["d1.Zone"],
        "aggregations": [{"function": "SUM", "field": "d1.Energy"}],
    })
    resolved = resolve_semantic_query(query, model())
    assert [item.field for item in resolved.columns] == ["d1.ZONE", "d1.KWH"]
    assert resolved.group_by == ["d1.ZONE"]
    assert resolved.aggregations[0].field == "d1.KWH"


def test_physical_fields_remain_unchanged():
    query = QueryDefinition.model_validate({
        "datasets": [{"id": "d1", "database": "pspcl", "semantic_dataset_id": "meter"}],
        "columns": [{"field": "d1.existing_column"}],
    })
    resolved = resolve_semantic_query(query, model())
    assert resolved.columns[0].field == "d1.existing_column"


def test_unknown_semantic_dataset_fails_explicitly():
    query = QueryDefinition.model_validate({
        "datasets": [{"id": "d1", "database": "pspcl", "semantic_dataset_id": "missing"}],
        "columns": [{"field": "d1.Zone"}],
    })
    try:
        resolve_semantic_query(query, model())
    except ValueError as exc:
        assert "Unknown semantic dataset" in str(exc)
    else:
        raise AssertionError("Expected semantic dataset validation failure")
