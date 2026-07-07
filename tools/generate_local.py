#!/usr/bin/env python3
"""Generate operator-specific mod-uac SQL from local DBC files."""

from __future__ import annotations

import argparse
from pathlib import Path

from aracgen.cli import (
    add_snapshot_cli_args,
    add_trainer_cli_args,
    resolve_generation_snapshot,
    write_class_quest_sql,
    write_client_patch,
    write_hunter_pet_sql,
    write_player_create_sql,
    write_skill_overlay_sql,
    write_totem_sql,
    write_trainer_sql,
)
from aracgen.sources import LocalDbcSource

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate operator-specific mod-uac SQL from your WoW Data/dbc/ "
            "or other local DBC baseline"
        ),
    )
    parser.add_argument(
        "dbc_dir",
        type=Path,
        help="Path to dbc/ directory (e.g. your server's Data/dbc/)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for generated SQL (default: tools/output/)",
    )
    parser.add_argument(
        "--db-max-id",
        type=int,
        default=0,
        help="MAX(ID) from SELECT MAX(ID) FROM skillraceclassinfo_dbc on your world DB",
    )
    parser.add_argument(
        "--outfit-db-max-id",
        type=int,
        default=0,
        help="MAX(ID) from SELECT MAX(ID) FROM charstartoutfit_dbc on your world DB",
    )
    add_snapshot_cli_args(parser)
    add_trainer_cli_args(parser)
    args = parser.parse_args()

    source = LocalDbcSource(args.dbc_dir)
    snapshot = resolve_generation_snapshot(args)
    install_path = args.output_dir / "mod_uac_skillraceclassinfo_dbc.sql"
    uninstall_path = args.output_dir / "mod_uac_skillraceclassinfo_dbc_uninstall.sql"

    write_skill_overlay_sql(
        source,
        install_path,
        uninstall_path,
        db_max_id=args.db_max_id,
        snapshot=snapshot,
    )
    write_player_create_sql(source, args.output_dir, args.output_dir, db_max_outfit_id=args.outfit_db_max_id)
    write_totem_sql(
        args.output_dir / "mod_uac_player_totem_model.sql",
        args.output_dir / "mod_uac_player_totem_model_uninstall.sql",
    )
    write_class_quest_sql(args.output_dir, args.output_dir)
    write_hunter_pet_sql(
        args.output_dir,
        args.output_dir,
        dbc_source=args.dbc_dir / "Spell.dbc",
    )
    write_client_patch(args.output_dir / "patch-A.mpq")

    write_trainer_sql(
        args.output_dir / "mod_uac_starter_trainers.sql",
        args.output_dir / "mod_uac_starter_trainers_uninstall.sql",
        args.output_dir / "trainer_worksheet.md",
        snapshot=snapshot,
        overrides_path=args.trainer_overrides,
        guid_base=args.trainer_guid_base,
    )


if __name__ == "__main__":
    main()
