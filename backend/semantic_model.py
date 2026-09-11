"""Datasource-neutral semantic model metadata.

The semantic model describes business meaning without materializing data. It is
intentionally separate from QueryDefinition so the existing execution contract
remains backward compatible while semantic metadata can be introduced safely.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

SemanticRole = Literal["dimension", "measure", "attribute"]
SemanticDataType = Literal[
    "string", "integer", "decimal", "boolean", "date", "datetime", "time", "unknown"
]
AggregationFunction = Literal["SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"]


class SemanticField(BaseModel):
    """Reusable semantic description of one physical dataset field."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    physical_field: str = Field(min_length=1, max_length=200)
    role: SemanticRole = "attribute"
    data_type: SemanticDataType = "unknown"
    display_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    nullable: bool | None = None

    @field_validator("name", "physical_field", "display_name")
    @classmethod
    def normalize_text(cls, value):
        if value is None:
            return value
        value = str(value).strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value


class SemanticDimension(SemanticField):
    role: Literal["dimension"] = "dimension"
    hierarchy: list[str] = Field(default_factory=list)


class SemanticMeasure(SemanticField):
    role: Literal["measure"] = "measure"
    default_aggregation: AggregationFunction = "SUM"
    format: str | None = Field(default=None, max_length=100)


class SemanticCalculatedMeasure(BaseModel):
    """Reusable measure expression evaluated by the query planner."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    expression: str = Field(min_length=1, max_length=4000)
    display_name: str | None = Field(default=None, max_length=200)
    data_type: SemanticDataType = "decimal"
    default_aggregation: AggregationFunction | None = None
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "expression", "display_name")
    @classmethod
    def normalize_text(cls, value):
        if value is None:
            return value
        value = str(value).strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value


class SemanticRelationship(BaseModel):
    """Reusable logical relationship between two semantic datasets."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    left_dataset: str = Field(min_length=1, max_length=200)
    right_dataset: str = Field(min_length=1, max_length=200)
    left_field: str = Field(min_length=1, max_length=200)
    right_field: str = Field(min_length=1, max_length=200)
    relationship: Literal["many_to_one", "one_to_many", "one_to_one", "many_to_many"] = "many_to_one"
    join_type: Literal["INNER", "LEFT", "RIGHT", "FULL"] = "LEFT"


class SemanticDataset(BaseModel):
    """Semantic metadata bound to a registered physical dataset."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    physical_dataset_id: str = Field(min_length=1, max_length=200)
    dimensions: list[SemanticDimension] = Field(default_factory=list)
    measures: list[SemanticMeasure] = Field(default_factory=list)
    calculated_measures: list[SemanticCalculatedMeasure] = Field(default_factory=list)

    @field_validator("id", "name", "physical_dataset_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value

    def field_names(self) -> set[str]:
        return {field.name for field in [*self.dimensions, *self.measures]}


class SemanticModel(BaseModel):
    """Collection-level semantic model containing reusable datasets and relationships."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    datasets: list[SemanticDataset] = Field(default_factory=list)
    relationships: list[SemanticRelationship] = Field(default_factory=list)
