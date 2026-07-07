"""Emit curated starter-zone class trainers for mod-uac new combos."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aracgen.matrix import ComboMatrix
from aracgen.schema_emit import format_sql_literal, prepare_row
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import MOD_UAC_CREATURE_GUID_MAX, Snapshot
from aracgen.snapshot_zones import (
    STARTER_SPAWN_BOX_RADIUS,
    StarterZoneBox,
    build_starter_zone_boxes,
)
from aracgen.trainer_catalog import (
    CLASS_KINSHIP,
    CLASS_ORDER,
    CURATED_SPELL_THRESHOLD,
    ID_TO_CLASS_NAME,
    PLACEMENT_GAP,
    PLACEMENT_STEP,
    TRAINER_GUID_BASE,
    TRAINER_SPAWN_TIME_SECS,
    ZONE_PROCESS_ORDER,
    TrainerOverride,
    trainer_class_name,
    zone_label,
)

CREATURE_TABLE = "creature"
DEFAULT_TRAINER_OVERRIDES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "trainer_overrides.yaml"
)


@dataclass(frozen=True, slots=True)
class NativeTrainer:
    class_name: str
    entry: int
    name: str
    x: float
    y: float
    z: float
    o: float


@dataclass(frozen=True, slots=True)
class TrainerPlacement:
    x: float
    y: float
    z: float
    o: float


@dataclass(frozen=True, slots=True)
class TrainerRow:
    guid: int
    zone_label: str
    map_id: int
    zone_id: int
    class_name: str
    entry: int
    entry_name: str
    anchor_class: str
    anchor_name: str
    x: float
    y: float
    z: float
    o: float
    equipment_id: int
    curhealth: int
    curmana: int
    npcflag: int
    computed: TrainerPlacement | None = None

    @property
    def comment(self) -> str:
        return f"mod-uac {self.zone_label} {self.class_name} trainer"

    @property
    def has_position_override(self) -> bool:
        return self.computed is not None


@dataclass(frozen=True, slots=True)
class TrainerEmitResult:
    rows: tuple[TrainerRow, ...]
    guid_base: int
    guid_max: int


def _trainer_data(snapshot: Snapshot) -> dict[str, Any]:
    return snapshot.data["trainers"]


def _parse_int_map(raw: Mapping[str, Any]) -> dict[int, int]:
    return {int(key): int(value) for key, value in raw.items()}


def _spawn_in_box(spawn: Mapping[str, Any], box: StarterZoneBox) -> bool:
    return (
        int(spawn["map"]) == box.map_id
        and abs(float(spawn["x"]) - box.cx) <= STARTER_SPAWN_BOX_RADIUS
        and abs(float(spawn["y"]) - box.cy) <= STARTER_SPAWN_BOX_RADIUS
    )


def _spawn_in_faction_boxes(
    spawn: Mapping[str, Any],
    boxes: Sequence[StarterZoneBox],
) -> bool:
    return any(_spawn_in_box(spawn, box) for box in boxes)


def _races_in_box(
    playercreateinfo: Sequence[Mapping[str, Any]],
    box: StarterZoneBox,
) -> frozenset[int]:
    races: set[int] = set()
    for row in playercreateinfo:
        if int(row["map"]) != box.map_id:
            continue
        if abs(float(row["x"]) - box.cx) > STARTER_SPAWN_BOX_RADIUS:
            continue
        if abs(float(row["y"]) - box.cy) > STARTER_SPAWN_BOX_RADIUS:
            continue
        races.add(int(row["race"]))
    return frozenset(races)


def _trainer_class_for_entry(
    entry: int,
    creature_default_trainer: Mapping[int, int],
    trainer_spell_counts: Mapping[int, int],
    creature_template: Mapping[int, Mapping[str, Any]],
) -> str | None:
    trainer_id = creature_default_trainer.get(entry)
    if trainer_id is None:
        return None
    if trainer_spell_counts.get(trainer_id, 999) > CURATED_SPELL_THRESHOLD:
        return None
    template = creature_template.get(entry, {})
    return trainer_class_name(str(template.get("name", "")), str(template.get("subname", "")))


def native_trainers_in_box(
    box: StarterZoneBox,
    *,
    creature_spawns: Sequence[Mapping[str, Any]],
    creature_default_trainer: Mapping[int, int],
    trainer_spell_counts: Mapping[int, int],
    creature_template: Mapping[int, Mapping[str, Any]],
) -> tuple[NativeTrainer, ...]:
    natives: list[NativeTrainer] = []
    seen_classes: set[str] = set()
    for spawn in sorted(creature_spawns, key=lambda row: (row["entry"], row["guid"])):
        if not _spawn_in_box(spawn, box):
            continue
        entry = int(spawn["entry"])
        class_name = _trainer_class_for_entry(
            entry,
            creature_default_trainer,
            trainer_spell_counts,
            creature_template,
        )
        if class_name is None or class_name in seen_classes:
            continue
        template = creature_template[entry]
        seen_classes.add(class_name)
        natives.append(
            NativeTrainer(
                class_name=class_name,
                entry=entry,
                name=str(template["name"]),
                x=float(spawn["x"]),
                y=float(spawn["y"]),
                z=float(spawn["z"]),
                o=float(spawn["o"]),
            )
        )
    return tuple(
        sorted(natives, key=lambda trainer: CLASS_ORDER.index(trainer.class_name))
    )


def build_entry_catalog(
    faction: str,
    *,
    faction_boxes: Sequence[StarterZoneBox],
    creature_spawns: Sequence[Mapping[str, Any]],
    creature_default_trainer: Mapping[int, int],
    trainer_spell_counts: Mapping[int, int],
    creature_template: Mapping[int, Mapping[str, Any]],
) -> dict[str, tuple[int, str, int]]:
    """Map class name -> (entry, display name, spell count) for faction starter zones."""
    best: dict[str, tuple[int, str, int]] = {}
    for spawn in creature_spawns:
        if not _spawn_in_faction_boxes(spawn, faction_boxes):
            continue
        entry = int(spawn["entry"])
        class_name = _trainer_class_for_entry(
            entry,
            creature_default_trainer,
            trainer_spell_counts,
            creature_template,
        )
        if class_name is None:
            continue
        trainer_id = creature_default_trainer[entry]
        spell_count = trainer_spell_counts[trainer_id]
        template = creature_template[entry]
        name = str(template["name"])
        current = best.get(class_name)
        if current is None or (spell_count, entry) < (current[2], current[0]):
            best[class_name] = (entry, name, spell_count)
    if not best:
        msg = f"No curated trainer entries found for faction {faction!r}"
        raise ValueError(msg)
    return best


def compute_zone_gaps(
    box: StarterZoneBox,
    matrix: ComboMatrix,
    natives: Sequence[NativeTrainer],
    *,
    playercreateinfo: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    present = {trainer.class_name for trainer in natives}
    needed: set[str] = set()
    for race_id in _races_in_box(playercreateinfo, box):
        for combo_race, class_id in matrix.new_combos:
            if combo_race != race_id:
                continue
            needed.add(ID_TO_CLASS_NAME[class_id])
    return tuple(class_name for class_name in CLASS_ORDER if class_name in needed - present)


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def _nearest_native(
    natives: Sequence[NativeTrainer],
    *,
    x: float,
    y: float,
) -> NativeTrainer:
    return min(natives, key=lambda trainer: _distance(trainer.x, trainer.y, x, y))


def select_anchor(
    gap_class: str,
    natives: Sequence[NativeTrainer],
    *,
    gap_classes: frozenset[str],
    fallback_x: float,
    fallback_y: float,
) -> NativeTrainer:
    natives_by_class = {trainer.class_name: trainer for trainer in natives}
    for kin_class in CLASS_KINSHIP.get(gap_class, ()):
        if kin_class in gap_classes:
            continue
        anchor = natives_by_class.get(kin_class)
        if anchor is not None:
            return anchor
    return _nearest_native(natives, x=fallback_x, y=fallback_y)


def _perpendicular(side_right: bool, orientation: float) -> tuple[float, float]:
    sign = 1.0 if side_right else -1.0
    return math.sin(orientation) * sign, -math.cos(orientation) * sign


def _min_native_distance(
    x: float,
    y: float,
    natives: Sequence[NativeTrainer],
) -> float:
    return min(_distance(x, y, trainer.x, trainer.y) for trainer in natives)


def _side_scores_at_offset(
    anchor: NativeTrainer,
    offset: float,
    natives: Sequence[NativeTrainer],
) -> tuple[float, float]:
    right = _perpendicular(True, anchor.o)
    left = _perpendicular(False, anchor.o)
    right_x = anchor.x + right[0] * offset
    right_y = anchor.y + right[1] * offset
    left_x = anchor.x + left[0] * offset
    left_y = anchor.y + left[1] * offset
    return (
        _min_native_distance(right_x, right_y, natives),
        _min_native_distance(left_x, left_y, natives),
    )


def _side_name_from_scores(right_score: float, left_score: float) -> str:
    return "right" if right_score >= left_score else "left"


def place_on_side(
    anchor: NativeTrainer,
    side_name: str,
    side_slot: int,
) -> tuple[float, float, float, float]:
    side = _perpendicular(side_name == "right", anchor.o)
    offset = PLACEMENT_GAP + side_slot * PLACEMENT_STEP
    return (
        round(anchor.x + side[0] * offset, 3),
        round(anchor.y + side[1] * offset, 3),
        round(anchor.z, 3),
        round(anchor.o, 4),
    )


def plan_anchor_placement(
    anchor: NativeTrainer,
    natives: Sequence[NativeTrainer],
    side_slots: dict[tuple[int, str], int],
) -> tuple[float, float, float, float, str]:
    """Place the next trainer beside an anchor, tracking slots per side.

    The first trainer on each side of an anchor sits at ``GAP``. Additional
    trainers on the same side extend by ``STEP`` (``GAP + slot * STEP``).
    When one side already has a trainer, the next gap prefers the empty side
    at ``GAP`` rather than jumping to ``GAP + STEP`` on the occupied side.
    """
    anchor_key = anchor.entry
    open_sides = [
        side
        for side in ("right", "left")
        if side_slots.get((anchor_key, side), 0) == 0
    ]
    if open_sides:
        if len(open_sides) == 1:
            side_name = open_sides[0]
        else:
            right_score, left_score = _side_scores_at_offset(anchor, PLACEMENT_GAP, natives)
            side_name = _side_name_from_scores(right_score, left_score)
        side_slot = 0
    else:
        best_side = "right"
        best_score = float("-inf")
        for side_name in ("right", "left"):
            side_slot = side_slots[(anchor_key, side_name)]
            offset = PLACEMENT_GAP + side_slot * PLACEMENT_STEP
            right_score, left_score = _side_scores_at_offset(anchor, offset, natives)
            score = right_score if side_name == "right" else left_score
            if score > best_score:
                best_score = score
                best_side = side_name
        side_name = best_side
        side_slot = side_slots[(anchor_key, side_name)]

    x, y, z, o = place_on_side(anchor, side_name, side_slot)
    side_slots[(anchor_key, side_name)] = side_slot + 1
    return x, y, z, o, side_name


def place_beside_anchor(
    anchor: NativeTrainer,
    slot_index: int,
    natives: Sequence[NativeTrainer],
) -> tuple[float, float, float, float]:
    """Legacy helper: single-side placement at ``GAP + slot_index * STEP``."""
    right_score, left_score = _side_scores_at_offset(
        anchor,
        PLACEMENT_GAP + slot_index * PLACEMENT_STEP,
        natives,
    )
    side_name = _side_name_from_scores(right_score, left_score)
    return place_on_side(anchor, side_name, slot_index)


def _override_for(
    overrides: Sequence[TrainerOverride],
    *,
    zone_name: str,
    class_name: str,
) -> TrainerOverride | None:
    for override in overrides:
        if override.zone == zone_name and override.class_name == class_name:
            return override
    return None


def _resolve_override_anchor(
    natives: Sequence[NativeTrainer],
    anchor_class: str,
    *,
    zone_name: str,
) -> NativeTrainer:
    for trainer in natives:
        if trainer.class_name == anchor_class:
            return trainer
    native_classes = sorted({trainer.class_name for trainer in natives})
    msg = (
        f"Override anchor {anchor_class!r} not present among native trainers "
        f"in {zone_name!r}; natives: {native_classes}"
    )
    raise ValueError(msg)


def _lookup_catalog_entry(
    catalog: Mapping[str, tuple[int, str, int]],
    class_name: str,
    *,
    zone_name: str,
    faction: str,
    override: TrainerOverride | None,
) -> int:
    if override and override.entry is not None:
        return override.entry
    try:
        return catalog[class_name][0]
    except KeyError as exc:
        msg = (
            f"No curated {class_name} trainer entry for faction {faction!r} "
            f"covering gap in {zone_name!r}"
        )
        raise ValueError(msg) from exc


def compute_trainer_rows(
    snapshot: Snapshot,
    matrix: ComboMatrix | None = None,
    *,
    guid_base: int = TRAINER_GUID_BASE,
    overrides: Sequence[TrainerOverride] = (),
) -> TrainerEmitResult:
    matrix = matrix or ComboMatrix.stock()
    data = _trainer_data(snapshot)
    playercreateinfo = data["playercreateinfo"]
    creature_spawns = data["creature_spawns"]
    creature_default_trainer = _parse_int_map(data["creature_default_trainer"])
    trainer_spell_counts = _parse_int_map(data["trainer_spell_counts"])
    creature_template = {int(key): value for key, value in data["creature_template"].items()}
    spawn_defaults = data.get("spawn_defaults", {})

    boxes = build_starter_zone_boxes(playercreateinfo)
    alliance_boxes = tuple(box for box in boxes if box.faction == "A")
    horde_boxes = tuple(box for box in boxes if box.faction == "H")
    entry_catalog: dict[str, dict[str, tuple[int, str, int]]] = {}
    if alliance_boxes:
        entry_catalog["A"] = build_entry_catalog(
            "A",
            faction_boxes=alliance_boxes,
            creature_spawns=creature_spawns,
            creature_default_trainer=creature_default_trainer,
            trainer_spell_counts=trainer_spell_counts,
            creature_template=creature_template,
        )
    if horde_boxes:
        entry_catalog["H"] = build_entry_catalog(
            "H",
            faction_boxes=horde_boxes,
            creature_spawns=creature_spawns,
            creature_default_trainer=creature_default_trainer,
            trainer_spell_counts=trainer_spell_counts,
            creature_template=creature_template,
        )

    order_index = {label: index for index, label in enumerate(ZONE_PROCESS_ORDER)}
    sorted_boxes = sorted(
        boxes,
        key=lambda box: order_index.get(zone_label(box.map_id, box.zone_id), 999),
    )

    rows: list[TrainerRow] = []
    next_guid = guid_base
    for box in sorted_boxes:
        label = zone_label(box.map_id, box.zone_id)
        natives = native_trainers_in_box(
            box,
            creature_spawns=creature_spawns,
            creature_default_trainer=creature_default_trainer,
            trainer_spell_counts=trainer_spell_counts,
            creature_template=creature_template,
        )
        if not natives:
            msg = f"No native trainers found in starter zone {label!r}"
            raise ValueError(msg)

        gap_classes = compute_zone_gaps(
            box,
            matrix,
            natives,
            playercreateinfo=playercreateinfo,
        )
        gap_class_set = frozenset(gap_classes)
        side_slots: dict[tuple[int, str], int] = {}
        catalog = entry_catalog[box.faction]

        for class_name in gap_classes:
            override = _override_for(overrides, zone_name=label, class_name=class_name)
            entry = _lookup_catalog_entry(
                catalog,
                class_name,
                zone_name=label,
                faction=box.faction,
                override=override,
            )
            entry_name = creature_template[entry]["name"]

            if override and override.anchor:
                anchor = _resolve_override_anchor(
                    natives,
                    override.anchor,
                    zone_name=label,
                )
            else:
                anchor = select_anchor(
                    class_name,
                    natives,
                    gap_classes=gap_class_set,
                    fallback_x=box.cx,
                    fallback_y=box.cy,
                )

            computed: TrainerPlacement | None = None
            x, y, z, o, _side = plan_anchor_placement(anchor, natives, side_slots)
            if override and any(
                value is not None for value in (override.x, override.y, override.z, override.o)
            ):
                computed = TrainerPlacement(x=x, y=y, z=z, o=o)
                if override.x is not None:
                    x = override.x
                if override.y is not None:
                    y = override.y
                if override.z is not None:
                    z = override.z
                if override.o is not None:
                    o = override.o

            defaults = spawn_defaults.get(str(entry), {})
            rows.append(
                TrainerRow(
                    guid=next_guid,
                    zone_label=label,
                    map_id=box.map_id,
                    zone_id=box.zone_id,
                    class_name=class_name,
                    entry=entry,
                    entry_name=str(entry_name),
                    anchor_class=anchor.class_name,
                    anchor_name=anchor.name,
                    x=x,
                    y=y,
                    z=z,
                    o=o,
                    equipment_id=int(defaults.get("equipment_id", 0)),
                    curhealth=int(defaults.get("curhealth", 0)),
                    curmana=int(defaults.get("curmana", 0)),
                    npcflag=int(defaults.get("npcflag", 0)),
                    computed=computed,
                )
            )
            next_guid += 1

    if not rows:
        return TrainerEmitResult(rows=(), guid_base=guid_base, guid_max=guid_base - 1)
    return TrainerEmitResult(rows=tuple(rows), guid_base=guid_base, guid_max=next_guid - 1)


def _creature_logical_values(row: TrainerRow) -> dict[str, Any]:
    return {
        "guid": row.guid,
        "entry": row.entry,
        "map": row.map_id,
        "zoneId": 0,
        "areaId": 0,
        "spawnMask": 1,
        "phaseMask": 1,
        "equipment_id": row.equipment_id,
        "position_x": row.x,
        "position_y": row.y,
        "position_z": row.z,
        "orientation": row.o,
        "spawntimesecs": TRAINER_SPAWN_TIME_SECS,
        "wander_distance": 0,
        "currentwaypoint": 0,
        "curhealth": row.curhealth,
        "curmana": row.curmana,
        "MovementType": 0,
        "npcflag": row.npcflag,
        "unit_flags": 0,
        "dynamicflags": 0,
        "ScriptName": "",
        "VerifiedBuild": 0,
        "CreateObject": 0,
        "Comment": row.comment,
    }


def _reserved_guid_delete_range() -> tuple[int, int]:
    """Full mod-uac trainer band so reinstall clears stale guids."""
    return TRAINER_GUID_BASE, MOD_UAC_CREATURE_GUID_MAX


def _render_guid_band_delete(comment: str, *, row_count: int | None = None) -> str:
    delete_min, delete_max = _reserved_guid_delete_range()
    lines = [comment, ""]
    if row_count is not None:
        lines[0] = f"{comment} ({row_count} rows in current emission)"
    lines.extend(
        [
            f"DELETE FROM `{CREATURE_TABLE}` WHERE `guid` BETWEEN "
            f"{delete_min} AND {delete_max};",
            "",
        ]
    )
    return "\n".join(lines)


def render_install_sql(
    result: TrainerEmitResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    if not result.rows:
        return _render_guid_band_delete(
            "-- mod-uac: no starter trainer spawns required for this baseline.",
        )

    snap = snapshot or load_snapshot()
    schema = snap.schema(CREATURE_TABLE)
    delete_min, delete_max = _reserved_guid_delete_range()
    lines = [
        "-- mod-uac: curated starter-list class trainers for new race/class combos.",
        "-- One faction-matched starter trainer per uncovered class per starter zone.",
        f"DELETE FROM `{CREATURE_TABLE}` WHERE `guid` BETWEEN "
        f"{delete_min} AND {delete_max};",
        "",
    ]
    value_lines: list[str] = []
    for row in result.rows:
        prepared = prepare_row(schema, _creature_logical_values(row))
        values = ", ".join(format_sql_literal(prepared[column]) for column in schema.column_names())
        value_lines.append(f"({values})")
    column_sql = ", ".join(f"`{name}`" for name in schema.column_names())
    lines.append(f"INSERT INTO `{CREATURE_TABLE}` ({column_sql}) VALUES")
    lines.append(",\n".join(value_lines) + ";")
    lines.append("")
    return "\n".join(lines)


def render_uninstall_sql(result: TrainerEmitResult) -> str:
    if not result.rows:
        return _render_guid_band_delete(
            "-- mod-uac: revert starter trainer spawns (no rows in current emission)",
        )
    return _render_guid_band_delete(
        "-- mod-uac: revert starter trainer spawns",
        row_count=len(result.rows),
    )


def _format_placement(placement: TrainerPlacement) -> str:
    return f"({placement.x}, {placement.y}, {placement.z}, o={placement.o})"


def render_worksheet(result: TrainerEmitResult) -> str:
    lines = [
        "# mod-uac starter trainers — worksheet",
        "",
        "Emitted coordinates match shipped SQL. Rows with a YAML position override also",
        "show the computed placement before override.",
        "",
    ]
    current_zone: str | None = None
    for row in result.rows:
        if row.zone_label != current_zone:
            current_zone = row.zone_label
            lines.extend(
                [
                    f"## {row.zone_label} (map {row.map_id}, zone {row.zone_id})",
                    "",
                ]
            )
        header = (
            f"- **{row.class_name}** guid `{row.guid}`: entry `{row.entry}` "
            f"({row.entry_name}) — anchor {row.anchor_class} ({row.anchor_name})"
        )
        if row.computed is None:
            lines.append(
                f"{header} @ {_format_placement(TrainerPlacement(row.x, row.y, row.z, row.o))}"
            )
            continue
        lines.append(header)
        lines.append(
            f"  - emitted: {_format_placement(TrainerPlacement(row.x, row.y, row.z, row.o))}"
        )
        lines.append(f"  - computed: {_format_placement(row.computed)} → overridden")
    lines.extend(
        [
            "",
            f"Total: {len(result.rows)} trainers "
            f"(guids {result.guid_base}-{result.guid_max})",
            "",
        ]
    )
    return "\n".join(lines)


def load_trainer_overrides(path: Path | None) -> tuple[TrainerOverride, ...]:
    if path is None or not path.is_file():
        return ()
    overrides: list[TrainerOverride] = []
    current: dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current:
                overrides.append(_override_from_mapping(current))
                current = {}
            line = line[2:].strip()
        if line in {"overrides:", "overrides: []"}:
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "overrides" and value in {"[]", ""}:
            continue
        if key == "position" and value.startswith("{"):
            continue
        if key in {"x", "y", "z", "o"}:
            current[key] = float(value.rstrip(","))
            continue
        if key == "entry":
            current[key] = int(value)
            continue
        current[key] = value.strip("'\"")
    if current:
        overrides.append(_override_from_mapping(current))
    return tuple(overrides)


def _override_from_mapping(payload: Mapping[str, Any]) -> TrainerOverride:
    if "zone" not in payload:
        msg = f"Invalid trainer override payload: {payload!r}"
        raise ValueError(msg)
    class_name = payload.get("class") or payload.get("class_name")
    if not class_name:
        msg = f"Trainer override requires class for zone {payload['zone']!r}: {payload!r}"
        raise ValueError(msg)
    return TrainerOverride(
        zone=str(payload["zone"]),
        class_name=str(class_name),
        entry=int(payload["entry"]) if "entry" in payload else None,
        anchor=str(payload["anchor"]) if "anchor" in payload else None,
        x=float(payload["x"]) if "x" in payload else None,
        y=float(payload["y"]) if "y" in payload else None,
        z=float(payload["z"]) if "z" in payload else None,
        o=float(payload["o"]) if "o" in payload else None,
    )


@dataclass(slots=True)
class TrainerEmitter:
    snapshot: Snapshot | None = None
    matrix: ComboMatrix | None = None
    guid_base: int = TRAINER_GUID_BASE
    overrides: Sequence[TrainerOverride] = ()

    def compute(self) -> TrainerEmitResult:
        snapshot = self.snapshot or load_snapshot()
        return compute_trainer_rows(
            snapshot,
            self.matrix,
            guid_base=self.guid_base,
            overrides=self.overrides,
        )

    def render_install(self, result: TrainerEmitResult | None = None) -> str:
        result = result or self.compute()
        snapshot = self.snapshot or load_snapshot()
        return render_install_sql(result, snapshot=snapshot)

    def render_uninstall(self, result: TrainerEmitResult | None = None) -> str:
        return render_uninstall_sql(result or self.compute())

    def render_worksheet(self, result: TrainerEmitResult | None = None) -> str:
        return render_worksheet(result or self.compute())


def regenerate_checked_in_trainer_sql(
    *,
    snapshot_path: Path | None = None,
    overrides_path: Path | None = DEFAULT_TRAINER_OVERRIDES_PATH,
    matrix: ComboMatrix | None = None,
    guid_base: int = TRAINER_GUID_BASE,
) -> tuple[str, str, str]:
    """Helper for tests and regeneration: install + uninstall SQL + worksheet."""
    snapshot = load_snapshot(snapshot_path) if snapshot_path else load_snapshot()
    overrides = load_trainer_overrides(overrides_path)
    result = compute_trainer_rows(
        snapshot,
        matrix,
        guid_base=guid_base,
        overrides=overrides,
    )
    install = render_install_sql(result, snapshot=snapshot)
    uninstall = render_uninstall_sql(result)
    worksheet = render_worksheet(result)
    return install, uninstall, worksheet
