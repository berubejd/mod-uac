"""Export charstartoutfit_dbc SQL rows from client CharStartOutfit.dbc overlays."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.dbc import DbcTable, FieldKind
from aracgen.schema_emit import render_replace
from aracgen.snapshot_model import Snapshot

CHARSTARTOUTFIT_TABLE = "charstartoutfit_dbc"
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


def _resolve_snapshot(snapshot: Snapshot | None) -> Snapshot:
    if snapshot is not None:
        return snapshot
    from aracgen.snapshot import load_snapshot

    return load_snapshot()


def outfit_logical_values(record: OutfitRecord) -> dict[str, int]:
    values: dict[str, int] = {
        "ID": record.record_id,
        "RaceID": record.race_id,
        "ClassID": record.class_id,
        "SexID": record.sex_id,
        "OutfitID": record.outfit_id,
    }
    for index, item_id in enumerate(record.item_ids, start=1):
        values[f"ItemID_{index}"] = item_id
    for index, display_id in enumerate(record.display_item_ids, start=1):
        values[f"DisplayItemID_{index}"] = display_id
    for index, inventory_type in enumerate(record.inventory_types, start=1):
        values[f"InventoryType_{index}"] = inventory_type
    return values


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


def render_outfit_row(record: OutfitRecord, *, snapshot: Snapshot | None = None) -> str:
    schema = _resolve_snapshot(snapshot).schema(CHARSTARTOUTFIT_TABLE)
    logical = outfit_logical_values(record)
    if len(logical) != len(schema.column_names()):
        msg = (
            f"Outfit logical field count {len(logical)} != schema columns "
            f"{len(schema.column_names())}"
        )
        raise ValueError(msg)
    return render_replace(CHARSTARTOUTFIT_TABLE, schema, logical)


def render_install_sql(
    records: tuple[OutfitRecord, ...],
    *,
    snapshot: Snapshot | None = None,
) -> str:
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
        lines.append(render_outfit_row(record, snapshot=snapshot))
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
            f"DELETE FROM `{CHARSTARTOUTFIT_TABLE}` WHERE `ID` IN ({ids});",
            "",
        ]
    )
