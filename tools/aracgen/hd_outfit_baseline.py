"""HD CharStartOutfit stock data as deduplicated JSON (enhanced client patch baseline)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aracgen.charstartoutfit_export import (
    OUTFIT_SLOT_COUNT,
    OutfitRecord,
    append_outfit_record,
    read_outfit_record,
)
from aracgen.dbc import DbcTable
from aracgen.formats import CHAR_START_OUTFIT

DATA_CLIENT_DIR = Path(__file__).resolve().parents[2] / "data" / "client"
HD_OUTFIT_TEMPLATES_PATH = DATA_CLIENT_DIR / "hd_outfit_templates.json"
HD_OUTFIT_STOCK_INDEX_PATH = DATA_CLIENT_DIR / "hd_outfit_stock_index.json"


@dataclass(frozen=True)
class HdOutfitTemplate:
    outfit_id: int
    item_ids: tuple[int, ...]
    display_item_ids: tuple[int, ...]
    inventory_types: tuple[int, ...]


@dataclass(frozen=True)
class HdStockIndexEntry:
    record_id: int
    race_id: int
    class_id: int
    sex_id: int
    template_id: int


@dataclass(frozen=True)
class HdOutfitCatalog:
    templates: tuple[HdOutfitTemplate, ...]
    stock: tuple[HdStockIndexEntry, ...]

    def stock_record(self, entry: HdStockIndexEntry) -> OutfitRecord:
        template = self.templates[entry.template_id]
        return OutfitRecord(
            record_id=entry.record_id,
            race_id=entry.race_id,
            class_id=entry.class_id,
            sex_id=entry.sex_id,
            outfit_id=template.outfit_id,
            item_ids=template.item_ids,
            display_item_ids=template.display_item_ids,
            inventory_types=template.inventory_types,
        )

    def reference_template(
        self,
        race_id: int,
        class_id: int,
        sex_id: int,
    ) -> HdOutfitTemplate:
        for entry in self.stock:
            if (
                entry.race_id == race_id
                and entry.class_id == class_id
                and entry.sex_id == sex_id
            ):
                return self.templates[entry.template_id]
        msg = f"HD outfit reference not found for ({race_id}, {class_id}, {sex_id})"
        raise ValueError(msg)

    def to_dbc_table(self) -> DbcTable:
        table = DbcTable.create_empty(CHAR_START_OUTFIT)
        for entry in self.stock:
            append_outfit_record(table, self.stock_record(entry))
        return table


def _slot_tuple(raw: list[int], *, name: str) -> tuple[int, ...]:
    if len(raw) != OUTFIT_SLOT_COUNT:
        msg = f"{name} must have {OUTFIT_SLOT_COUNT} entries, got {len(raw)}"
        raise ValueError(msg)
    return tuple(int(value) for value in raw)


def _template_from_dict(payload: dict[str, Any]) -> HdOutfitTemplate:
    return HdOutfitTemplate(
        outfit_id=int(payload["outfit_id"]),
        item_ids=_slot_tuple(payload["item_ids"], name="item_ids"),
        display_item_ids=_slot_tuple(payload["display_item_ids"], name="display_item_ids"),
        inventory_types=_slot_tuple(payload["inventory_types"], name="inventory_types"),
    )


def _entry_from_dict(payload: dict[str, Any]) -> HdStockIndexEntry:
    return HdStockIndexEntry(
        record_id=int(payload["record_id"]),
        race_id=int(payload["race_id"]),
        class_id=int(payload["class_id"]),
        sex_id=int(payload["sex_id"]),
        template_id=int(payload["template_id"]),
    )


def load_hd_outfit_catalog(
    templates_path: Path | None = None,
    stock_index_path: Path | None = None,
) -> HdOutfitCatalog:
    templates_file = templates_path or HD_OUTFIT_TEMPLATES_PATH
    stock_file = stock_index_path or HD_OUTFIT_STOCK_INDEX_PATH
    if not templates_file.is_file():
        msg = f"HD outfit templates not found: {templates_file}"
        raise FileNotFoundError(msg)
    if not stock_file.is_file():
        msg = f"HD outfit stock index not found: {stock_file}"
        raise FileNotFoundError(msg)

    templates_payload = json.loads(templates_file.read_text(encoding="utf-8"))
    stock_payload = json.loads(stock_file.read_text(encoding="utf-8"))
    templates = tuple(_template_from_dict(row) for row in templates_payload["templates"])
    stock = tuple(_entry_from_dict(row) for row in stock_payload["stock"])
    return HdOutfitCatalog(templates=templates, stock=stock)


def load_hd_charstartoutfit_baseline(
    templates_path: Path | None = None,
    stock_index_path: Path | None = None,
) -> DbcTable:
    """Expand checked-in HD JSON into a CharStartOutfit DBC table (126 stock rows)."""
    return load_hd_outfit_catalog(templates_path, stock_index_path).to_dbc_table()


def outfit_template_signature(record: OutfitRecord) -> tuple[Any, ...]:
    return (
        record.outfit_id,
        record.item_ids,
        record.display_item_ids,
        record.inventory_types,
    )


def catalog_from_dbc_table(
    table: DbcTable,
    *,
    source: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build deduplicated JSON payloads from a CharStartOutfit DBC table."""
    signature_to_id: dict[tuple[Any, ...], int] = {}
    templates: list[dict[str, Any]] = []
    stock: list[dict[str, Any]] = []

    for record_index in range(table.record_count):
        record = read_outfit_record(table, record_index)
        signature = outfit_template_signature(record)
        template_id = signature_to_id.get(signature)
        if template_id is None:
            template_id = len(templates)
            signature_to_id[signature] = template_id
            templates.append(
                {
                    "outfit_id": record.outfit_id,
                    "item_ids": list(record.item_ids),
                    "display_item_ids": list(record.display_item_ids),
                    "inventory_types": list(record.inventory_types),
                }
            )
        stock.append(
            {
                "record_id": record.record_id,
                "race_id": record.race_id,
                "class_id": record.class_id,
                "sex_id": record.sex_id,
                "template_id": template_id,
            }
        )

    templates_payload = {
        "source": source,
        "template_count": len(templates),
        "templates": templates,
    }
    stock_payload = {
        "source": source,
        "record_count": len(stock),
        "stock": stock,
    }
    return templates_payload, stock_payload


