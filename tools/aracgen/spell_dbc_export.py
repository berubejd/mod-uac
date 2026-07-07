"""Export spell_dbc SQL rows from client Spell.dbc (full-row overlay for AC)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from aracgen.dbc import DbcTable, FieldKind
from aracgen.formats import SPELL, SPELL_BASE_LEVEL_FIELD, SPELL_SPELL_LEVEL_FIELD
from aracgen.schema_emit import compact_float_format, render_replace
from aracgen.snapshot_model import Snapshot, TableSchema

SPELL_DBC_TABLE = "spell_dbc"


def _resolve_snapshot(snapshot: Snapshot | None) -> Snapshot:
    if snapshot is not None:
        return snapshot
    from aracgen.snapshot import load_snapshot

    return load_snapshot()


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


# Spell.dbc padding slots that map to real spell_dbc SQL integer columns.
_SPELL_SQL_PAD_FIELDS = frozenset(
    {
        13,
        15,  # unk_320_2, unk_320_3
        48,  # ModalNextSpell
        215,  # StanceBarOrder
        219,
        220,
        221,  # MinFactionID, MinReputation, RequiredAuraVision
        227,
        228,  # SpellMissileID, PowerDisplayID
        232,
        233,  # SpellDescriptionVariableID, SpellDifficultyID
    }
)

_NAME_STRING_FIELD = 136
_SUBTEXT_STRING_FIELD = 153
_TAIL_NUMERIC_FIELD = 204


def _append_dbc_field(
    table: DbcTable,
    record_index: int,
    field_idx: int,
    values: list[int | float | str | None],
) -> None:
    spec = table._fields[field_idx]  # noqa: SLF001
    if spec.kind == FieldKind.PAD_BYTE:
        return
    if spec.kind == FieldKind.PAD_UINT32:
        if field_idx in _SPELL_SQL_PAD_FIELDS:
            values.append(0)
        return
    if spec.kind == FieldKind.UINT8:
        values.append(table.get_uint8(record_index, field_idx))
        return
    if spec.kind == FieldKind.UINT32:
        values.append(table.get_uint32(record_index, field_idx))
        return
    if spec.kind == FieldKind.FLOAT:
        values.append(table.get_float(record_index, field_idx))
        return
    msg = f"Unhandled field kind {spec.kind} at index {field_idx}"
    raise ValueError(msg)


def _record_values(
    table: DbcTable,
    record_index: int,
    schema: TableSchema,
) -> list[int | float | str | None]:
    """Build the spell_dbc row AC expects (client DBC + locale expansion)."""
    values: list[int | float | str | None] = []

    for field_idx in range(_NAME_STRING_FIELD):
        _append_dbc_field(table, record_index, field_idx, values)

    values.extend(_string_group_values(table, record_index, _NAME_STRING_FIELD))
    values.extend(_string_group_values(table, record_index, _SUBTEXT_STRING_FIELD))
    values.extend(_empty_string_group())  # Description (client Spell.dbc has no text)
    values.extend(_empty_string_group())  # AuraDescription

    for field_idx in range(_TAIL_NUMERIC_FIELD, len(table._fields)):  # noqa: SLF001
        _append_dbc_field(table, record_index, field_idx, values)

    columns = schema.column_names()
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


def export_spell_row(
    table: DbcTable,
    spell_id: int,
    *,
    snapshot: Snapshot | None = None,
    base_level: int = 1,
) -> str:
    schema = _resolve_snapshot(snapshot).schema(SPELL_DBC_TABLE)
    record_index = find_spell_record(table, spell_id)
    table.set_uint32(record_index, SPELL_BASE_LEVEL_FIELD, base_level)
    table.set_uint32(record_index, SPELL_SPELL_LEVEL_FIELD, base_level)
    values = _record_values(table, record_index, schema)
    logical = dict(zip(schema.column_names(), values, strict=True))
    return render_replace(
        SPELL_DBC_TABLE,
        schema,
        logical,
        float_format=compact_float_format,
    )


def render_spell_dbc_install(
    spell_ids: tuple[int, ...],
    dbc_source: Path,
    *,
    snapshot: Snapshot | None = None,
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
        lines.append(
            export_spell_row(
                table,
                spell_id,
                snapshot=snapshot,
                base_level=base_level,
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_spell_dbc_uninstall(spell_ids: tuple[int, ...]) -> str:
    ids = ", ".join(str(spell_id) for spell_id in spell_ids)
    return "\n".join(
        [
            "-- mod-uac: remove hunter pet spell_dbc overlays (revert to client Spell.dbc)",
            "",
            f"DELETE FROM `{SPELL_DBC_TABLE}` WHERE `ID` IN ({ids});",
            "",
        ]
    )
