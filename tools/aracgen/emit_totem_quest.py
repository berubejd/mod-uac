"""Emit synthetic Earth Totem access quests for displaced shaman races (Call of Earth).

Adds two zero-objective "Call of Earth" quests (one per faction) attached to the
shaman trainers mod-uac places in the displaced starter zones, and re-narrows the
Draenei vanilla chain so every race is covered by exactly one Earth-Totem path.
Quest IDs are drawn from a fixed reserved band, so install is idempotent via
DELETE + INSERT without the runtime ``MAX(ID)`` recovery the prototype needed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aracgen.emit_trainers import (
    DEFAULT_TRAINER_OVERRIDES_PATH,
    TrainerRow,
    compute_trainer_rows,
    load_trainer_overrides,
)
from aracgen.matrix import ComboMatrix
from aracgen.schema_emit import render_insert, render_update
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import (
    MOD_UAC_QUEST_ID_MAX,
    MOD_UAC_QUEST_ID_MIN,
    Snapshot,
)
from aracgen.totem_quest_catalog import (
    EARTH_ACCESS_QUESTS,
    EARTH_CHAIN_RENARROW,
    EARTH_QUEST_INFO_ID,
    EARTH_QUEST_LEVEL,
    EARTH_QUEST_MIN_LEVEL,
    EARTH_QUEST_SORT_ID,
    EARTH_QUEST_TYPE,
    EARTH_QUEST_XP_DIFFICULTY,
    EARTH_TOTEM_ITEM_ID,
    SHAMAN_CLASSMASK,
    SyntheticTotemQuest,
)

QUEST_TEMPLATE_TABLE = "quest_template"
QUEST_TEMPLATE_ADDON_TABLE = "quest_template_addon"
QUEST_OFFER_REWARD_TABLE = "quest_offer_reward"
CREATURE_QUESTSTARTER_TABLE = "creature_queststarter"
CREATURE_QUESTENDER_TABLE = "creature_questender"

NPCFLAG_QUESTGIVER = 2

# Starter zones (map_id, zone_id) per faction, from trainer_catalog labels.
# Alliance: Coldridge, Northshire, Shadowglen, Ammen Vale.
ALLIANCE_STARTER_ZONES: frozenset[tuple[int, int]] = frozenset(
    {(0, 1), (0, 12), (1, 141), (530, 3526)}
)
# Horde: Deathknell, Valley of Trials, Camp Narache, Sunstrider Isle.
HORDE_STARTER_ZONES: frozenset[tuple[int, int]] = frozenset(
    {(0, 85), (1, 14), (1, 215), (530, 3431)}
)


@dataclass(frozen=True, slots=True)
class TotemQuestResult:
    """Resolved synthetic quests: quest -> (id, trainer entry)."""

    quest_ids: dict[str, int]  # faction -> quest ID
    trainer_entries: dict[str, int]  # faction -> shaman trainer entry


def _zones_for_faction(faction: str) -> frozenset[tuple[int, int]]:
    return ALLIANCE_STARTER_ZONES if faction == "alliance" else HORDE_STARTER_ZONES


def _template_npcflag(snapshot: Snapshot, entry: int) -> int | None:
    templates = snapshot.data.get("trainers", {}).get("creature_template", {})
    meta = templates.get(str(entry)) or templates.get(entry)
    if not meta or "npcflag" not in meta:
        return None
    return int(meta["npcflag"])


def resolve_shaman_trainer_entry(
    faction: str,
    trainer_rows: Sequence[TrainerRow],
    snapshot: Snapshot,
) -> int:
    """Derive the faction's mod-uac shaman trainer entry and verify it is a questgiver."""
    zones = _zones_for_faction(faction)
    entries = {
        row.entry
        for row in trainer_rows
        if row.class_name == "Shaman" and (row.map_id, row.zone_id) in zones
    }
    if not entries:
        msg = f"No mod-uac shaman starter trainer found for faction {faction!r}"
        raise ValueError(msg)
    if len(entries) != 1:
        msg = (
            f"Multiple shaman trainer entries for faction {faction!r}: {sorted(entries)}. "
            "The synthetic Call of Earth quest attaches to a single entry."
        )
        raise ValueError(msg)
    entry = next(iter(entries))

    npcflag = _template_npcflag(snapshot, entry)
    if npcflag is None:
        msg = (
            f"Snapshot has no npcflag for shaman trainer entry {entry}; refresh the snapshot "
            "so questgiver validation can run (capture_snapshot.py)."
        )
        raise ValueError(msg)
    if not npcflag & NPCFLAG_QUESTGIVER:
        msg = (
            f"Shaman trainer entry {entry} (npcflag {npcflag}) is not a QUESTGIVER; it cannot "
            f"offer the synthetic Call of Earth quest. Choose a questgiver trainer via "
            f"trainer_overrides.yaml for faction {faction!r}."
        )
        raise ValueError(msg)
    return entry


