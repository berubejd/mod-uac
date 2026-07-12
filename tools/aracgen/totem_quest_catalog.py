"""Synthetic Earth Totem access quests for displaced shaman races (Call of Earth).

The vanilla Call of Earth chains are anchored to their starting zones by
intermediate questgiver/ender NPCs (Spirit of the Vale in Ammen Vale, Minor
Manifestation of Earth in Valley of Trials / Camp Narache). Opening
``AllowableRaces`` faction-wide cannot fix that: a displaced shaman can accept
the quest but dead-ends at a step whose NPC never spawns in their zone. They
reach level 4, learn Stoneskin Totem, but never receive item 5175 (Earth Totem)
-- a TotemCategory 2 reagent required to cast it.

The fix is two zero-objective "Call of Earth" quests attached to the shaman
trainers mod-uac already places in the displaced starter zones. Each rewards
item 5175 and is completable at the same NPC. The vanilla chains are re-narrowed
to their native races so every race is covered by exactly one Earth-Totem path
(mask partition sums to 1791, no overlap -> no duplicate NO_USER_DESTROY totem).
"""

from __future__ import annotations

from dataclasses import dataclass

SHAMAN_CLASS_ID = 7
SHAMAN_CLASSMASK = 64  # CLASSMASK_SHAMAN (quest_template_addon.AllowableClasses)

EARTH_TOTEM_ITEM_ID = (
    5175  # Earth Totem; TotemCategory 2 reagent, Flags 32 (NO_USER_DESTROY)
)

# Presentation fields lifted from the stock Draenei Call of Earth chain so the
# synthetic quests sort and scale identically (verified against the world DB):
#   QuestSortID -82 (shaman class sort), RewardXPDifficulty 6 (quest 9451).
EARTH_QUEST_SORT_ID = -82
EARTH_QUEST_INFO_ID = 0
EARTH_QUEST_LEVEL = 4
EARTH_QUEST_MIN_LEVEL = 4
EARTH_QUEST_XP_DIFFICULTY = 6

# QuestType 2 (normal) with zero objectives completes on accept + turn-in at the
# same NPC. If in-game QA shows it does not auto-complete, flip to 0
# (QUEST_TYPE_AUTOCOMPLETE) -- a single-constant change.
EARTH_QUEST_TYPE = 2


@dataclass(frozen=True, slots=True)
class SyntheticTotemQuest:
    """A zero-objective Earth Totem access quest for one faction's displaced races."""

    faction: str  # "alliance" | "horde"
    allowable_races: int
    log_title: str
    log_description: str
    quest_description: str
    quest_completion_log: str
    reward_text: str


# allowable_races partition (must sum with the re-narrowed vanilla chains to
# 1791 = all ten races, no overlap):
#   alliance 77  = 1 + 4 + 8 + 64      Human, Dwarf, Night Elf, Gnome
#   horde    528 = 16 + 512            Undead, Blood Elf
EARTH_ACCESS_QUESTS: tuple[SyntheticTotemQuest, ...] = (
    SyntheticTotemQuest(
        faction="alliance",
        allowable_races=77,
        log_title="Call of Earth",
        log_description="Commune with the earth at Firmanvaar's side.",
        quest_description=(
            "You were not born to this, and so you believe the earth is a stranger to you. "
            "It is not. It has simply been waiting to be addressed.\n\n"
            "My own people crossed the Great Dark to arrive here, and still the stone of this "
            "world knew us. Do you imagine it will refuse you, who were born of it?\n\n"
            "Set down your weapon. Put your hands flat upon the ground and stop speaking. The "
            "earth has no use for petition. It wishes only to be acknowledged."
        ),
        quest_completion_log="The earth has answered.",
        reward_text=(
            "It heard you. I saw the moment it did... you did not, but I did.\n\n"
            "Carry this. It is not a weapon and it is not a charm. It is a place for the earth "
            "to stand when you call it, and it will not answer without one."
        ),
    ),
    SyntheticTotemQuest(
        faction="horde",
        allowable_races=528,
        log_title="Call of Earth",
        log_description="Commune with the earth at Meela Dawnstrider's side.",
        quest_description=(
            "I have walked a long way from Mulgore to stand in this place, $N, and I will tell "
            "you what I told myself on the road: the earth does not keep the borders that we "
            "do.\n\n"
            "When I was taught, my elders sent me into the hills to search out the earth's "
            "voice. You will not walk so far. The stone beneath us is older than every grievance "
            "buried in it, and it is already listening.\n\n"
            "Kneel. Lay your hand against the ground. Ask it for nothing. Only let it know that "
            "you have come."
        ),
        quest_completion_log="The earth has answered.",
        reward_text=(
            "There. You felt that, and you did not expect to.\n\n"
            "Take this totem. It is not the source of your power... you are. It is only the "
            "ground the earth needs beneath it before it will rise for you."
        ),
    ),
)

# Vanilla Call of Earth chains reset to native races so displaced shamans use
# the synthetic quests above instead of dead-ending here, and so the ten races
# partition cleanly (no duplicate NO_USER_DESTROY totem). The Orc/Troll (130)
# and Tauren (32) resets equal stock -- they are emitted authoritatively anyway
# so an install over a prior faction-wide (690) mod-uac state self-corrects.
# The Draenei chain is a genuine narrow (stock 1101 -> 1024).
#   (quest_id, stock_allowable_races, native_allowable_races)
EARTH_CHAIN_RENARROW: tuple[tuple[int, int, int], ...] = (
    (1516, 130, 130),  # Orc + Troll (Valley of Trials)
    (1517, 130, 130),
    (1518, 130, 130),
    (1519, 32, 32),  # Tauren (Camp Narache)
    (1520, 32, 32),
    (1521, 32, 32),
    (9449, 1101, 1024),  # Draenei (Ammen Vale) -- genuine narrow
    (9450, 1101, 1024),
    (9451, 1101, 1024),
)
