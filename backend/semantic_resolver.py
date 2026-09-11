"""Resolve semantic field names to physical query fields.

The resolver is deliberately pure: it does not inspect data or execute SQL.
Existing physical-field queries remain unchanged when no semantic model is supplied.
"""
from __future__ import annotations

from copy import deepcopy

from query_model import QueryDefinition
from semantic_model import SemanticModel


def _field_map(model: SemanticModel, semantic_dataset_id: str) -> dict[str, str]:
    dataset = next((item for item in model.datasets if item.id == semantic_dataset_id), None)
    if not dataset:
        raise ValueError(f"Unknown semantic dataset: {semantic_dataset_id}")
    mapping = {field.name: field.physical_field for field in [*dataset.dimensions, *dataset.measures]}
    mapping.update({item.name: item.expression for item in dataset.calculated_measures})
    return mapping


def resolve_semantic_query(query: QueryDefinition, model: SemanticModel) -> QueryDefinition:
    """Return a physical-field QueryDefinition resolved from semantic names."""
    result = deepcopy(query)
    maps = {dataset.id: _field_map(model, dataset.semantic_dataset_id)
            for dataset in result.datasets if dataset.semantic_dataset_id}

    def resolve(value: str) -> str:
        if "." not in value:
            matches = {mapping[value] for mapping in maps.values() if value in mapping}
            if len(matches) == 1:
                return next(iter(matches))
            if len(matches) > 1:
                raise ValueError(f"Ambiguous semantic field: {value}")
            return value
        dataset_id, field = value.split(".", 1)
        mapping = maps.get(dataset_id)
        if not mapping or field not in mapping:
            return value
        return f"{dataset_id}.{mapping[field]}"

    for column in result.columns:
        column.field = resolve(column.field)
    for item in result.filters:
        item.field = resolve(item.field)
    for item in result.sorts:
        item.field = resolve(item.field)
    result.group_by = [resolve(item) for item in result.group_by]
    for item in result.aggregations:
        item.field = resolve(item.field)
    for item in result.calculations:
        item.left_field = resolve(item.left_field)
        if item.right_field:
            item.right_field = resolve(item.right_field)
    return result