def _quest_id_for_index(index: int) -> int:
    quest_id = MOD_UAC_QUEST_ID_MIN + index
    if quest_id > MOD_UAC_QUEST_ID_MAX:
        msg = f"Synthetic quest ID {quest_id} exceeds reserved band max {MOD_UAC_QUEST_ID_MAX}"
        raise ValueError(msg)
    return quest_id


def compute_totem_quests(
    trainer_rows: Sequence[TrainerRow],
    snapshot: Snapshot,
) -> TotemQuestResult:
    quest_ids: dict[str, int] = {}
    trainer_entries: dict[str, int] = {}
    for index, quest in enumerate(EARTH_ACCESS_QUESTS):
        quest_ids[quest.faction] = _quest_id_for_index(index)
        trainer_entries[quest.faction] = resolve_shaman_trainer_entry(
            quest.faction, trainer_rows, snapshot
        )
    return TotemQuestResult(quest_ids=quest_ids, trainer_entries=trainer_entries)


def _quest_template_row(quest: SyntheticTotemQuest, quest_id: int) -> dict[str, object]:
    return {
        "ID": quest_id,
        "QuestType": EARTH_QUEST_TYPE,
        "QuestLevel": EARTH_QUEST_LEVEL,
        "MinLevel": EARTH_QUEST_MIN_LEVEL,
        "QuestSortID": EARTH_QUEST_SORT_ID,
        "QuestInfoID": EARTH_QUEST_INFO_ID,
        "RewardXPDifficulty": EARTH_QUEST_XP_DIFFICULTY,
        "AllowableRaces": quest.allowable_races,
        "RewardItem1": EARTH_TOTEM_ITEM_ID,
        "RewardAmount1": 1,
        "Flags": 0,
        "LogTitle": quest.log_title,
        "LogDescription": quest.log_description,
        "QuestDescription": quest.quest_description,
        "QuestCompletionLog": quest.quest_completion_log,
    }


def _reserved_band_deletes() -> list[str]:
    lo, hi = MOD_UAC_QUEST_ID_MIN, MOD_UAC_QUEST_ID_MAX
    return [
        f"DELETE FROM `{CREATURE_QUESTSTARTER_TABLE}` WHERE `quest` BETWEEN {lo} AND {hi};",
        f"DELETE FROM `{CREATURE_QUESTENDER_TABLE}` WHERE `quest` BETWEEN {lo} AND {hi};",
        f"DELETE FROM `{QUEST_OFFER_REWARD_TABLE}` WHERE `ID` BETWEEN {lo} AND {hi};",
        f"DELETE FROM `{QUEST_TEMPLATE_ADDON_TABLE}` WHERE `ID` BETWEEN {lo} AND {hi};",
        f"DELETE FROM `{QUEST_TEMPLATE_TABLE}` WHERE `ID` BETWEEN {lo} AND {hi};",
    ]


def _resolve(snapshot: Snapshot | None) -> Snapshot:
    return snapshot if snapshot is not None else load_snapshot()


