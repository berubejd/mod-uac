"""Generate install/revert SQL from an operator's captured class-quest audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aracgen.quest_race_audit import compute_race_fixes, render_race_sql
from aracgen.snapshot_model import TableSchema


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.audit.read_text(encoding='utf8'))
    schema = TableSchema.from_json(data['schemas']['quest_template'])
    result = compute_race_fixes(data)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'class-quest-race-report.json').write_text(
        json.dumps(result.to_json(), ensure_ascii=False, indent=2), encoding='utf8',
    )
    for uninstall in (False, True):
        directory = args.output / ('db-uninstall' if uninstall else 'db-world')
        directory.mkdir(exist_ok=True)
        suffix = '_uninstall' if uninstall else ''
        (directory / f'zz_mod_uac_class_quest_races{suffix}.sql').write_text(
            render_race_sql(result, schema, uninstall=uninstall), encoding='utf8',
        )
    print(f'{len(result.class_quest_ids)} class quests audited; '
          f'{len(result.patches)} race gates widened')


if __name__ == '__main__':
    main()
