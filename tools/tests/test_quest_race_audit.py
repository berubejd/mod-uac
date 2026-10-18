from __future__ import annotations

from aracgen.quest_race_audit import compute_race_fixes, expand_faction_mask, render_race_sql
from aracgen.snapshot import load_snapshot


def quest(quest_id=6064, races=4, classes=4, sort=-261, **extra):
    return {
        'ID': quest_id, 'LogTitle': 'Taming the Beast', 'AllowableRaces': races,
        'AllowableClasses': classes, 'QuestSortID': sort, 'MinLevel': 10,
        'PrevQuestID': 0, **extra,
    }


def audit(*quests):
    return {'quests': list(quests), 'conditions': [], 'items': [], 'spell_areas': []}


def test_hunter_complete_chain_is_opened_without_changing_levels_or_prerequisites():
    rows = [quest(i, PrevQuestID=prev) for i, prev in (
        (6064, 0), (6084, 6064), (6085, 6084), (6086, 6085),
    )]
    result = compute_race_fixes(audit(*rows))
    assert {p.quest_id for p in result.patches} == {6064, 6084, 6085, 6086}
    assert all(p.before == 4 and p.after == 1101 for p in result.patches)
    assert rows[1]['MinLevel'] == 10 and rows[1]['PrevQuestID'] == 6064


def test_faction_boundaries_and_unrestricted_quests_are_preserved():
    result = compute_race_fixes(audit(quest(1, 2), quest(2, 0), quest(3, 690)))
    assert [(p.quest_id, p.after) for p in result.patches] == [(1, 690)]


def test_non_class_racial_quests_and_queldelar_variants_are_not_widened():
    result = compute_race_fixes(audit(
        quest(1, classes=0, sort=12),
        quest(24594, races=512, classes=1519, sort=4075),
    ))
    assert not result.patches


def test_single_class_exception_in_racial_story_variant_is_preserved():
    result = compute_race_fixes(audit(
        quest(24594, races=512, classes=1519, sort=4075, LogTitle='QuelDelar'),
        quest(24596, races=512, classes=16, sort=4075, LogTitle='QuelDelar'),
    ))
    assert not result.patches


def test_racial_prerequisite_of_class_quest_is_opened_not_removed():
    result = compute_race_fixes(audit(
        quest(1, races=512, classes=4, PrevQuestID=2),
        quest(2, races=512, classes=0, sort=3431),
    ))
    assert len(result.patches) == 2
    assert result.patches[1].reason == 'class-quest prerequisite'


def test_single_class_quest_without_class_sort_is_included():
    result = compute_race_fixes(audit(quest(6721, races=8, sort=1537)))
    assert result.patches[0].after == 1101


def test_existing_earth_totem_partition_and_synthetic_routes_are_preserved():
    result = compute_race_fixes(audit(
        quest(1516, races=130, classes=64, sort=-82),
        quest(9451, races=1024, classes=64, sort=-82),
        quest(6000000, races=77, classes=64, sort=-82),
    ))
    assert not result.patches
    assert len(result.preserved) == 3


def test_death_knight_racial_story_variants_are_preserved():
    result = compute_race_fixes(audit(quest(12742, races=1, classes=32, sort=-372)))
    assert not result.patches


def test_mixed_faction_mask_retains_original_bits():
    assert expand_faction_mask(1 | 2) == 1791
    assert expand_faction_mask(4 | 4096) == 1101 | 4096
    assert expand_faction_mask(0) == 0


def test_full_faction_open_quests_are_not_emitted_again():
    assert not compute_race_fixes(audit(quest(races=1101))).patches


def test_sql_has_expected_before_guard_and_exact_inverse():
    result = compute_race_fixes(audit(quest()))
    schema = load_snapshot().schema('quest_template')
    install = render_race_sql(result, schema)
    rollback = render_race_sql(result, schema, uninstall=True)
    assert '`AllowableRaces` = 1101' in install
    assert '`ID` = 6064 AND `AllowableRaces` = 4' in install
    assert '`AllowableRaces` = 4' in rollback
    assert '`ID` = 6064 AND `AllowableRaces` = 1101' in rollback
    assert 'MinLevel' not in install and 'PrevQuestID' not in install


def test_race_conditions_on_class_quests_are_reported_not_silently_deleted():
    data = audit(quest())
    data['conditions'] = [{
        'SourceTypeOrReferenceId': 19, 'SourceEntry': 6064,
        'ConditionTypeOrReference': 16, 'ConditionValue1': 4,
    }]
    result = compute_race_fixes(data)
    assert result.blockers['quest_race_conditions']


def test_related_race_restricted_quest_items_are_reported():
    data = audit(quest(StartItem=123))
    data['items'] = [{'entry': 123, 'AllowableRace': 4, 'startquest': 0}]
    assert compute_race_fixes(data).blockers['quest_race_items']


def test_unrelated_mount_gossip_and_spell_areas_are_not_touched():
    data = audit(quest())
    data['conditions'] = [{
        'SourceTypeOrReferenceId': 15, 'SourceEntry': 0,
        'ConditionTypeOrReference': 16, 'ConditionValue1': 4,
    }]
    data['spell_areas'] = [{'quest_start': 123, 'quest_end': 0, 'racemask': 4}]
    result = compute_race_fixes(data)
    assert not any(result.blockers.values())
