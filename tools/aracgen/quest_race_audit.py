"""Snapshot-driven, faction-preserving fixes for off-race class quest access.

Unlike the small reference-chain catalog, this pass examines every class quest
in the operator's world. It changes race masks only, never class, level, phase,
prerequisite, reputation or skill requirements. New condition/item blockers are
reported as a generation failure instead of being indiscriminately removed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from aracgen.class_quest_catalog import ALLIANCE_FACTION_MASK, HORDE_FACTION_MASK
from aracgen.schema_emit import render_update
from aracgen.snapshot_model import MOD_UAC_QUEST_ID_MAX, MOD_UAC_QUEST_ID_MIN, TableSchema
from aracgen.totem_quest_catalog import EARTH_CHAIN_RENARROW

# SharedDefines.h ClassByQuestSort; DK already supports every playable race and
# its A Special Surprise variants deliberately identify the player's own race.
CLASS_SORTS = frozenset((-61, -81, -82, -141, -161, -162, -261, -262, -263))
CLASS_MASKS = frozenset((1, 2, 4, 8, 16, 64, 128, 256, 1024))
ALL_RACES = ALLIANCE_FACTION_MASK | HORDE_FACTION_MASK
EARTH_QUEST_IDS = frozenset(row[0] for row in EARTH_CHAIN_RENARROW)


@dataclass(frozen=True, slots=True)
class RaceFix:
    quest_id: int
    title: str
    before: int
    after: int
    reason: str


@dataclass(frozen=True, slots=True)
class RaceAudit:
    patches: tuple[RaceFix, ...]
    preserved: tuple[dict[str, Any], ...]
    blockers: dict[str, list[dict[str, Any]]]
    class_quest_ids: frozenset[int]

    def to_json(self) -> dict[str, Any]:
        return {
            'patches': [asdict(patch) for patch in self.patches],
            'preserved': list(self.preserved),
            'blockers': self.blockers,
            'class_quest_count': len(self.class_quest_ids),
        }


def expand_faction_mask(mask: int) -> int:
    if not mask:
        return mask
    result = mask
    if mask & ALLIANCE_FACTION_MASK:
        result |= ALLIANCE_FACTION_MASK
    if mask & HORDE_FACTION_MASK:
        result |= HORDE_FACTION_MASK
    return result


def _preserved_reason(row: dict[str, Any]) -> str | None:
    quest_id = int(row['ID'])
    if (row.get('AllowableClasses') or 0) == 32 or row['QuestSortID'] == -372:
        return 'Death Knight racial story variant; no new DK race combinations'
    if quest_id in EARTH_QUEST_IDS or MOD_UAC_QUEST_ID_MIN <= quest_id <= MOD_UAC_QUEST_ID_MAX:
        return 'Existing mod-uac Earth Totem paths partition native/displaced races'
    return None


def compute_race_fixes(data: dict[str, Any]) -> RaceAudit:
    quests = {int(row['ID']): row for row in data['quests']}
    class_ids = {
        quest_id for quest_id, row in quests.items()
        if (row.get('AllowableClasses') or 0) in CLASS_MASKS or row['QuestSortID'] in CLASS_SORTS
    }
    preserved = []
    # Reward/story chains such as Quel'Delar have a one-class exception next to
    # a multi-class racial variant. A single class mask alone does not turn
    # those into class quests; keep their mutually exclusive racial identity.
    mixed_class_variants = {
        (row['LogTitle'], row['QuestSortID']) for row in quests.values()
        if (row.get('AllowableClasses') or 0) not in (*CLASS_MASKS, 0, 1535, 1503, 32)
        and row['QuestSortID'] not in CLASS_SORTS
    }
    for quest_id, row in sorted(quests.items()):
        reason = _preserved_reason(row)
        if (row['LogTitle'], row['QuestSortID']) in mixed_class_variants:
            reason = 'Racial story/reward variant rather than a class quest'
        if reason:
            races = row['AllowableRaces']
            if races and expand_faction_mask(races) != races:
                preserved.append({'quest_id': quest_id, 'reason': reason})
            class_ids.discard(quest_id)

    # A few class-introduction quests depend on a generic racial starter quest.
    # Open the prerequisite's faction gate too; do not delete the dependency.
    candidate_ids = set(class_ids)
    pending = list(class_ids)
    while pending:
        row = quests[pending.pop()]
        previous = int(row.get('PrevQuestID') or 0)
        if previous > 0 and previous in quests and previous not in candidate_ids:
            if not _preserved_reason(quests[previous]):
                candidate_ids.add(previous)
                pending.append(previous)

    patches = []
    for quest_id in sorted(candidate_ids):
        row = quests[quest_id]
        before = int(row['AllowableRaces'])
        after = expand_faction_mask(before)
        if before != after:
            patches.append(RaceFix(
                quest_id, str(row['LogTitle']), before, after,
                'class quest' if quest_id in class_ids else 'class-quest prerequisite',
            ))

    blockers: dict[str, list[dict[str, Any]]] = {
        'quest_race_conditions': [], 'quest_race_items': [], 'quest_race_spell_areas': [],
    }
    conditions = data.get('conditions', [])
    relevant = [c for c in conditions if c['SourceTypeOrReferenceId'] == 19
                and c['SourceEntry'] in candidate_ids]
    references: set[int] = set()
    for condition in relevant:
        if condition['ConditionTypeOrReference'] < 0:
            references.add(condition['ConditionTypeOrReference'])
    visited: set[int] = set()
    while references - visited:
        ref = min(references - visited)
        visited.add(ref)
        rows = [c for c in conditions if c['SourceTypeOrReferenceId'] == ref]
        relevant.extend(rows)
        references.update(c['ConditionTypeOrReference'] for c in rows
                          if c['ConditionTypeOrReference'] < 0)
    blockers['quest_race_conditions'] = [c for c in relevant
                                        if c['ConditionTypeOrReference'] == 16
                                        and expand_faction_mask(c['ConditionValue1'])
                                        != c['ConditionValue1']]

    item_ids = {
        value for quest_id in candidate_ids for key, value in quests[quest_id].items()
        if key == 'StartItem'
        or key.startswith(('RequiredItemId', 'RewardItem', 'RewardChoiceItemID'))
    }
    for item in data.get('items', []):
        if item['entry'] in item_ids or item.get('startquest') in candidate_ids:
            mask = int(item['AllowableRace'])
            if mask > 0 and expand_faction_mask(mask) != mask:
                blockers['quest_race_items'].append(item)
    blockers['quest_race_spell_areas'] = [
        area for area in data.get('spell_areas', [])
        if (area['quest_start'] in candidate_ids or area['quest_end'] in candidate_ids)
        and expand_faction_mask(area['racemask']) != area['racemask']
    ]
    return RaceAudit(tuple(patches), tuple(preserved), blockers, frozenset(class_ids))


def render_race_sql(result: RaceAudit, schema: TableSchema, *, uninstall: bool = False) -> str:
    if any(result.blockers.values()):
        raise ValueError('Unresolved race blockers in class quest conditions/items/spell areas')
    lines = [
        '-- mod-uac: snapshot-driven class quest race access audit',
        '-- Generated; preserve class, level, prerequisite and progression restrictions.',
        '-- Earth Totem route partitions and DK racial story variants are intentional.',
        '',
    ]
    for patch in result.patches:
        old, new = (patch.after, patch.before) if uninstall else (patch.before, patch.after)
        # Guard against overwriting operator changes made after this snapshot.
        lines.append(f'-- quest {patch.quest_id}: {patch.reason} ({old} -> {new})')
        lines.append(render_update(
            'quest_template', schema, {'AllowableRaces': new},
            {'ID': patch.quest_id, 'AllowableRaces': old},
        ))
    return '\n'.join([*lines, ''])