def render_install(
    result: TotemQuestResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    snap = _resolve(snapshot)
    qt = snap.schema(QUEST_TEMPLATE_TABLE)
    qta = snap.schema(QUEST_TEMPLATE_ADDON_TABLE)
    qor = snap.schema(QUEST_OFFER_REWARD_TABLE)
    starter = snap.schema(CREATURE_QUESTSTARTER_TABLE)
    ender = snap.schema(CREATURE_QUESTENDER_TABLE)

    lines = [
        "-- mod-uac: level-4 Earth Totem access for displaced shaman races (Call of Earth).",
        "-- Two zero-objective quests reward item 5175 (Earth Totem) from the mod-uac shaman",
        "-- starter trainers; the Draenei vanilla chain is re-narrowed so every race has exactly",
        "-- one Earth-Totem path (mask partition: 77 + 528 + 130 + 32 + 1024 = 1791).",
        "",
        "-- Idempotent: clear the reserved quest band before re-inserting.",
        *_reserved_band_deletes(),
        "",
    ]

    for quest in EARTH_ACCESS_QUESTS:
        quest_id = result.quest_ids[quest.faction]
        entry = result.trainer_entries[quest.faction]
        lines.append(
            f"-- {quest.faction}: quest {quest_id}, AllowableRaces {quest.allowable_races}, "
            f"trainer entry {entry}"
        )
        lines.append(render_insert(QUEST_TEMPLATE_TABLE, qt, _quest_template_row(quest, quest_id)))
        lines.append(
            render_insert(
                QUEST_TEMPLATE_ADDON_TABLE,
                qta,
                {"ID": quest_id, "AllowableClasses": SHAMAN_CLASSMASK},
            )
        )
        lines.append(
            render_insert(
                QUEST_OFFER_REWARD_TABLE,
                qor,
                {"ID": quest_id, "RewardText": quest.reward_text},
            )
        )
        lines.append(
            render_insert(CREATURE_QUESTSTARTER_TABLE, starter, {"id": entry, "quest": quest_id})
        )
        lines.append(
            render_insert(CREATURE_QUESTENDER_TABLE, ender, {"id": entry, "quest": quest_id})
        )
        lines.append("")

    lines.append("-- Reset the vanilla Call of Earth chains to native races (authoritative).")
    for quest_id, _stock, native in EARTH_CHAIN_RENARROW:
        lines.append(
            render_update(
                QUEST_TEMPLATE_TABLE, qt, {"AllowableRaces": native}, {"ID": quest_id}
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_uninstall(
    result: TotemQuestResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    snap = _resolve(snapshot)
    qt = snap.schema(QUEST_TEMPLATE_TABLE)
    lines = [
        "-- mod-uac: revert synthetic Call of Earth quests and Draenei chain re-narrow.",
        "",
        *_reserved_band_deletes(),
        "",
        "-- Restore the vanilla Call of Earth chains to their stock masks.",
    ]
    for quest_id, stock, _native in EARTH_CHAIN_RENARROW:
        lines.append(
            render_update(
                QUEST_TEMPLATE_TABLE, qt, {"AllowableRaces": stock}, {"ID": quest_id}
            )
        )
    lines.append("")
    return "\n".join(lines)


@dataclass(slots=True)
class TotemQuestEmitter:
    snapshot: Snapshot | None = None
    matrix: ComboMatrix | None = None
    overrides_path: Path | None = DEFAULT_TRAINER_OVERRIDES_PATH

    def compute(self) -> TotemQuestResult:
        snapshot = self.snapshot or load_snapshot()
        matrix = self.matrix or ComboMatrix.stock()
        overrides = load_trainer_overrides(self.overrides_path)
        trainer_rows = compute_trainer_rows(snapshot, matrix, overrides=overrides).rows
        return compute_totem_quests(trainer_rows, snapshot)

    def render_install(self, result: TotemQuestResult | None = None) -> str:
        snapshot = self.snapshot or load_snapshot()
        return render_install(result or self.compute(), snapshot=snapshot)

    def render_uninstall(self, result: TotemQuestResult | None = None) -> str:
        snapshot = self.snapshot or load_snapshot()
        return render_uninstall(result or self.compute(), snapshot=snapshot)
