"""Schema-driven SQL emission from snapshot TableSchema definitions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aracgen.snapshot_model import COLUMN_ALIASES, ColumnDef, TableSchema


def typed_default(column: ColumnDef) -> Any:
    default = column.default
    if default is None:
        return None
    column_type = column.type.lower()
    if "int" in column_type:
        return int(default)
    if any(token in column_type for token in ("float", "double", "decimal")):
        return float(default)
    return default


def resolve_logical_column(schema: TableSchema, logical: str) -> str:
    if schema.has_column(logical):
        return logical
    if logical in COLUMN_ALIASES.get(schema.table, {}):
        return schema.resolve_logical(logical)
    msg = f"Unknown logical field {logical!r} for table {schema.table!r}"
    raise ValueError(msg)


def prepare_row(schema: TableSchema, logical_values: Mapping[str, Any]) -> dict[str, Any]:
    row = {column.name: typed_default(column) for column in schema.columns}
    for logical, value in logical_values.items():
        physical = resolve_logical_column(schema, logical)
        row[physical] = value
    return row


def format_sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "''")
        return f"'{escaped}'"
    return str(value)


def row_values(schema: TableSchema, row: Mapping[str, Any]) -> list[Any]:
    columns = schema.column_names()
    return [row[column] for column in columns]


def render_insert(
    table: str,
    schema: TableSchema,
    logical_values: Mapping[str, Any],
) -> str:
    row = prepare_row(schema, logical_values)
    columns = schema.column_names()
    column_sql = ", ".join(f"`{name}`" for name in columns)
    values_sql = ", ".join(format_sql_literal(row[name]) for name in columns)
    return f"INSERT INTO `{table}` ({column_sql}) VALUES ({values_sql});"


def render_insert_lines(
    table: str,
    schema: TableSchema,
    rows: list[Mapping[str, Any]],
) -> list[str]:
    return [render_insert(table, schema, row) for row in rows]
