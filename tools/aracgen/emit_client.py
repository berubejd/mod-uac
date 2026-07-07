"""Emit the universal client MPQ patch (Phase 1e)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from aracgen.charstartoutfit_export import merge_outfit_overlays
from aracgen.dbc import DbcTable
from aracgen.emit_player import build_resolver, compute_player_create
from aracgen.emit_skill import compute_skill_overlay, merge_skill_overlays
from aracgen.formats import CHAR_BASE_INFO
from aracgen.hd_outfit_baseline import (
    HD_OUTFIT_STOCK_INDEX_PATH,
    HD_OUTFIT_TEMPLATES_PATH,
    apply_hd_preview_displays,
    load_hd_outfit_catalog,
)
from aracgen.matrix import PLAYABLE_CLASSES, PLAYABLE_RACES, ComboMatrix
from aracgen.mpq import MpqFileEntry, build_mpq_v1
from aracgen.sources import DbcSource

# WoW 3.3.5a client lookup paths inside the MPQ.
CHAR_BASE_INFO_MPQ_PATH = "DBFilesClient\\CharBaseInfo.dbc"
CHAR_START_OUTFIT_MPQ_PATH = "DBFilesClient\\CharStartOutfit.dbc"
SKILL_RACE_CLASS_INFO_MPQ_PATH = "DBFilesClient\\SkillRaceClassInfo.dbc"
LISTFILE_MPQ_PATH = "(listfile)"

# Single-letter patch slot; loads late on stock clients. See README for rename guidance.
DEFAULT_CLIENT_PATCH_NAME = "patch-z.mpq"

CLIENT_PATCH_UNLOCK_ONLY_DIR = "unlock-only"
CLIENT_PATCH_STANDARD_DIR = "standard"
CLIENT_PATCH_ENHANCED_DIR = "enhanced"


class ClientPatchVariant(Enum):
    """Checked-in client patch flavors under ``client-patch/<dir>/patch-z.mpq``."""

    UNLOCK_ONLY = CLIENT_PATCH_UNLOCK_ONLY_DIR
    STANDARD = CLIENT_PATCH_STANDARD_DIR
    ENHANCED = CLIENT_PATCH_ENHANCED_DIR


def build_char_base_info_table() -> DbcTable:
    """Full playable race × class matrix (100 records including DK)."""
    table = DbcTable.create_empty(CHAR_BASE_INFO)
    for race_id in sorted(PLAYABLE_RACES):
        for class_id in sorted(PLAYABLE_CLASSES):
            index = table.record_count
            table.append_record()
            table.set_uint8(index, 0, race_id)
            table.set_uint8(index, 1, class_id)
    return table


def build_skill_race_class_info_table(source: DbcSource) -> DbcTable:
    """Stock SkillRaceClassInfo.dbc plus mod-uac overlay rows for client equip tooltips."""
    stock = source.load_skill_race_class_info()
    overlay = compute_skill_overlay(stock, ComboMatrix.stock())
    return merge_skill_overlays(stock, overlay.rows)


def build_client_patch_bytes(
    source: DbcSource,
    *,
    variant: ClientPatchVariant = ClientPatchVariant.UNLOCK_ONLY,
    hd_templates_path: Path | None = None,
    hd_stock_index_path: Path | None = None,
) -> bytes:
    """Build the client MPQ payload for the requested variant."""
    char_base_info = build_char_base_info_table().write()
    skill_race_class_info = build_skill_race_class_info_table(source).write()
    listfile_lines = [CHAR_BASE_INFO_MPQ_PATH, SKILL_RACE_CLASS_INFO_MPQ_PATH]

    entries: list[MpqFileEntry] = [
        MpqFileEntry(path=CHAR_BASE_INFO_MPQ_PATH, data=char_base_info),
        MpqFileEntry(path=SKILL_RACE_CLASS_INFO_MPQ_PATH, data=skill_race_class_info),
    ]

    if variant is not ClientPatchVariant.UNLOCK_ONLY:
        outfit = source.load_char_start_outfit()
        resolver = build_resolver(outfit)
        overlay_records = compute_player_create(resolver).outfit_records
        if overlay_records:
            if variant is ClientPatchVariant.ENHANCED:
                hd_catalog = load_hd_outfit_catalog(
                    hd_templates_path or HD_OUTFIT_TEMPLATES_PATH,
                    hd_stock_index_path or HD_OUTFIT_STOCK_INDEX_PATH,
                )
                overlay_records = apply_hd_preview_displays(
                    overlay_records,
                    hd_catalog,
                    ref_race_for=resolver.reference_race_for_class,
                )
                outfit_base = hd_catalog.to_dbc_table()
            else:
                outfit_base = outfit

            char_start_outfit = merge_outfit_overlays(outfit_base, overlay_records).write()
            entries.append(
                MpqFileEntry(path=CHAR_START_OUTFIT_MPQ_PATH, data=char_start_outfit)
            )
            listfile_lines.append(CHAR_START_OUTFIT_MPQ_PATH)

    listfile = "".join(f"{line}\r\n" for line in listfile_lines).encode("ascii")
    return build_mpq_v1((MpqFileEntry(path=LISTFILE_MPQ_PATH, data=listfile), *entries))


@dataclass(slots=True)
class ClientPatchEmitter:
    source: DbcSource
    variant: ClientPatchVariant = ClientPatchVariant.UNLOCK_ONLY
    hd_templates_path: Path | None = None
    hd_stock_index_path: Path | None = None

    def compute(self) -> bytes:
        return build_client_patch_bytes(
            self.source,
            variant=self.variant,
            hd_templates_path=self.hd_templates_path,
            hd_stock_index_path=self.hd_stock_index_path,
        )

    def write(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.compute())
