"""Export spell_dbc SQL rows from client Spell.dbc (full-row overlay for AC)."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from aracgen.dbc import DbcTable, FieldKind
from aracgen.formats import SPELL

REPO_ROOT = Path(__file__).resolve().parents[2]
AC_SPELL_DBC_SCHEMA = (
    REPO_ROOT.parent
    / "azerothcore-wotlk"
    / "data"
    / "sql"
    / "base"
    / "db_world"
    / "spell_dbc.sql"
)


def _load_spell_columns() -> list[str]:
    text = AC_SPELL_DBC_SCHEMA.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"CREATE TABLE.*?\((.*?)\) ENGINE", text, re.S)
    if match is None:
        msg = f"Could not parse spell_dbc schema from {AC_SPELL_DBC_SCHEMA}"
        raise ValueError(msg)
    cols: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("PRIMARY"):
            continue
        cols.append(stripped.split()[0].strip("`"))
    return cols


def _sql_literal(value: int | float | str | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, float):
        text = f"{value:g}"
        return text if text != "-0" else "0"
    if isinstance(value, int):
        return str(value)
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def _string_group_values(table: DbcTable, record_index: int, start_field: int) -> list[str | None]:
    """Map 16 client locale string fields + mask column for one SQL string group."""
    values: list[str | None] = []
    primary: str | None = None
    for offset in range(16):
        spec = table._fields[start_field + offset]  # noqa: SLF001
        if spec.kind != FieldKind.STRING:
            msg = f"Expected string field at {start_field + offset}"
            raise TypeError(msg)
        try:
            text = table.get_string(record_index, start_field + offset)
        except ValueError:
            text = ""
        if offset == 0 and text:
            primary = text
        values.append(primary if offset == 0 and primary else None)
    values.append(0)  # Lang_Mask
    return values


def _empty_string_group() -> list[str | None | int]:
    return [None] * 16 + [0]


def _record_values(table: DbcTable, record_index: int) -> list[int | float | str | None]:
    """Build the 234-column spell_dbc row AC expects (client DBC + locale expansion)."""
    values: list[int | float | str | None] = []
    specs = table._fields  # noqa: SLF001
    field_idx = 0
    string_groups = 0
    while field_idx < len(specs):
        spec = specs[field_idx]
        if spec.kind == FieldKind.PAD_BYTE:
            field_idx += 1
            continue
        if spec.kind == FieldKind.PAD_UINT32:
            field_idx += 1
            continue
        if spec.kind == FieldKind.UINT8:
            values.append(table.get_uint8(record_index, field_idx))
            field_idx += 1
            continue
        if spec.kind == FieldKind.UINT32:
            values.append(table.get_uint32(record_index, field_idx))
            field_idx += 1
            continue
        if spec.kind == FieldKind.FLOAT:
            values.append(table.get_float(record_index, field_idx))
            field_idx += 1
            continue
        if spec.kind == FieldKind.STRING:
            values.extend(_string_group_values(table, record_index, field_idx))
            field_idx += 16
            string_groups += 1
            continue
        msg = f"Unhandled field kind {spec.kind}"
        raise ValueError(msg)

    # Client Spell.dbc carries Name + NameSubtext strings; SQL also has Description/AuraDescription.
    while string_groups < 4:
        values.extend(_empty_string_group())
        string_groups += 1

    columns = _load_spell_columns()
    while len(values) < len(columns):
        values.append(0)

    if len(values) != len(columns):
        msg = f"spell_dbc row width {len(values)} != schema columns {len(columns)}"
        raise ValueError(msg)
    return values


def load_spell_table(dbc_zip: Path) -> DbcTable:
    with zipfile.ZipFile(dbc_zip) as archive:
        data = archive.read("dbc/Spell.dbc")
    return DbcTable.read(data, SPELL)


def load_spell_table_file(spell_dbc_path: Path) -> DbcTable:
    return DbcTable.read_file(spell_dbc_path, SPELL)


def find_spell_record(table: DbcTable, spell_id: int) -> int:
    for index in range(table.record_count):
        if table.get_uint32(index, 0) == spell_id:
            return index
    msg = f"Spell {spell_id} not found in Spell.dbc"
    raise ValueError(msg)


def export_spell_row(table: DbcTable, spell_id: int, *, base_level: int = 1) -> str:
    record_index = find_spell_record(table, spell_id)
    table.set_uint32(record_index, 38, base_level)
    table.set_uint32(record_index, 39, base_level)
    values = _record_values(table, record_index)
    columns = _load_spell_columns()
    rendered = ", ".join(_sql_literal(value) for value in values)
    col_list = ", ".join(f"`{name}`" for name in columns)
    return f"REPLACE INTO `spell_dbc` ({col_list}) VALUES ({rendered});"


def render_spell_dbc_install(
    spell_ids: tuple[int, ...],
    dbc_source: Path,
    *,
    base_level: int = 1,
) -> str:
    if dbc_source.suffix.lower() == ".dbc":
        table = load_spell_table_file(dbc_source)
    else:
        table = load_spell_table(dbc_source)
    lines = [
        "-- mod-uac: hunter pet spell level patch (BaseLevel/SpellLevel -> 1)",
        "-- Optional companion to mod_uac_hunter_pet_spell_custom.sql; revert via uninstall file.",
        "",
    ]
    for spell_id in spell_ids:
        lines.append(f"-- spell {spell_id}")
        lines.append(export_spell_row(table, spell_id, base_level=base_level))
    lines.append("")
    return "\n".join(lines)


def render_spell_dbc_uninstall(spell_ids: tuple[int, ...]) -> str:
    ids = ", ".join(str(spell_id) for spell_id in spell_ids)
    return "\n".join(
        [
            "-- mod-uac: remove hunter pet spell_dbc overlays (revert to client Spell.dbc)",
            "",
            f"DELETE FROM `spell_dbc` WHERE `ID` IN ({ids});",
            "",
        ]
    )
