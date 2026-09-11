"""Canonical, connector-neutral report query model.

Change #9 introduces a stable query contract without changing the existing
report execution engine. The model mirrors the current /report/query payload
so existing clients can continue sending the same JSON shape.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class QueryDataset(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    connection_id: str | None = None
    source_type: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    database: str
    table: str | None = None
    object_name: str | None = None
    semantic_dataset_id: str | None = None

    @field_validator("id", "database")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value


class QueryJoin(BaseModel):
    left_dataset: str
    right_dataset: str
    left_column: str
    right_column: str
    join_type: str = "INNER"

    @field_validator("join_type")
    @classmethod
    def normalize_join_type(cls, value: str) -> str:
        value = str(value).strip().upper()
        allowed = {"INNER", "LEFT", "RIGHT", "FULL"}
        if value not in allowed:
            raise ValueError(f"Unsupported join type: {value}")
        return value


class QueryColumn(BaseModel):
    field: str
    alias: str | None = None


class QueryFilter(BaseModel):
    field: str
    operator: str
    value: Any = None
    logic: Literal["AND", "OR"] = "AND"

    @field_validator("operator")
    @classmethod
    def normalize_operator(cls, value: str) -> str:
        return str(value).strip().upper()


class QuerySort(BaseModel):
    field: str
    direction: Literal["ASC", "DESC"] = "ASC"


class QueryAggregation(BaseModel):
    function: str
    field: str
    alias: str | None = None

    @field_validator("function")
    @classmethod
    def normalize_function(cls, value: str) -> str:
        return str(value).strip().upper()


class QueryCalculation(BaseModel):
    alias: str
    left_field: str
    operation: str
    right_field: str | None = None
    right_value: Any = None


class QueryDefinition(BaseModel):
    """Canonical report query shared by API, planner and future UI."""
    datasets: list[QueryDataset] = Field(default_factory=list)
    joins: list[QueryJoin] = Field(default_factory=list)
    columns: list[QueryColumn] = Field(default_factory=list)
    filters: list[QueryFilter] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[QueryAggregation] = Field(default_factory=list)
    calculations: list[QueryCalculation] = Field(default_factory=list)
    sorts: list[QuerySort] = Field(default_factory=list)
    limit: int = 0  # 0 = no application row ceiling

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        value = int(value)
        if value < 0:
            raise ValueError("Limit cannot be negative. Use 0 for no application ceiling.")
        return value

    def normalized(self) -> dict[str, Any]:
        """Return the stable wire representation used by the planner."""
        data = self.model_dump(exclude_none=True)
        # The existing execution layer calls this property calculated_columns.
        data["calculated_columns"] = data.pop("calculations", [])
        return data
