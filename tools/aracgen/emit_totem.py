"""Emit player_totem_model SQL for off-race shamans."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.kits import ALLIANCE_RACES, HORDE_RACES
from aracgen.matrix import ComboMatrix
from aracgen.schema_emit import render_insert_bulk
from aracgen.snapshot_model import Snapshot

TOTEM_TABLE = "player_totem_model"

SHAMAN_CLASS_ID = 7

# Races with stock player_totem_model rows (native shaman races in AC base db_world).
STOCK_TOTEM_RACES: frozenset[int] = frozenset({2, 3, 6, 8, 11})

# Reference totem display IDs from AzerothCore base player_totem_model.sql.
ALLIANCE_TOTEM_REFERENCE_RACE = 3  # Dwarf
HORDE_TOTEM_REFERENCE_RACE = 2  # Orc

REFERENCE_TOTEM_MODELS: dict[int, dict[int, int]] = {
    ALLIANCE_TOTEM_REFERENCE_RACE: {1: 30754, 2: 30753, 3: 30755, 4: 30736},
    HORDE_TOTEM_REFERENCE_RACE: {1: 30758, 2: 30757, 3: 30759, 4: 30756},
}

TOTEM_IDS: tuple[int, ...] = (1, 2, 3, 4)


@dataclass(frozen=True, slots=True)
class TotemModelRow:
    totem_id: int
    race_id: int
    model_id: int


@dataclass(frozen=True, slots=True)
class TotemModelResult:
    rows: tuple[TotemModelRow, ...]


def _resolve_snapshot(snapshot: Snapshot | None) -> Snapshot:
    if snapshot is not None:
        return snapshot
    from aracgen.snapshot import load_snapshot

    return load_snapshot()


def off_race_shaman_races(matrix: ComboMatrix) -> tuple[int, ...]:
    """Races gaining shaman via mod-uac that lack stock player_totem_model rows."""
    new_shaman = {race for race, class_id in matrix.new_combos if class_id == SHAMAN_CLASS_ID}
    return tuple(sorted(new_shaman - STOCK_TOTEM_RACES))


def _reference_race_for(race_id: int) -> int:
    if race_id in ALLIANCE_RACES:
        return ALLIANCE_TOTEM_REFERENCE_RACE
    if race_id in HORDE_RACES:
        return HORDE_TOTEM_REFERENCE_RACE
    msg = f"Race {race_id} is not in a known faction"
    raise ValueError(msg)


def compute_totem_models(matrix: ComboMatrix) -> TotemModelResult:
    rows: list[TotemModelRow] = []
    for race_id in off_race_shaman_races(matrix):
        ref_race = _reference_race_for(race_id)
        models = REFERENCE_TOTEM_MODELS[ref_race]
        for totem_id in TOTEM_IDS:
            rows.append(
                TotemModelRow(
                    totem_id=totem_id,
                    race_id=race_id,
                    model_id=models[totem_id],
                )
            )
    return TotemModelResult(rows=tuple(rows))


def render_totem_install(
    result: TotemModelResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    if not result.rows:
        return "-- mod-uac: no player_totem_model rows required.\n"

    schema = _resolve_snapshot(snapshot).schema(TOTEM_TABLE)
    race_ids = sorted({row.race_id for row in result.rows})
    race_list = ", ".join(str(race_id) for race_id in race_ids)
    logical_rows = [
        {
            "TotemID": row.totem_id,
            "RaceID": row.race_id,
            "ModelID": row.model_id,
        }
        for row in result.rows
    ]
    lines = [
        "-- mod-uac: totem display models for off-race shamans",
        f"-- races: {race_list} (Alliance -> Dwarf models, Horde -> Orc models)",
        "",
        f"DELETE FROM `{TOTEM_TABLE}` WHERE `RaceID` IN ({race_list});",
        render_insert_bulk(TOTEM_TABLE, schema, logical_rows),
        "",
    ]
    return "\n".join(lines)


def render_totem_uninstall(result: TotemModelResult) -> str:
    if not result.rows:
        return "-- mod-uac: no player_totem_model rows to remove.\n"

    race_ids = sorted({row.race_id for row in result.rows})
    race_list = ", ".join(str(race_id) for race_id in race_ids)
    return "\n".join(
        [
            "-- mod-uac: revert player_totem_model rows for off-race shamans",
            "",
            f"DELETE FROM `{TOTEM_TABLE}` WHERE `RaceID` IN ({race_list});",
            "",
        ]
    )


@dataclass(slots=True)
class TotemEmitter:
    matrix: ComboMatrix
    snapshot: Snapshot | None = None

    def compute(self) -> TotemModelResult:
        return compute_totem_models(self.matrix)

    def render_install(self, result: TotemModelResult | None = None) -> str:
        return render_totem_install(result or self.compute(), snapshot=self.snapshot)

    def render_uninstall(self, result: TotemModelResult | None = None) -> str:
        return render_totem_uninstall(result or self.compute())
