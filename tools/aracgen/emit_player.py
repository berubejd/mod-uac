"""Emit playercreateinfo SQL for new race/class combos."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.charstartoutfit_export import OutfitRecord, render_install_sql, render_uninstall_sql
from aracgen.kits import CanonicalKitResolver, ComboKit
from aracgen.matrix import ComboMatrix, class_bit, race_bit
from aracgen.schema_emit import render_insert
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import Snapshot
from aracgen.starter_skills import StarterSkillRow

PLAYERCREATEINFO_TABLE = "playercreateinfo"
PLAYERCREATEINFO_ACTION_TABLE = "playercreateinfo_action"
PLAYERCREATEINFO_SKILLS_TABLE = "playercreateinfo_skills"


@dataclass(frozen=True, slots=True)
class PlayerCreateResult:
    kits: tuple[ComboKit, ...]

    @property
    def outfit_records(self) -> tuple[OutfitRecord, ...]:
        return tuple(
            record for kit in self.kits for record in kit.outfit_records
        )


def compute_player_create(resolver: CanonicalKitResolver) -> PlayerCreateResult:
    return PlayerCreateResult(kits=tuple(resolver.resolve_all()))


def _resolve_snapshot(snapshot: Snapshot | None) -> Snapshot:
    return snapshot if snapshot is not None else load_snapshot()


def _combo_keys(result: PlayerCreateResult) -> str:
    pairs = ", ".join(f"({kit.race_id}, {kit.class_id})" for kit in result.kits)
    return pairs


def render_playercreateinfo_install(
    result: PlayerCreateResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    if not result.kits:
        return "-- mod-uac: no playercreateinfo rows required.\n"

    schema = _resolve_snapshot(snapshot).schema(PLAYERCREATEINFO_TABLE)
    lines = [
        "-- mod-uac: playercreateinfo rows for Unlock All Classes",
        f"-- combos: {_combo_keys(result)}",
        "",
    ]
    for kit in result.kits:
        spawn = kit.spawn
        lines.append(
            render_insert(
                PLAYERCREATEINFO_TABLE,
                schema,
                {
                    "race": kit.race_id,
                    "class": kit.class_id,
                    "map": spawn.map_id,
                    "zone": spawn.zone_id,
                    "position_x": spawn.x,
                    "position_y": spawn.y,
                    "position_z": spawn.z,
                    "orientation": spawn.orientation,
                },
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_playercreateinfo_uninstall(result: PlayerCreateResult) -> str:
    if not result.kits:
        return "-- mod-uac: no playercreateinfo rows to remove.\n"

    pairs = "), (".join(f"{kit.race_id}, {kit.class_id}" for kit in result.kits)
    return "\n".join(
        [
            "-- mod-uac: revert playercreateinfo rows",
            "",
            f"DELETE FROM `{PLAYERCREATEINFO_TABLE}` WHERE (`race`, `class`) IN (({pairs}));",
            "",
        ]
    )


def render_playercreateinfo_action_install(
    result: PlayerCreateResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    if not result.kits:
        return "-- mod-uac: no playercreateinfo_action rows required.\n"

    schema = _resolve_snapshot(snapshot).schema(PLAYERCREATEINFO_ACTION_TABLE)
    lines = [
        "-- mod-uac: playercreateinfo_action rows for Unlock All Classes",
        "",
    ]
    for kit in result.kits:
        for entry in kit.actions:
            lines.append(
                render_insert(
                    PLAYERCREATEINFO_ACTION_TABLE,
                    schema,
                    {
                        "race": kit.race_id,
                        "class": kit.class_id,
                        "button": entry.button,
                        "action": entry.action,
                        "type": entry.action_type,
                    },
                )
            )
    lines.append("")
    return "\n".join(lines)


def render_playercreateinfo_action_uninstall(result: PlayerCreateResult) -> str:
    if not result.kits:
        return "-- mod-uac: no playercreateinfo_action rows to remove.\n"
    pairs = "), (".join(f"{kit.race_id}, {kit.class_id}" for kit in result.kits)
    return "\n".join(
        [
            "-- mod-uac: revert playercreateinfo_action rows",
            "",
            f"DELETE FROM `{PLAYERCREATEINFO_ACTION_TABLE}` "
            f"WHERE (`race`, `class`) IN (({pairs}));",
            "",
        ]
    )


def _kits_with_skills(result: PlayerCreateResult) -> tuple[ComboKit, ...]:
    return tuple(kit for kit in result.kits if kit.skills)


def render_charstartoutfit_install(
    result: PlayerCreateResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    lines: list[str] = []
    if result.kits:
        pairs = "), (".join(f"{kit.race_id}, {kit.class_id}" for kit in result.kits)
        lines.extend(
            [
                "-- mod-uac: remove legacy playercreateinfo_item rows "
                "superseded by charstartoutfit_dbc",
                "",
                f"DELETE FROM `playercreateinfo_item` WHERE (`race`, `class`) IN (({pairs}));",
                "",
            ]
        )
    lines.append(render_install_sql(result.outfit_records, snapshot=snapshot).rstrip())
    lines.append("")
    return "\n".join(lines)


def render_charstartoutfit_uninstall(result: PlayerCreateResult) -> str:
    return render_uninstall_sql(result.outfit_records)


def render_playercreateinfo_skills_install(
    result: PlayerCreateResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    rows: list[StarterSkillRow] = []
    for kit in result.kits:
        rows.extend(kit.skills)
    if not rows:
        return "-- mod-uac: no playercreateinfo_skills rows required.\n"

    schema = _resolve_snapshot(snapshot).schema(PLAYERCREATEINFO_SKILLS_TABLE)
    lines = [
        "-- mod-uac: playercreateinfo_skills for gear-required proficiencies on new combos",
        "-- Gear-derived with reference weapon-skill sanity check; skips stock-covered skills.",
        "",
    ]
    for row in rows:
        lines.append(
            render_insert(
                PLAYERCREATEINFO_SKILLS_TABLE,
                schema,
                {
                    "raceMask": race_bit(row.race_id),
                    "classMask": class_bit(row.class_id),
                    "skill": row.skill_id,
                    "rank": row.rank,
                    "comment": "mod-uac: starter gear skill",
                },
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_playercreateinfo_skills_uninstall(result: PlayerCreateResult) -> str:
    kits = _kits_with_skills(result)
    if not kits:
        return "-- mod-uac: no playercreateinfo_skills rows to remove.\n"

    lines = [
        "-- mod-uac: revert playercreateinfo_skills overlays for new combos",
        "",
    ]
    for kit in kits:
        skill_ids = ", ".join(str(row.skill_id) for row in kit.skills)
        lines.append(
            "DELETE FROM `playercreateinfo_skills` "
            f"WHERE `raceMask` = {race_bit(kit.race_id)} "
            f"AND `classMask` = {class_bit(kit.class_id)} "
            f"AND `skill` IN ({skill_ids});"
        )
    lines.append("")
    return "\n".join(lines)


class PlayerCreateEmitter:
    def __init__(
        self,
        resolver: CanonicalKitResolver,
        snapshot: Snapshot | None = None,
    ) -> None:
        self.resolver = resolver
        self.snapshot = snapshot

    def compute(self) -> PlayerCreateResult:
        return compute_player_create(self.resolver)

    def render_install_files(self, result: PlayerCreateResult | None = None) -> dict[str, str]:
        data = result or self.compute()
        snapshot = self.snapshot
        return {
            "playercreateinfo": render_playercreateinfo_install(data, snapshot=snapshot),
            "playercreateinfo_action": render_playercreateinfo_action_install(
                data,
                snapshot=snapshot,
            ),
            "charstartoutfit_dbc": render_charstartoutfit_install(data, snapshot=snapshot),
            "playercreateinfo_skills": render_playercreateinfo_skills_install(
                data,
                snapshot=snapshot,
            ),
        }

    def render_uninstall_files(self, result: PlayerCreateResult | None = None) -> dict[str, str]:
        data = result or self.compute()
        return {
            "playercreateinfo": render_playercreateinfo_uninstall(data),
            "playercreateinfo_action": render_playercreateinfo_action_uninstall(data),
            "charstartoutfit_dbc": render_charstartoutfit_uninstall(data),
            "playercreateinfo_skills": render_playercreateinfo_skills_uninstall(data),
        }


def build_resolver(
    source_outfit,
    matrix: ComboMatrix | None = None,
    stock_dir=None,
    item_prototypes_path=None,
    db_max_outfit_id: int = 0,
) -> CanonicalKitResolver:
    from pathlib import Path

    from aracgen.item_prototypes import ItemPrototypeStore
    from aracgen.stock_loader import StockKitStore

    return CanonicalKitResolver(
        matrix=matrix or ComboMatrix.stock(),
        store=StockKitStore.load(Path(stock_dir) if stock_dir else None),
        outfit=source_outfit,
        item_prototypes=ItemPrototypeStore(
            Path(item_prototypes_path) if item_prototypes_path else None
        ),
        db_max_outfit_id=db_max_outfit_id,
    )
