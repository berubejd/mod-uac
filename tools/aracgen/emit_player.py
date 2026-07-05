"""Emit playercreateinfo SQL for new race/class combos."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.kits import CanonicalKitResolver, ComboKit
from aracgen.matrix import ComboMatrix
from aracgen.stock_loader import StockKitStore


@dataclass(frozen=True, slots=True)
class PlayerCreateResult:
    kits: tuple[ComboKit, ...]


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


def _kits_with_items(result: PlayerCreateResult) -> tuple[ComboKit, ...]:
    return tuple(kit for kit in result.kits if kit.items)


def render_playercreateinfo_item_uninstall(result: PlayerCreateResult) -> str:
    kits = _kits_with_items(result)
    if not kits:
        return "-- mod-uac: no playercreateinfo_item rows to remove.\n"
    pairs = "), (".join(f"{kit.race_id}, {kit.class_id}" for kit in kits)
    return "\n".join(
        [
            "-- mod-uac: revert playercreateinfo_item rows",
            "",
            f"DELETE FROM `playercreateinfo_item` WHERE (`race`, `class`) IN (({pairs}));",
            "",
        ]
    )


def render_playercreateinfo_item_install(result: PlayerCreateResult) -> str:
    kits = _kits_with_items(result)
    if not kits:
        return "-- mod-uac: no playercreateinfo_item rows required.\n"

    lines = [
        "-- mod-uac: playercreateinfo_item rows (from CharStartOutfit reference kits)",
        "-- Skips combos that already have native CharStartOutfit.dbc rows.",
        "",
    ]
    for kit in kits:
        for item_id, amount in kit.items:
            lines.append(
                "INSERT INTO `playercreateinfo_item` "
                "(`race`, `class`, `itemid`, `amount`) "
                f"VALUES ({kit.race_id}, {kit.class_id}, {item_id}, {amount});"
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
            "playercreateinfo_item": render_playercreateinfo_item_install(data),
        }

    def render_uninstall_files(self, result: PlayerCreateResult | None = None) -> dict[str, str]:
        data = result or self.compute()
        return {
            "playercreateinfo": render_playercreateinfo_uninstall(data),
            "playercreateinfo_action": render_playercreateinfo_action_uninstall(data),
            "playercreateinfo_item": render_playercreateinfo_item_uninstall(data),
        }


def build_resolver(
    source_outfit,
    matrix: ComboMatrix | None = None,
    stock_dir=None,
) -> CanonicalKitResolver:
    from pathlib import Path

    return CanonicalKitResolver(
        matrix=matrix or ComboMatrix.stock(),
        store=StockKitStore.load(Path(stock_dir) if stock_dir else None),
        outfit=source_outfit,
    )
