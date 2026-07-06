"""Export charstartoutfit_dbc SQL rows from client CharStartOutfit.dbc overlays."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from aracgen.dbc import DbcTable, FieldKind

REPO_ROOT = Path(__file__).resolve().parents[2]
AC_CHARSTARTOUTFIT_SCHEMA = (
    REPO_ROOT.parent
    / "azerothcore-wotlk"
    / "data"
    / "sql"
    / "base"
    / "db_world"
    / "charstartoutfit_dbc.sql"
)

OUTFIT_SLOT_COUNT = 24
# DBC field indices (CharStartOutfitEntryfmt): ItemId 5-28, Display 29-52, Inventory 53-76.
ITEM_ID_FIELD = 5
DISPLAY_ID_FIELD = 29
INVENTORY_TYPE_FIELD = 53


@dataclass(frozen=True)
class OutfitRecord:
    record_id: int
    race_id: int
    class_id: int
    sex_id: int
    outfit_id: int
    item_ids: tuple[int, ...]
    display_item_ids: tuple[int, ...]
    inventory_types: tuple[int, ...]

    def positive_item_ids(self) -> frozenset[int]:
        return frozenset(
            item_id
            for item_id in self.item_ids
            if item_id > 0 and item_id < 0x80000000
        )


@lru_cache(maxsize=1)
def _load_outfit_schema() -> tuple[tuple[str, bool], ...]:
    text = AC_CHARSTARTOUTFIT_SCHEMA.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"CREATE TABLE.*?\((.*?)\) ENGINE", text, re.S)
    if match is None:
        msg = f"Could not parse charstartoutfit_dbc schema from {AC_CHARSTARTOUTFIT_SCHEMA}"
        raise ValueError(msg)
    cols: list[tuple[str, bool]] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("PRIMARY"):
            continue
        name = stripped.split()[0].strip("`")
        signed = "` int NOT NULL" in stripped and "unsigned" not in stripped
        cols.append((name, signed))
    if len(cols) != 77:
        msg = f"Expected 77 charstartoutfit_dbc columns, got {len(cols)}"
        raise ValueError(msg)
    return tuple(cols)


def _load_outfit_columns() -> list[str]:
    return [name for name, _signed in _load_outfit_schema()]


def _to_signed_int32(value: int) -> int:
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        return value - 0x100000000
    return value


def _read_field(table: DbcTable, record_index: int, field_index: int) -> int:
    spec = table._fields[field_index]  # noqa: SLF001
    if spec.kind == FieldKind.UINT8:
        return table.get_uint8(record_index, field_index)
    if spec.kind == FieldKind.PAD_BYTE:
        return table.records[record_index][spec.offset]
    if spec.kind in {FieldKind.UINT32, FieldKind.PAD_UINT32}:
        return table.get_uint32(record_index, field_index)
    msg = f"Unhandled outfit field kind {spec.kind} at index {field_index}"
    raise TypeError(msg)


def _read_slot_array(table: DbcTable, record_index: int, start_field: int) -> tuple[int, ...]:
    return tuple(
        _read_field(table, record_index, start_field + offset)
        for offset in range(OUTFIT_SLOT_COUNT)
    )


def read_outfit_record(table: DbcTable, record_index: int) -> OutfitRecord:
    return OutfitRecord(
        record_id=_read_field(table, record_index, 0),
        race_id=_read_field(table, record_index, 1),
        class_id=_read_field(table, record_index, 2),
        sex_id=_read_field(table, record_index, 3),
        outfit_id=_read_field(table, record_index, 4),
        item_ids=_read_slot_array(table, record_index, ITEM_ID_FIELD),
        display_item_ids=_read_slot_array(table, record_index, DISPLAY_ID_FIELD),
        inventory_types=_read_slot_array(table, record_index, INVENTORY_TYPE_FIELD),
    )


def find_outfit_record(table: DbcTable, race_id: int, class_id: int, sex_id: int) -> int:
    for record_index in range(table.record_count):
        if (
            table.get_uint8(record_index, 1) == race_id
            and table.get_uint8(record_index, 2) == class_id
            and table.get_uint8(record_index, 3) == sex_id
        ):
            return record_index
    msg = f"CharStartOutfit record not found for ({race_id}, {class_id}, {sex_id})"
    raise ValueError(msg)


def stock_outfit_covers(table: DbcTable, race_id: int, class_id: int) -> bool:
    """True when client CharStartOutfit.dbc already defines this combo."""
    return any(
        table.get_uint8(record_index, 1) == race_id
        and table.get_uint8(record_index, 2) == class_id
        for record_index in range(table.record_count)
    )


def dbc_max_outfit_id(table: DbcTable) -> int:
    if table.record_count == 0:
        return 0
    return max(_read_field(table, record_index, 0) for record_index in range(table.record_count))


def outfit_id_floor(table: DbcTable, db_max_outfit_id: int = 0) -> tuple[int, int, int]:
    """Return (dbc_max, db_max, next_id) for overlay assignment."""
    if db_max_outfit_id < 0:
        msg = f"db_max_outfit_id must be >= 0, got {db_max_outfit_id}"
        raise ValueError(msg)
    dbc_max = dbc_max_outfit_id(table)
    floor = max(dbc_max, db_max_outfit_id)
    return dbc_max, db_max_outfit_id, floor + 1


def clone_outfit_record(
    table: DbcTable,
    record_index: int,
    *,
    record_id: int,
    race_id: int,
    class_id: int,
) -> OutfitRecord:
    source = read_outfit_record(table, record_index)
    return OutfitRecord(
        record_id=record_id,
        race_id=race_id,
        class_id=class_id,
        sex_id=source.sex_id,
        outfit_id=source.outfit_id,
        item_ids=source.item_ids,
        display_item_ids=source.display_item_ids,
        inventory_types=source.inventory_types,
    )


def clone_reference_outfits(
    table: DbcTable,
    *,
    race_id: int,
    class_id: int,
    ref_race: int,
    next_record_id: int,
) -> tuple[tuple[OutfitRecord, ...], int]:
    records: list[OutfitRecord] = []
    record_id = next_record_id
    for sex_id in (0, 1):
        ref_index = find_outfit_record(table, ref_race, class_id, sex_id)
        records.append(
            clone_outfit_record(
                table,
                ref_index,
                record_id=record_id,
                race_id=race_id,
                class_id=class_id,
            )
        )
        record_id += 1
    return tuple(records), record_id


def _record_values(record: OutfitRecord) -> list[int]:
    values: list[int] = [
        record.record_id,
        record.race_id,
        record.class_id,
        record.sex_id,
        record.outfit_id,
        *record.item_ids,
        *record.display_item_ids,
        *record.inventory_types,
    ]
    if len(values) != len(_load_outfit_columns()):
        msg = f"Outfit row width {len(values)} != schema columns {len(_load_outfit_columns())}"
        raise ValueError(msg)
    return values


def _sql_literal(value: int, *, signed: bool) -> str:
    if signed:
        return str(_to_signed_int32(value))
    return str(value)


def render_outfit_row(record: OutfitRecord) -> str:
    schema = _load_outfit_schema()
    values = _record_values(record)
    rendered = ", ".join(
        _sql_literal(value, signed=signed) for (_name, signed), value in zip(schema, values, strict=True)
    )
    columns = ", ".join(f"`{name}`" for name, _signed in schema)
    return f"REPLACE INTO `charstartoutfit_dbc` ({columns}) VALUES ({rendered});"


def render_install_sql(records: tuple[OutfitRecord, ...]) -> str:
    if not records:
        return "-- mod-uac: no charstartoutfit_dbc overlay rows required.\n"
    ids = ", ".join(str(record.record_id) for record in records)
    lines = [
        "-- mod-uac: charstartoutfit_dbc overlays (cloned reference outfits for new combos)",
        "-- Skips combos that already have native CharStartOutfit.dbc rows.",
        f"-- overlay IDs: {ids}",
        "",
    ]
    for record in records:
        lines.append(
            f"-- ({record.race_id}, {record.class_id}, sex={record.sex_id}) from reference clone"
        )
        lines.append(render_outfit_row(record))
    lines.append("")
    return "\n".join(lines)


def render_uninstall_sql(records: tuple[OutfitRecord, ...]) -> str:
    if not records:
        return "-- mod-uac: no charstartoutfit_dbc overlay rows to remove.\n"
    ids = ", ".join(str(record.record_id) for record in records)
    return "\n".join(
        [
            "-- mod-uac: revert charstartoutfit_dbc overlays",
            f"-- removes exactly these IDs: {ids}",
            "",
            f"DELETE FROM `charstartoutfit_dbc` WHERE `ID` IN ({ids});",
            "",
        ]
    )
