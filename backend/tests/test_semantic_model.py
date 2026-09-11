from semantic_model import (
    SemanticCalculatedMeasure,
    SemanticDataset,
    SemanticDimension,
    SemanticMeasure,
    SemanticModel,
    SemanticRelationship,
)


def test_semantic_dataset_supports_dimensions_and_measures():
    dataset = SemanticDataset(
        id="meter",
        name="Meter Data",
        physical_dataset_id="dataset_123",
        dimensions=[SemanticDimension(name="Zone", physical_field="ZONE", data_type="string")],
        measures=[SemanticMeasure(name="Energy", physical_field="KWH", data_type="decimal")],
    )

    assert dataset.field_names() == {"Zone", "Energy"}
    assert dataset.measures[0].default_aggregation == "SUM"


def test_semantic_calculated_measure_is_reusable_metadata():
    measure = SemanticCalculatedMeasure(
        name="Net Energy",
        expression="EnergyImport - EnergyExport",
        display_name="Net Energy",
    )

    assert measure.expression == "EnergyImport - EnergyExport"
    assert measure.data_type == "decimal"


def test_semantic_relationship_is_logical_not_query_specific():
    relationship = SemanticRelationship(
        name="Meter to Zone",
        left_dataset="meter",
        right_dataset="zone",
        left_field="ZoneId",
        right_field="Id",
    )

    assert relationship.relationship == "many_to_one"
    assert relationship.join_type == "LEFT"


def test_semantic_model_is_metadata_only():
    model = SemanticModel(
        datasets=[
            SemanticDataset(id="d1", name="Dataset 1", physical_dataset_id="physical-1")
        ]
    )

    assert model.version == 1
    assert model.datasets[0].physical_dataset_id == "physical-1"
    assert not hasattr(model.datasets[0], "rows")
