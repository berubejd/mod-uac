"""Stock class-quest chains used as references for new combos (Phase 1g)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WARRIOR_CLASS_ID = 1
PALADIN_CLASS_ID = 2
HUNTER_CLASS_ID = 3
SHAMAN_CLASS_ID = 7
WARLOCK_CLASS_ID = 9
DRUID_CLASS_ID = 11

# Summon Imp (688) — reward spell on imp-completion quests in stock AC.
SUMMON_IMP_SPELL_ID = 688

# Hunter pet kit (stock level-10 quest chain rewards via spells 1579 / 5300).
HUNTER_PET_SPELL_IDS: tuple[int, ...] = (
    1515,  # Tame Beast
    883,  # Call Pet
    2641,  # Dismiss Pet
    6991,  # Feed Pet
    982,  # Revive Pet
)

# Playable-race bitmasks for faction-wide quest unlock (§8.3).
ALLIANCE_FACTION_MASK = 1 + 4 + 8 + 64 + 1024  # 1101
HORDE_FACTION_MASK = 2 + 16 + 32 + 128 + 512  # 690

FactionName = Literal["alliance", "horde"]


@dataclass(frozen=True, slots=True)
class QuestRaceGate:
    quest_id: int
    zone_id: int
    stock_allowable_races: int
    stock_max_level: int = 0  # quest_template_addon.MaxLevel; 0 = no cap in stock AC


@dataclass(frozen=True, slots=True)
class ClassQuestChain:
    class_id: int
    reference_race_id: int
    primary_zone_id: int
    reward_spell_id: int
    quests: tuple[QuestRaceGate, ...]


@dataclass(frozen=True, slots=True)
class FactionQuestChain:
    """Reference chain opened to the entire faction (§8.3 travel-gated classes)."""

    class_id: int
    faction: FactionName
    label: str
    quests: tuple[QuestRaceGate, ...]


# Introductory letter/memorandum quests precede the imp reward quest in each chain.
WARLOCK_CHAINS: tuple[ClassQuestChain, ...] = (
    ClassQuestChain(
        class_id=WARLOCK_CLASS_ID,
        reference_race_id=1,
        primary_zone_id=12,
        reward_spell_id=SUMMON_IMP_SPELL_ID,
        quests=(
            QuestRaceGate(3105, 12, 1),
            QuestRaceGate(1598, 12, 1),
        ),
    ),
    ClassQuestChain(
        class_id=WARLOCK_CLASS_ID,
        reference_race_id=7,
        primary_zone_id=1,
        reward_spell_id=SUMMON_IMP_SPELL_ID,
        quests=(
            QuestRaceGate(3115, 1, 64),
            QuestRaceGate(1599, 1, 64),
        ),
    ),
    ClassQuestChain(
        class_id=WARLOCK_CLASS_ID,
        reference_race_id=5,
        primary_zone_id=85,
        reward_spell_id=SUMMON_IMP_SPELL_ID,
        quests=(QuestRaceGate(1470, 85, 690),),
    ),
    ClassQuestChain(
        class_id=WARLOCK_CLASS_ID,
        reference_race_id=2,
        primary_zone_id=14,
        reward_spell_id=SUMMON_IMP_SPELL_ID,
        quests=(QuestRaceGate(1485, 14, 690),),
    ),
    ClassQuestChain(
        class_id=WARLOCK_CLASS_ID,
        reference_race_id=10,
        primary_zone_id=3430,
        reward_spell_id=SUMMON_IMP_SPELL_ID,
        quests=(QuestRaceGate(8344, 3430, 690),),
    ),
)

# Hunter pet taming (level 10+) — catalogued for optional HunterPetEmitter slice.
HUNTER_CHAINS: tuple[ClassQuestChain, ...] = (
    ClassQuestChain(
        class_id=HUNTER_CLASS_ID,
        reference_race_id=3,
        primary_zone_id=1,
        reward_spell_id=1515,
        quests=(
            QuestRaceGate(6064, 1, 4),
            QuestRaceGate(6084, 1, 4),
            QuestRaceGate(6085, 1, 4),
        ),
    ),
)

# §8.3 — faction-wide AllowableRaces unlock for travel-gated class abilities.
# Horde warrior stance chain is already mask 690 in stock AC; only alliance gaps below.
FACTION_UNLOCK_CHAINS: tuple[FactionQuestChain, ...] = (
    FactionQuestChain(
        class_id=WARRIOR_CLASS_ID,
        faction="alliance",
        label="warrior Defensive Stance (Ironforge)",
        quests=(
            QuestRaceGate(1678, 1, 68),
            QuestRaceGate(1679, 1, 68),
        ),
    ),
    FactionQuestChain(
        class_id=SHAMAN_CLASS_ID,
        faction="horde",
        label="shaman Call of Earth (Durotar)",
        quests=(
            QuestRaceGate(1516, 14, 130),
            QuestRaceGate(1517, 14, 130),
            QuestRaceGate(1518, 14, 130),
        ),
    ),
    FactionQuestChain(
        class_id=SHAMAN_CLASS_ID,
        faction="horde",
        label="shaman Call of Earth (Mulgore)",
        quests=(
            QuestRaceGate(1519, 215, 32),
            QuestRaceGate(1520, 215, 32),
            QuestRaceGate(1521, 215, 32),
        ),
    ),
    # Call of Water (level 20) and Call of Air (level 30) exist only as the
    # Draenei chain on the Alliance side (mask 1024) — there is no Eastern
    # Kingdoms equivalent. Stock Call of Fire is already 1101, so it needs no
    # patch. The open entry 9502 (mask 0) is a dead end because step 9501 and
    # every follow-up are Draenei-gated, so the whole chain body is unlocked.
    # Mainland Earthen Ring emissaries (Farseer Umbrua in Stormwind, Farseer
    # Javad) offer 10490/10491/9547; body + turn-ins are on Azuremyst (3524).
    FactionQuestChain(
        class_id=SHAMAN_CLASS_ID,
        faction="alliance",
        label="shaman Call of Water (Azuremyst)",
        quests=(
            QuestRaceGate(9500, 3524, 1024),
            QuestRaceGate(9501, 3524, 1024),
            QuestRaceGate(9503, 3524, 1024),
            QuestRaceGate(9504, 3524, 1024),
            QuestRaceGate(9508, 3524, 1024),
            QuestRaceGate(9509, 3524, 1024),
            QuestRaceGate(10490, 1519, 1024),
        ),
    ),
    FactionQuestChain(
        class_id=SHAMAN_CLASS_ID,
        faction="alliance",
        label="shaman Call of Air (Azuremyst)",
        quests=(
            QuestRaceGate(9547, 3524, 1024),
            QuestRaceGate(9551, 3524, 1024),
            QuestRaceGate(9552, 3524, 1024),
            QuestRaceGate(9553, 3524, 1024),
            QuestRaceGate(9554, 3524, 1024),
            QuestRaceGate(10491, 1519, 1024),
        ),
    ),
    FactionQuestChain(
        class_id=DRUID_CLASS_ID,
        faction="alliance",
        label="druid bear form (Teldrassil)",
        quests=(
            QuestRaceGate(5921, 141, 8),
            QuestRaceGate(5929, 493, 8),
            QuestRaceGate(5931, 493, 8),
            QuestRaceGate(6001, 141, 8),
        ),
    ),
    FactionQuestChain(
        class_id=DRUID_CLASS_ID,
        faction="horde",
        label="druid bear form (Mulgore)",
        quests=(
            QuestRaceGate(5922, 215, 32),
            QuestRaceGate(5930, 493, 32),
            QuestRaceGate(5932, 493, 32),
            QuestRaceGate(6002, 215, 32),
        ),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="alliance",
        label="paladin Redemption (Stormwind)",
        quests=(
            QuestRaceGate(1642, 12, 1),
            QuestRaceGate(1643, 12, 1),
            QuestRaceGate(1644, 12, 1),
            QuestRaceGate(1780, 12, 1),
            QuestRaceGate(1781, 12, 1),
            QuestRaceGate(1786, 12, 1),
            QuestRaceGate(1787, 12, 1),
            QuestRaceGate(1788, 12, 1),
        ),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="alliance",
        label="paladin Redemption (Ironforge)",
        quests=(
            QuestRaceGate(1646, 1, 4),
            QuestRaceGate(1647, 1, 4),
            QuestRaceGate(1648, 1, 4),
            QuestRaceGate(1778, 1, 4),
            QuestRaceGate(1779, 1, 4),
            QuestRaceGate(1783, 1, 4),
            QuestRaceGate(1784, 1, 4),
            QuestRaceGate(1785, 1, 4),
        ),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="alliance",
        label="paladin Redemption (Azuremyst)",
        quests=(
            QuestRaceGate(9598, 3524, 1024),
            QuestRaceGate(9600, 3524, 1024),
        ),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="horde",
        label="paladin Redemption (Eversong)",
        quests=(
            QuestRaceGate(9676, 3430, 512),
            QuestRaceGate(9677, 3430, 512),
            QuestRaceGate(9678, 3430, 512),
            QuestRaceGate(9684, 3430, 512),
            QuestRaceGate(9685, 3430, 512),
        ),
    ),
    # DB-verified full audit of paladin-only class quests (AllowableClasses=2):
    # every narrow-gated chain below blocks new combos (Alliance: NE/Gnome;
    # Horde: Orc/Undead/Tauren/Troll). We open the whole chain body to the
    # faction so new combos can *do* the quest, even where the reward (mount,
    # Redemption spell) is also trainable in 3.3.5 — the opportunity is the
    # point. Excluded: quest 9287 (Draenei "Paladin Training"), hard-blocked
    # behind the Draenei-only non-class prereq 9280, so unlocking is futile.
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="alliance",
        label="paladin Tome of Divinity (Stormwind/Human)",
        quests=(
            QuestRaceGate(3101, 12, 1),  # Consecrated Letter (Northshire)
            QuestRaceGate(1641, 1519, 1),
            QuestRaceGate(1790, 1519, 1),  # The Symbol of Life
            QuestRaceGate(2998, 1519, 1),
            QuestRaceGate(3681, 1519, 1),
        ),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="alliance",
        label="paladin Tome of Divinity (Ironforge/Dwarf)",
        quests=(
            QuestRaceGate(3107, 1, 4),  # Consecrated Rune (Kharanos)
            QuestRaceGate(1645, 1537, 4),
            QuestRaceGate(1789, 1537, 4),  # The Symbol of Life
            QuestRaceGate(2997, 1537, 4),
            QuestRaceGate(2999, 1537, 4),
            QuestRaceGate(3000, 1537, 4),
        ),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="alliance",
        label="paladin Redemption root (Azuremyst/Draenei)",
        quests=(QuestRaceGate(10366, 3524, 1024),),  # Jol -> 9598 (catalogued)
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="alliance",
        label="paladin Charger epic mount (level 60)",
        quests=(
            QuestRaceGate(7637, 1519, 1029),
            QuestRaceGate(7638, 1519, 1029),
            QuestRaceGate(7639, 1519, 1029),
            QuestRaceGate(7640, 1519, 1029),
            QuestRaceGate(7641, 1519, 1029),
            QuestRaceGate(7642, 1519, 1029),
            QuestRaceGate(7643, 1519, 1029),
            QuestRaceGate(7644, 1519, 1029),
            QuestRaceGate(7645, 1519, 1029),
            QuestRaceGate(7646, 1519, 1029),
            QuestRaceGate(7647, 1519, 1029),
            QuestRaceGate(7670, 1519, 1029),
        ),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="horde",
        label="paladin Blood Knight trials + weapon (Silvermoon)",
        quests=(
            QuestRaceGate(10069, 3487, 512),  # Well Watcher Solanian
            QuestRaceGate(9681, 3487, 512),  # A Study in Power (L12)
            QuestRaceGate(9686, 3487, 512),  # The Second Trial (L20)
            QuestRaceGate(9690, 3487, 512),
            QuestRaceGate(9691, 3487, 512),
            QuestRaceGate(9692, 3487, 512),
            QuestRaceGate(9707, 3487, 512),
            QuestRaceGate(9710, 3487, 512),  # The Blood-Tempered Ranseur
        ),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="horde",
        label="paladin Thalassian Warhorse (level 40)",
        quests=(QuestRaceGate(9712, 3487, 512),),
    ),
    FactionQuestChain(
        class_id=PALADIN_CLASS_ID,
        faction="horde",
        label="paladin Blood Knight charger (level 60)",
        quests=(
            QuestRaceGate(9721, 3487, 512),
            QuestRaceGate(9722, 3487, 512),
            QuestRaceGate(9723, 3487, 512),
            QuestRaceGate(9735, 3487, 512),
            QuestRaceGate(9736, 3487, 512),
            QuestRaceGate(9737, 3487, 512),
        ),
    ),
)

CLASS_CHAINS_BY_ID: dict[int, tuple[ClassQuestChain, ...]] = {
    WARLOCK_CLASS_ID: WARLOCK_CHAINS,
    HUNTER_CLASS_ID: HUNTER_CHAINS,
}

# Per-combo tier resolution (warlock imp only in Phase 1g).
EMITTED_CLASS_CHAINS: dict[int, tuple[ClassQuestChain, ...]] = {
    WARLOCK_CLASS_ID: WARLOCK_CHAINS,
}
