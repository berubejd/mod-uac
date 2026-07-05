"""Emit targeted class-quest SQL for new race/class combos (Phase 1g)."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.class_quest_catalog import (
    ALLIANCE_FACTION_MASK,
    EMITTED_CLASS_CHAINS,
    FACTION_UNLOCK_CHAINS,
    HORDE_FACTION_MASK,
    ClassQuestChain,
    FactionQuestChain,
)
from aracgen.geography import quest_access_tier, spawn_zone_for_race
from aracgen.kits import ALLIANCE_RACES, HORDE_RACES
from aracgen.matrix import ComboMatrix, class_bit, race_bit
from aracgen.stock_loader import StockKitStore

SPELL_CUSTOM_CLASSES: frozenset[int] = frozenset(EMITTED_CLASS_CHAINS)


@dataclass(frozen=True, slots=True)
class QuestRacePatch:
    quest_id: int
    original_allowable_races: int
    new_allowable_races: int
    tier: str
    race_id: int
    class_id: int
    note: str = ""


@dataclass(frozen=True, slots=True)
class QuestAddonPatch:
    quest_id: int
    original_max_level: int
    new_max_level: int = 0
    note: str = ""


@dataclass(frozen=True, slots=True)
class SpellGrantRow:
    race_id: int
    class_id: int
    spell_id: int
    tier: str
    note: str


@dataclass(frozen=True, slots=True)
class ClassQuestResult:
    quest_patches: tuple[QuestRacePatch, ...]
    addon_patches: tuple[QuestAddonPatch, ...]
    spell_grants: tuple[SpellGrantRow, ...]


def _faction_of(race_id: int) -> frozenset[int]:
    if race_id in ALLIANCE_RACES:
        return ALLIANCE_RACES
    if race_id in HORDE_RACES:
        return HORDE_RACES
    msg = f"Race {race_id} is not in a known faction"
    raise ValueError(msg)


def _faction_mask(chain: FactionQuestChain) -> int:
    if chain.faction == "alliance":
        return ALLIANCE_FACTION_MASK
    return HORDE_FACTION_MASK


def _race_allowed(stock_allowable_races: int, race_id: int) -> bool:
    if stock_allowable_races == 0:
        return True
    return bool(stock_allowable_races & race_bit(race_id))


def _best_chain(
    race_id: int,
    class_id: int,
    chains: tuple[ClassQuestChain, ...],
    target_zone_id: int,
) -> ClassQuestChain:
    faction = _faction_of(race_id)
    candidates = [chain for chain in chains if chain.reference_race_id in faction]
    if not candidates:
        msg = f"No class quest chain for class {class_id} in faction of race {race_id}"
        raise ValueError(msg)

    def sort_key(chain: ClassQuestChain) -> tuple[int, int, int]:
        tier = quest_access_tier(target_zone_id, chain.primary_zone_id)
        tier_rank = {"A": 0, "B": 1, "C": 2}[tier]
        return (tier_rank, chain.primary_zone_id, chain.reference_race_id)

    return min(candidates, key=sort_key)


FactionPatchResult = tuple[tuple[QuestRacePatch, ...], tuple[QuestAddonPatch, ...]]


def compute_faction_quest_patches() -> FactionPatchResult:
    """§8.3 — open reference chains to the full faction regardless of combo tier."""
    quest_patches: dict[int, QuestRacePatch] = {}
    addon_patches: dict[int, QuestAddonPatch] = {}

    for chain in FACTION_UNLOCK_CHAINS:
        target_mask = _faction_mask(chain)
        for quest in chain.quests:
            stock_mask = quest.stock_allowable_races
            if stock_mask == 0 or stock_mask == target_mask:
                continue

            new_mask = stock_mask | target_mask
            note = f"mod-uac: {chain.label} faction unlock"
            existing = quest_patches.get(quest.quest_id)
            if existing is None:
                quest_patches[quest.quest_id] = QuestRacePatch(
                    quest_id=quest.quest_id,
                    original_allowable_races=stock_mask,
                    new_allowable_races=new_mask,
                    tier="faction",
                    race_id=0,
                    class_id=chain.class_id,
                    note=note,
                )
            else:
                quest_patches[quest.quest_id] = QuestRacePatch(
                    quest_id=quest.quest_id,
                    original_allowable_races=existing.original_allowable_races,
                    new_allowable_races=existing.new_allowable_races | new_mask,
                    tier="faction",
                    race_id=0,
                    class_id=chain.class_id,
                    note=existing.note,
                )

            if quest.stock_max_level > 0 and quest.quest_id not in addon_patches:
                addon_patches[quest.quest_id] = QuestAddonPatch(
                    quest_id=quest.quest_id,
                    original_max_level=quest.stock_max_level,
                    note=note,
                )

    return (
        tuple(sorted(quest_patches.values(), key=lambda row: row.quest_id)),
        tuple(sorted(addon_patches.values(), key=lambda row: row.quest_id)),
    )


def _resolve_combo(
    race_id: int,
    class_id: int,
    store: StockKitStore,
) -> tuple[tuple[QuestRacePatch, ...], tuple[SpellGrantRow, ...]]:
    chains = EMITTED_CLASS_CHAINS.get(class_id)
    if not chains:
        return (), ()

    target_zone = spawn_zone_for_race(store, race_id)
    chain = _best_chain(race_id, class_id, chains, target_zone)
    tier = quest_access_tier(target_zone, chain.primary_zone_id)

    if tier == "C":
        note = f"mod-uac: {race_id}/{class_id} cross-continent class quest fallback"
        grant = SpellGrantRow(
            race_id=race_id,
            class_id=class_id,
            spell_id=chain.reward_spell_id,
            tier=tier,
            note=note,
        )
        return (), (grant,)

    patches: list[QuestRacePatch] = []
    for quest in chain.quests:
        if _race_allowed(quest.stock_allowable_races, race_id):
            continue
        new_mask = quest.stock_allowable_races | race_bit(race_id)
        patches.append(
            QuestRacePatch(
                quest_id=quest.quest_id,
                original_allowable_races=quest.stock_allowable_races,
                new_allowable_races=new_mask,
                tier=tier,
                race_id=race_id,
                class_id=class_id,
            )
        )
    return tuple(patches), ()


def _merge_quest_patches(patches: list[QuestRacePatch]) -> tuple[QuestRacePatch, ...]:
    merged: dict[int, QuestRacePatch] = {}
    for patch in patches:
        existing = merged.get(patch.quest_id)
        if existing is None:
            merged[patch.quest_id] = patch
            continue
        merged[patch.quest_id] = QuestRacePatch(
            quest_id=patch.quest_id,
            original_allowable_races=existing.original_allowable_races,
            new_allowable_races=existing.new_allowable_races | patch.new_allowable_races,
            tier=existing.tier,
            race_id=existing.race_id,
            class_id=existing.class_id,
            note=existing.note or patch.note,
        )
    return tuple(sorted(merged.values(), key=lambda row: row.quest_id))


def compute_class_quests(matrix: ComboMatrix, store: StockKitStore) -> ClassQuestResult:
    quest_patches: list[QuestRacePatch] = []
    spell_grants: list[SpellGrantRow] = []

    for race_id, class_id in sorted(matrix.new_combos):
        if class_id not in SPELL_CUSTOM_CLASSES:
            continue
        patches, grants = _resolve_combo(race_id, class_id, store)
        quest_patches.extend(patches)
        spell_grants.extend(grants)

    faction_patches, addon_patches = compute_faction_quest_patches()
    quest_patches.extend(faction_patches)

    return ClassQuestResult(
        quest_patches=_merge_quest_patches(quest_patches),
        addon_patches=addon_patches,
        spell_grants=tuple(spell_grants),
    )


def render_quest_install(result: ClassQuestResult) -> str:
    if not result.quest_patches:
        return "-- mod-uac: no quest_template race-mask patches required.\n"

    lines = [
        "-- mod-uac: quest_template AllowableRaces patches (Phase 1g)",
        "-- warlock tier A/B per-combo; §8.3 faction-wide unlock for travel-gated classes",
        "",
    ]
    for patch in result.quest_patches:
        tier_label = patch.tier if patch.tier != "faction" else "faction (§8.3)"
        lines.append(
            f"-- quest {patch.quest_id}: tier {tier_label} "
            f"(stock {patch.original_allowable_races} -> {patch.new_allowable_races})"
        )
        if patch.note:
            lines.append(f"--   {patch.note}")
        lines.append(
            "UPDATE `quest_template` "
            f"SET `AllowableRaces` = {patch.new_allowable_races} "
            f"WHERE `ID` = {patch.quest_id};"
        )
    lines.append("")
    return "\n".join(lines)


def render_quest_uninstall(result: ClassQuestResult) -> str:
    if not result.quest_patches:
        return "-- mod-uac: no quest_template patches to revert.\n"

    lines = [
        "-- mod-uac: revert quest_template AllowableRaces patches",
        "",
    ]
    for patch in result.quest_patches:
        lines.append(
            "UPDATE `quest_template` "
            f"SET `AllowableRaces` = {patch.original_allowable_races} "
            f"WHERE `ID` = {patch.quest_id};"
        )
    lines.append("")
    return "\n".join(lines)


def render_addon_install(result: ClassQuestResult) -> str:
    if not result.addon_patches:
        return "-- mod-uac: no quest_template_addon anti-gray patches required.\n"

    lines = [
        "-- mod-uac: quest_template_addon MaxLevel patches (§8.3 anti-gray)",
        "",
    ]
    for patch in result.addon_patches:
        lines.append(
            f"-- quest {patch.quest_id}: MaxLevel {patch.original_max_level} -> "
            f"{patch.new_max_level}"
        )
        lines.append(
            "UPDATE `quest_template_addon` "
            f"SET `MaxLevel` = {patch.new_max_level} "
            f"WHERE `ID` = {patch.quest_id};"
        )
    lines.append("")
    return "\n".join(lines)


def render_addon_uninstall(result: ClassQuestResult) -> str:
    if not result.addon_patches:
        return "-- mod-uac: no quest_template_addon patches to revert.\n"

    lines = [
        "-- mod-uac: revert quest_template_addon MaxLevel patches",
        "",
    ]
    for patch in result.addon_patches:
        lines.append(
            "UPDATE `quest_template_addon` "
            f"SET `MaxLevel` = {patch.original_max_level} "
            f"WHERE `ID` = {patch.quest_id};"
        )
    lines.append("")
    return "\n".join(lines)


def render_spell_install(result: ClassQuestResult) -> str:
    if not result.spell_grants:
        return "-- mod-uac: no playercreateinfo_spell_custom rows required.\n"

    lines = [
        "-- mod-uac: creation spell grants for cross-continent class combos (Phase 1g tier C)",
        "",
    ]
    for row in result.spell_grants:
        lines.append(
            "INSERT INTO `playercreateinfo_spell_custom` "
            "(`racemask`, `classmask`, `Spell`, `Note`) "
            f"VALUES ({race_bit(row.race_id)}, {class_bit(row.class_id)}, "
            f"{row.spell_id}, '{row.note}');"
        )
    lines.append("")
    return "\n".join(lines)


def render_spell_uninstall(result: ClassQuestResult) -> str:
    if not result.spell_grants:
        return "-- mod-uac: no playercreateinfo_spell_custom rows to remove.\n"

    lines = [
        "-- mod-uac: revert playercreateinfo_spell_custom grants",
        "",
    ]
    for row in result.spell_grants:
        lines.append(
            "DELETE FROM `playercreateinfo_spell_custom` "
            f"WHERE `racemask` = {race_bit(row.race_id)} "
            f"AND `classmask` = {class_bit(row.class_id)} "
            f"AND `Spell` = {row.spell_id};"
        )
    lines.append("")
    return "\n".join(lines)


@dataclass(slots=True)
class ClassQuestEmitter:
    matrix: ComboMatrix
    store: StockKitStore

    def compute(self) -> ClassQuestResult:
        return compute_class_quests(self.matrix, self.store)

    def render_install_files(self, result: ClassQuestResult | None = None) -> dict[str, str]:
        data = result or self.compute()
        return {
            "quest_template": render_quest_install(data),
            "quest_template_addon": render_addon_install(data),
            "playercreateinfo_spell_custom": render_spell_install(data),
        }

    def render_uninstall_files(self, result: ClassQuestResult | None = None) -> dict[str, str]:
        data = result or self.compute()
        return {
            "quest_template": render_quest_uninstall(data),
            "quest_template_addon": render_addon_uninstall(data),
            "playercreateinfo_spell_custom": render_spell_uninstall(data),
        }
