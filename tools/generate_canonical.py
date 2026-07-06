#!/usr/bin/env python3
"""Generate checked-in mod-uac SQL from canonical wowgaming/client-data (v19)."""

from __future__ import annotations

import argparse
from pathlib import Path

from aracgen.cli import (
    write_class_quest_sql,
    write_client_patch,
    write_hunter_pet_sql,
    write_player_create_sql,
    write_skill_overlay_sql,
    write_totem_sql,
)
from aracgen.sources import DEFAULT_CANONICAL_PIN, CanonicalDbcSource, LocalDbcSource

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "cache"
INSTALL_DIR = REPO_ROOT / "data" / "sql" / "db-world"
UNINSTALL_DIR = REPO_ROOT / "data" / "sql" / "db-uninstall"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate checked-in mod-uac SQL from pinned wowgaming/client-data "
            f"({DEFAULT_CANONICAL_PIN})"
        ),
    )
    parser.add_argument(
        "--pin",
        default=DEFAULT_CANONICAL_PIN,
        help=f"wowgaming/client-data release tag (default: {DEFAULT_CANONICAL_PIN})",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Directory for downloaded client-data zip cache",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-download client data even if cached",
    )
    parser.add_argument(
        "--dbc-dir",
        type=Path,
        help="Offline override: read DBCs from this directory instead of downloading",
    )
    parser.add_argument(
        "--db-max-id",
        type=int,
        default=0,
        help="MAX(ID) already in skillraceclassinfo_dbc (default: 0 for stock DB)",
    )
    parser.add_argument(
        "--outfit-db-max-id",
        type=int,
        default=0,
        help="MAX(ID) already in charstartoutfit_dbc (default: 0 for stock DB)",
    )
    args = parser.parse_args()

    if args.dbc_dir is not None:
        source = LocalDbcSource(args.dbc_dir)
        hunter_dbc_source = args.dbc_dir / "Spell.dbc"
        print(f"Using local DBC override: {args.dbc_dir}")
    else:
        source = CanonicalDbcSource(
            pin=args.pin,
            cache_dir=args.cache_dir,
            refresh=args.refresh,
        )
        hunter_dbc_source = source.zip_path
        print(f"Using canonical client-data {args.pin}: {source.zip_path}")

    write_skill_overlay_sql(
        source,
        INSTALL_DIR / "mod_uac_skillraceclassinfo_dbc.sql",
        UNINSTALL_DIR / "mod_uac_skillraceclassinfo_dbc_uninstall.sql",
        db_max_id=args.db_max_id,
    )
    write_player_create_sql(
        source,
        INSTALL_DIR,
        UNINSTALL_DIR,
        db_max_outfit_id=args.outfit_db_max_id,
    )
    write_totem_sql(
        INSTALL_DIR / "mod_uac_player_totem_model.sql",
        UNINSTALL_DIR / "mod_uac_player_totem_model_uninstall.sql",
    )
    write_class_quest_sql(INSTALL_DIR, UNINSTALL_DIR)
    write_hunter_pet_sql(INSTALL_DIR, UNINSTALL_DIR, dbc_source=hunter_dbc_source)
    write_client_patch(REPO_ROOT / "client-patch" / "patch-A.mpq")


if __name__ == "__main__":
    main()