def write_hd_outfit_catalog(
    table: DbcTable,
    templates_path: Path,
    stock_index_path: Path,
    *,
    source: str,
) -> None:
    templates_payload, stock_payload = catalog_from_dbc_table(table, source=source)
    templates_path.parent.mkdir(parents=True, exist_ok=True)
    templates_path.write_text(
        json.dumps(templates_payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    stock_index_path.write_text(
        json.dumps(stock_payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def apply_hd_preview_displays(
    overlay_records: tuple[OutfitRecord, ...],
    hd_catalog: HdOutfitCatalog,
    *,
    ref_race_for: Callable[[int, int], int],
) -> tuple[OutfitRecord, ...]:
    """Keep server item IDs; swap preview display/inventory from HD catalog ref rows."""
    enhanced: list[OutfitRecord] = []
    for overlay in overlay_records:
        ref_race = ref_race_for(overlay.class_id, overlay.race_id)
        reference = hd_catalog.reference_template(
            ref_race,
            overlay.class_id,
            overlay.sex_id,
        )
        enhanced.append(
            OutfitRecord(
                record_id=overlay.record_id,
                race_id=overlay.race_id,
                class_id=overlay.class_id,
                sex_id=overlay.sex_id,
                outfit_id=overlay.outfit_id,
                item_ids=overlay.item_ids,
                display_item_ids=reference.display_item_ids,
                inventory_types=reference.inventory_types,
            )
        )
    return tuple(enhanced)
