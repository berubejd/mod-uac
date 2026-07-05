#!/usr/bin/env python3
"""Generate operator-specific mod-uac SQL from local DBC files."""

from __future__ import annotations

import argparse
from pathlib import Path

from aracgen.cli import write_player_create_sql, write_skill_overlay_sql
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
    args = parser.parse_args()

    source = LocalDbcSource(args.dbc_dir)
    install_path = args.output_dir / "mod_uac_skillraceclassinfo_dbc.sql"
    uninstall_path = args.output_dir / "mod_uac_skillraceclassinfo_dbc_uninstall.sql"

    write_skill_overlay_sql(
        source,
        install_path,
        uninstall_path,
        db_max_id=args.db_max_id,
    )
    write_player_create_sql(source, args.output_dir, args.output_dir)


if __name__ == "__main__":
    main()
