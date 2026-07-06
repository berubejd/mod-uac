"""Emit playercreateinfo SQL for new race/class combos."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.charstartoutfit_export import OutfitRecord, render_install_sql, render_uninstall_sql
from aracgen.kits import CanonicalKitResolver, ComboKit
from aracgen.item_prototypes import ItemPrototypeStore
from aracgen.matrix import ComboMatrix, class_bit, race_bit
from aracgen.starter_skills import StarterSkillRow
from aracgen.stock_loader import StockKitStore


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


def _combo_keys(result: PlayerCreateResult) -> str:
    pairs = ", ".join(f"({kit.race_id}, {kit.class_id})" for kit in result.kits)
    return pairs


def render_playercreateinfo_install(result: PlayerCreateResult) -> str:
    if not result.kits:
        return "-- mod-uac: no playercreateinfo rows required.\n"

    lines = [
        "-- mod-uac: playercreateinfo rows for Unlock All Classes",
        f"-- combos: {_combo_keys(result)}",
        "",
    ]
    for kit in result.kits:
        spawn = kit.spawn
        lines.append(
            "INSERT INTO `playercreateinfo` "
            "(`race`, `class`, `map`, `zone`, `position_x`, `position_y`, "
            "`position_z`, `orientation`) "
            f"VALUES ({kit.race_id}, {kit.class_id}, {spawn.map_id}, {spawn.zone_id}, "
            f"{spawn.x}, {spawn.y}, {spawn.z}, {spawn.orientation});"
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
            f"DELETE FROM `playercreateinfo` WHERE (`race`, `class`) IN (({pairs}));",
            "",
        ]
    )


def render_playercreateinfo_action_install(result: PlayerCreateResult) -> str:
    if not result.kits:
        return "-- mod-uac: no playercreateinfo_action rows required.\n"

    lines = [
        "-- mod-uac: playercreateinfo_action rows for Unlock All Classes",
        "",
    ]
    for kit in result.kits:
        for entry in kit.actions:
            lines.append(
                "INSERT INTO `playercreateinfo_action` "
                "(`race`, `class`, `button`, `action`, `type`) "
                f"VALUES ({kit.race_id}, {kit.class_id}, {entry.button}, "
                f"{entry.action}, {entry.action_type});"
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
            f"DELETE FROM `playercreateinfo_action` WHERE (`race`, `class`) IN (({pairs}));",
            "",
        ]
    )


def _kits_with_skills(result: PlayerCreateResult) -> tuple[ComboKit, ...]:
    return tuple(kit for kit in result.kits if kit.skills)


def render_charstartoutfit_install(result: PlayerCreateResult) -> str:
    lines: list[str] = []
    if result.kits:
        pairs = "), (".join(f"{kit.race_id}, {kit.class_id}" for kit in result.kits)
        lines.extend(
            [
                "-- mod-uac: remove legacy playercreateinfo_item rows superseded by charstartoutfit_dbc",
                "",
                f"DELETE FROM `playercreateinfo_item` WHERE (`race`, `class`) IN (({pairs}));",
                "",
            ]
        )
    lines.append(render_install_sql(result.outfit_records).rstrip())
    lines.append("")
    return "\n".join(lines)


def render_charstartoutfit_uninstall(result: PlayerCreateResult) -> str:
    return render_uninstall_sql(result.outfit_records)


def render_playercreateinfo_skills_install(result: PlayerCreateResult) -> str:
    rows: list[StarterSkillRow] = []
    for kit in result.kits:
        rows.extend(kit.skills)
    if not rows:
        return "-- mod-uac: no playercreateinfo_skills rows required.\n"

    lines = [
        "-- mod-uac: playercreateinfo_skills for gear-required proficiencies on new combos",
        "-- Gear-derived with reference weapon-skill sanity check; skips stock-covered skills.",
        "",
    ]
    for row in rows:
        lines.append(
            "INSERT INTO `playercreateinfo_skills` "
            "(`raceMask`, `classMask`, `skill`, `rank`, `comment`) "
            f"VALUES ({race_bit(row.race_id)}, {class_bit(row.class_id)}, "
            f"{row.skill_id}, {row.rank}, 'mod-uac: starter gear skill');"
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
    ) -> None:
        self.resolver = resolver

    def compute(self) -> PlayerCreateResult:
        return compute_player_create(self.resolver)

    def render_install_files(self, result: PlayerCreateResult | None = None) -> dict[str, str]:
        data = result or self.compute()
        return {
            "playercreateinfo": render_playercreateinfo_install(data),
            "playercreateinfo_action": render_playercreateinfo_action_install(data),
            "charstartoutfit_dbc": render_charstartoutfit_install(data),
            "playercreateinfo_skills": render_playercreateinfo_skills_install(data),
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
    item_template_path=None,
    db_max_outfit_id: int = 0,
) -> CanonicalKitResolver:
    from pathlib import Path

    return CanonicalKitResolver(
        matrix=matrix or ComboMatrix.stock(),
        store=StockKitStore.load(Path(stock_dir) if stock_dir else None),
        outfit=source_outfit,
        item_prototypes=ItemPrototypeStore(
            Path(item_template_path) if item_template_path else None
        ),
        db_max_outfit_id=db_max_outfit_id,
    )
