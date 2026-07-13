"""Emit capital guard POI + gossip options for mod-uac capital class trainers (Phase 2d)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from aracgen.capital_trainer_catalog import CAPITAL_ZONES, capital_display_name
from aracgen.emit_trainers import (
    DEFAULT_TRAINER_OVERRIDES_PATH,
    TrainerRow,
    compute_capital_trainer_result,
    load_trainer_overrides,
)
from aracgen.guard_directions_catalog import (
    CLASS_OPTION_BROADCAST_TEXT,
    POI_FLAGS,
    POI_ICON,
    confirm_text,
    poi_name,
)
from aracgen.matrix import ComboMatrix
from aracgen.schema_emit import render_insert
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import (
    MOD_UAC_GUARD_MENU_MAX,
    MOD_UAC_GUARD_MENU_MIN,
    MOD_UAC_GUARD_NPC_TEXT_MAX,
    MOD_UAC_GUARD_NPC_TEXT_MIN,
    MOD_UAC_GUARD_POI_MAX,
    MOD_UAC_GUARD_POI_MIN,
    Snapshot,
)
from aracgen.trainer_catalog import CLASS_ORDER, TrainerOverride

POINTS_OF_INTEREST_TABLE = "points_of_interest"
NPC_TEXT_TABLE = "npc_text"
GOSSIP_MENU_TABLE = "gossip_menu"
GOSSIP_MENU_OPTION_TABLE = "gossip_menu_option"


@dataclass(frozen=True, slots=True)
class GuardTrainerArtifacts:
    capital: str
    class_name: str
    entry_name: str
    poi_id: int
    confirm_menu_id: int
    npc_text_id: int
    trainer_x: float
    trainer_y: float


@dataclass(frozen=True, slots=True)
class GuardMenuOptionPatch:
    class_menu_id: int
    option_id: int
    class_name: str
    poi_id: int
    confirm_menu_id: int


@dataclass(frozen=True, slots=True)
class GuardDirectionsResult:
    artifacts: tuple[GuardTrainerArtifacts, ...]
    options: tuple[GuardMenuOptionPatch, ...]
    poi_ids: tuple[int, ...]
    npc_text_ids: tuple[int, ...]
    confirm_menu_ids: tuple[int, ...]


def _capital_menu_index(snapshot: Snapshot) -> dict[str, Mapping[str, object]]:
    menus = snapshot.data.get("trainers", {}).get("capital_class_menus")
    if not menus:
        msg = (
            "Snapshot is missing trainers.capital_class_menus; refresh the world snapshot "
            "(capture_snapshot.py / --refresh-snapshot) so guard menu wiring can be read."
        )
        raise ValueError(msg)
    return {str(entry["capital"]): entry for entry in menus}


def _sort_trainer_rows(rows: Sequence[TrainerRow]) -> tuple[TrainerRow, ...]:
    zone_order = {zone.label: index for index, zone in enumerate(CAPITAL_ZONES)}
    class_order = {name: index for index, name in enumerate(CLASS_ORDER)}

    def sort_key(row: TrainerRow) -> tuple[int, int, str]:
        return (
            zone_order.get(row.zone_label, 999),
            class_order.get(row.class_name, 999),
            row.class_name,
        )

    return tuple(sorted((row for row in rows if row.is_capital), key=sort_key))


def _allocate_ids(count: int) -> tuple[list[int], list[int], list[int]]:
    if count == 0:
        return [], [], []
    poi_ids = list(range(MOD_UAC_GUARD_POI_MIN, MOD_UAC_GUARD_POI_MIN + count))
    npc_text_ids = list(range(MOD_UAC_GUARD_NPC_TEXT_MIN, MOD_UAC_GUARD_NPC_TEXT_MIN + count))
    confirm_menu_ids = list(range(MOD_UAC_GUARD_MENU_MIN, MOD_UAC_GUARD_MENU_MIN + count))
    if poi_ids[-1] > MOD_UAC_GUARD_POI_MAX:
        msg = (
            f"Capital guard emission needs {count} POIs but reserved band "
            f"tops out at {MOD_UAC_GUARD_POI_MAX}"
        )
        raise ValueError(msg)
    if npc_text_ids[-1] > MOD_UAC_GUARD_NPC_TEXT_MAX:
        msg = (
            f"Capital guard emission needs {count} npc_text rows but reserved band "
            f"tops out at {MOD_UAC_GUARD_NPC_TEXT_MAX}"
        )
        raise ValueError(msg)
    if confirm_menu_ids[-1] > MOD_UAC_GUARD_MENU_MAX:
        msg = (
            f"Capital guard emission needs {count} confirm menus but reserved band "
            f"tops out at {MOD_UAC_GUARD_MENU_MAX}"
        )
        raise ValueError(msg)
    return poi_ids, npc_text_ids, confirm_menu_ids


def compute_guard_directions(
    snapshot: Snapshot,
    capital_rows: Sequence[TrainerRow],
) -> GuardDirectionsResult:
    menu_index = _capital_menu_index(snapshot)
    sorted_rows = _sort_trainer_rows(capital_rows)
    if not sorted_rows:
        return GuardDirectionsResult(
            artifacts=(),
            options=(),
            poi_ids=(),
            npc_text_ids=(),
            confirm_menu_ids=(),
        )

    next_option_by_menu: dict[int, int] = {}
    artifacts: list[GuardTrainerArtifacts] = []
    options: list[GuardMenuOptionPatch] = []

    poi_ids, npc_text_ids, confirm_menu_ids = _allocate_ids(len(sorted_rows))
    for index, row in enumerate(sorted_rows):
        capital_entry = menu_index.get(row.zone_label)
        if capital_entry is None:
            msg = (
                f"No captured class-trainer gossip submenu for capital {row.zone_label!r}; "
                "refresh the snapshot against a stock AC world DB."
            )
            raise ValueError(msg)
        artifact = GuardTrainerArtifacts(
            capital=row.zone_label,
            class_name=row.class_name,
            entry_name=row.entry_name,
            poi_id=poi_ids[index],
            confirm_menu_id=confirm_menu_ids[index],
            npc_text_id=npc_text_ids[index],
            trainer_x=row.x,
            trainer_y=row.y,
        )
        artifacts.append(artifact)
        for menu in capital_entry["menus"]:
            menu_id = int(menu["menu_id"])
            present = frozenset(menu["present_classes"])
            if row.class_name in present:
                continue
            option_id = next_option_by_menu.get(menu_id)
            if option_id is None:
                option_id = int(menu["max_option_id"]) + 1
            options.append(
                GuardMenuOptionPatch(
                    class_menu_id=menu_id,
                    option_id=option_id,
                    class_name=row.class_name,
                    poi_id=artifact.poi_id,
                    confirm_menu_id=artifact.confirm_menu_id,
                )
            )
            next_option_by_menu[menu_id] = option_id + 1

    return GuardDirectionsResult(
        artifacts=tuple(artifacts),
        options=tuple(options),
        poi_ids=tuple(poi_ids),
        npc_text_ids=tuple(npc_text_ids),
        confirm_menu_ids=tuple(confirm_menu_ids),
    )


def _band_delete(table: str, column: str, lo: int, hi: int) -> str:
    return f"DELETE FROM `{table}` WHERE `{column}` BETWEEN {lo} AND {hi};"


def _reserved_band_deletes() -> list[str]:
    return [
        _band_delete(POINTS_OF_INTEREST_TABLE, "ID", MOD_UAC_GUARD_POI_MIN, MOD_UAC_GUARD_POI_MAX),
        _band_delete(NPC_TEXT_TABLE, "ID", MOD_UAC_GUARD_NPC_TEXT_MIN, MOD_UAC_GUARD_NPC_TEXT_MAX),
        _band_delete(GOSSIP_MENU_TABLE, "MenuID", MOD_UAC_GUARD_MENU_MIN, MOD_UAC_GUARD_MENU_MAX),
        (
            "DELETE FROM `gossip_menu_option` WHERE `ActionPoiID` BETWEEN "
            f"{MOD_UAC_GUARD_POI_MIN} AND {MOD_UAC_GUARD_POI_MAX};"
        ),
    ]


def _poi_row(artifact: GuardTrainerArtifacts) -> dict[str, object]:
    return {
        "ID": artifact.poi_id,
        "PositionX": artifact.trainer_x,
        "PositionY": artifact.trainer_y,
        "Icon": POI_ICON,
        "Flags": POI_FLAGS,
        "Importance": 0,
        "Name": poi_name(artifact.capital, artifact.class_name),
    }


def _npc_text_row(artifact: GuardTrainerArtifacts) -> dict[str, object]:
    text = confirm_text(
        capital_display_name(artifact.capital),
        artifact.class_name,
        artifact.entry_name,
    )
    return {
        "ID": artifact.npc_text_id,
        "text0_0": text,
        "text0_1": text,
        "Probability0": 1,
    }


def _gossip_menu_row(artifact: GuardTrainerArtifacts) -> dict[str, object]:
    return {"MenuID": artifact.confirm_menu_id, "TextID": artifact.npc_text_id}


def _gossip_option_row(option: GuardMenuOptionPatch) -> dict[str, object]:
    return {
        "MenuID": option.class_menu_id,
        "OptionID": option.option_id,
        "OptionIcon": 0,
        "OptionText": option.class_name,
        "OptionBroadcastTextID": CLASS_OPTION_BROADCAST_TEXT[option.class_name],
        "OptionType": 1,
        "OptionNpcFlag": 1,
        "ActionMenuID": option.confirm_menu_id,
        "ActionPoiID": option.poi_id,
        "BoxCoded": 0,
        "BoxMoney": 0,
        "BoxText": "",
        "BoxBroadcastTextID": 0,
        "VerifiedBuild": 0,
    }


def _resolve(snapshot: Snapshot | None) -> Snapshot:
    return snapshot if snapshot is not None else load_snapshot()


def render_install(
    result: GuardDirectionsResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    snap = _resolve(snapshot)
    poi_schema = snap.schema(POINTS_OF_INTEREST_TABLE)
    npc_schema = snap.schema(NPC_TEXT_TABLE)
    menu_schema = snap.schema(GOSSIP_MENU_TABLE)
    option_schema = snap.schema(GOSSIP_MENU_OPTION_TABLE)

    lines = [
        "-- mod-uac: capital guard map markers + gossip for mod-uac capital class trainers.",
        "-- POI pins use emitted trainer coordinates; confirm text is generated per trainer row.",
        "",
        "-- Idempotent: clear the reserved guard-artifact bands before re-inserting.",
        *_reserved_band_deletes(),
        "",
    ]

    if not result.artifacts:
        lines.append("-- No capital guard patches required.")
        return "\n".join(lines) + "\n"

    lines.append(
        f"-- {len(result.artifacts)} trainer POI(s), {len(result.options)} guard option(s)."
    )
    lines.append("")
    for artifact in result.artifacts:
        lines.append(
            f"-- {artifact.capital} {artifact.class_name}: POI {artifact.poi_id}, "
            f"confirm menu {artifact.confirm_menu_id}"
        )
        lines.append(render_insert(POINTS_OF_INTEREST_TABLE, poi_schema, _poi_row(artifact)))
        lines.append(render_insert(NPC_TEXT_TABLE, npc_schema, _npc_text_row(artifact)))
        lines.append(render_insert(GOSSIP_MENU_TABLE, menu_schema, _gossip_menu_row(artifact)))
        lines.append("")

    for option in result.options:
        lines.append(
            f"-- menu {option.class_menu_id} option {option.option_id}: {option.class_name}"
        )
        lines.append(
            render_insert(GOSSIP_MENU_OPTION_TABLE, option_schema, _gossip_option_row(option))
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_uninstall(result: GuardDirectionsResult) -> str:
    lines = [
        "-- mod-uac: revert capital guard POI / gossip patches.",
        "",
    ]
    if result.artifacts:
        lines.extend(_reserved_band_deletes())
    else:
        lines.append("-- No capital guard patches were emitted.")
    return "\n".join(lines) + "\n"


@dataclass
class GuardDirectionsEmitter:
    snapshot: Snapshot | None = None
    matrix: ComboMatrix | None = None
    overrides: Sequence[TrainerOverride] = ()
    overrides_path: Path | None = DEFAULT_TRAINER_OVERRIDES_PATH

    def compute(self) -> GuardDirectionsResult:
        snapshot = _resolve(self.snapshot)
        overrides = self.overrides
        if not overrides and self.overrides_path is not None:
            overrides = load_trainer_overrides(self.overrides_path)
        capital = compute_capital_trainer_result(
            snapshot,
            self.matrix,
            overrides=overrides,
        )
        return compute_guard_directions(snapshot, capital.rows)

    def render_install(self, result: GuardDirectionsResult) -> str:
        return render_install(result, snapshot=self.snapshot)

    def render_uninstall(self, result: GuardDirectionsResult) -> str:
        return render_uninstall(result)


def main() -> None:
    emitter = GuardDirectionsEmitter()
    result = emitter.compute()
    print(emitter.render_install(result))


if __name__ == "__main__":
    main()
