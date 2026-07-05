#!/usr/bin/env python3
"""Generate checked-in mod-uac SQL from canonical wowgaming/client-data (v19)."""

from __future__ import annotations

import argparse
from pathlib import Path

from aracgen.cli import write_skill_overlay_sql
from aracgen.sources import DEFAULT_CANONICAL_PIN, CanonicalDbcSource, LocalDbcSource

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "cache"
INSTALL_DIR = REPO_ROOT / "data" / "sql" / "db-world"
UNINSTALL_DIR = REPO_ROOT / "data" / "sql" / "db-uninstall"
INSTALL_FILE = INSTALL_DIR / "mod_uac_skillraceclassinfo_dbc.sql"
UNINSTALL_FILE = UNINSTALL_DIR / "mod_uac_skillraceclassinfo_dbc_uninstall.sql"


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
    args = parser.parse_args()

    if args.dbc_dir is not None:
        source = LocalDbcSource(args.dbc_dir)
        print(f"Using local DBC override: {args.dbc_dir}")
    else:
        source = CanonicalDbcSource(
            pin=args.pin,
            cache_dir=args.cache_dir,
            refresh=args.refresh,
        )
        print(f"Using canonical client-data {args.pin}: {source.zip_path}")

    write_skill_overlay_sql(
        source,
        INSTALL_FILE,
        UNINSTALL_FILE,
        db_max_id=args.db_max_id,
    )


if __name__ == "__main__":
    main()
