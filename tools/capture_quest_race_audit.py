"""Capture live quest race gates read-only, without exporting DB credentials."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from aracgen.snapshot import _connect, capture_table_schema
from aracgen.snapshot_dsn import resolve_world_database_info

QUERIES = {
    'quests': '''SELECT q.ID,q.LogTitle,q.QuestSortID,q.AllowableRaces,q.MinLevel,
        q.StartItem,q.RewardNextQuest,q.RequiredItemId1,q.RequiredItemId2,
        q.RequiredItemId3,q.RequiredItemId4,q.RequiredItemId5,q.RequiredItemId6,
        q.RewardItem1,q.RewardItem2,q.RewardItem3,q.RewardItem4,
        q.RewardChoiceItemID1,q.RewardChoiceItemID2,q.RewardChoiceItemID3,
        q.RewardChoiceItemID4,q.RewardChoiceItemID5,q.RewardChoiceItemID6,
        a.AllowableClasses,a.PrevQuestID,a.NextQuestID,a.BreadcrumbForQuestId
        FROM quest_template q LEFT JOIN quest_template_addon a ON a.ID=q.ID
        ORDER BY q.ID''',
    'conditions': 'SELECT * FROM conditions',
    'items': '''SELECT entry,name,AllowableRace,startquest FROM item_template
        WHERE AllowableRace NOT IN (-1,0,2147483647,4294967295)
        OR startquest<>0 ORDER BY entry''',
    'spell_areas': 'SELECT * FROM spell_area WHERE racemask<>0 ORDER BY spell,area',
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    dsn = resolve_world_database_info(config_path=args.config)
    connection = _connect(dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SET SESSION TRANSACTION READ ONLY')
            cursor.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT')
            data = {'captured_at': datetime.now(UTC).isoformat(), 'database': dsn.database}
            for name, query in QUERIES.items():
                cursor.execute(query)
                data[name] = cursor.fetchall()
        schema = capture_table_schema(connection, dsn.database, 'quest_template')
        data['schemas'] = {'quest_template': schema.to_json()}
    finally:
        connection.rollback()
        connection.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
    print(f"Captured {len(data['quests'])} quests and their condition/item/area gates")


if __name__ == '__main__':
    main()
