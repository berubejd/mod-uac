"""Emit class-wide hunter pet spell grants at level 1 (Phase 1g, optional slice)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aracgen.class_quest_catalog import HUNTER_CLASS_ID, HUNTER_PET_SPELL_IDS
from aracgen.matrix import class_bit
from aracgen.schema_emit import render_insert
from aracgen.snapshot_model import Snapshot
from aracgen.sources import DEFAULT_CANONICAL_PIN, cached_client_data_zip
from aracgen.spell_dbc_export import render_spell_dbc_install, render_spell_dbc_uninstall

SPELL_CUSTOM_TABLE = "playercreateinfo_spell_custom"

HUNTER_CLASS_MASK = class_bit(HUNTER_CLASS_ID)
ALL_RACES_MASK = 0
HUNTER_PET_NOTE = "mod-uac: level-1 hunter pet kit (all hunters)"


@dataclass(frozen=True, slots=True)
class HunterPetSpellRow:
    spell_id: int


@dataclass(frozen=True, slots=True)
class HunterPetResult:
    spell_rows: tuple[HunterPetSpellRow, ...]


def compute_hunter_pet_spells() -> HunterPetResult:
    return HunterPetResult(
        spell_rows=tuple(HunterPetSpellRow(spell_id=spell_id) for spell_id in HUNTER_PET_SPELL_IDS)
    )


def _resolve_snapshot(snapshot: Snapshot | None) -> Snapshot:
    if snapshot is not None:
        return snapshot
    from aracgen.snapshot import load_snapshot

    return load_snapshot()


def render_spell_custom_install(
    result: HunterPetResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    schema = _resolve_snapshot(snapshot).schema(SPELL_CUSTOM_TABLE)
    lines = [
        "-- mod-uac: level-1 hunter pet spells for ALL hunters (optional — revert separately)",
        "-- Requires worldserver.conf: PlayerStart.CustomSpells = 1",
        "-- Pair with mod_uac_hunter_pet_spell_dbc.sql so Tame Beast is castable at level 1.",
        "",
    ]
    for row in result.spell_rows:
        lines.append(
            render_insert(
                SPELL_CUSTOM_TABLE,
                schema,
                {
                    "racemask": ALL_RACES_MASK,
                    "classmask": HUNTER_CLASS_MASK,
                    "Spell": row.spell_id,
                    "Note": HUNTER_PET_NOTE,
                },
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_spell_custom_uninstall(result: HunterPetResult) -> str:
    lines = [
        "-- mod-uac: revert level-1 hunter pet spell grants",
        "-- (stock hunters return to level-10 quest gate)",
        "",
    ]
    for row in result.spell_rows:
        lines.append(
            "DELETE FROM `playercreateinfo_spell_custom` "
            f"WHERE `racemask` = {ALL_RACES_MASK} "
            f"AND `classmask` = {HUNTER_CLASS_MASK} "
            f"AND `Spell` = {row.spell_id};"
        )
    lines.append("")
    return "\n".join(lines)


@dataclass(slots=True)
class HunterPetEmitter:
    dbc_source: Path | None = None
    canonical_pin: str = DEFAULT_CANONICAL_PIN
    snapshot: Snapshot | None = None

    def compute(self) -> HunterPetResult:
        return compute_hunter_pet_spells()

    def _dbc_source(self) -> Path:
        if self.dbc_source is not None:
            return self.dbc_source
        return cached_client_data_zip(
            Path(__file__).resolve().parents[2] / "data" / "cache",
            self.canonical_pin,
        )

    def render_install_files(self, result: HunterPetResult | None = None) -> dict[str, str]:
        data = result or self.compute()
        return {
            "hunter_pet_spell_custom": render_spell_custom_install(
                data,
                snapshot=self.snapshot,
            ),
            "hunter_pet_spell_dbc": render_spell_dbc_install(
                HUNTER_PET_SPELL_IDS,
                self._dbc_source(),
                snapshot=self.snapshot,
            ),
        }

    def render_uninstall_files(self, result: HunterPetResult | None = None) -> dict[str, str]:
        data = result or self.compute()
        return {
            "hunter_pet_spell_custom": render_spell_custom_uninstall(data),
            "hunter_pet_spell_dbc": render_spell_dbc_uninstall(HUNTER_PET_SPELL_IDS),
        }
