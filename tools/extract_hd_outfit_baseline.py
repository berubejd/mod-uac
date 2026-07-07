#!/usr/bin/env python3
"""Extract deduplicated HD CharStartOutfit JSON from patch-k or a loose .dbc file."""

from __future__ import annotations

import argparse
from pathlib import Path

from aracgen.dbc import DbcTable
from aracgen.formats import CHAR_START_OUTFIT
from aracgen.hd_outfit_baseline import (
    HD_OUTFIT_STOCK_INDEX_PATH,
    HD_OUTFIT_TEMPLATES_PATH,
    write_hd_outfit_catalog,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    "Official HD 3.3.5a client patch-k.mpq DBFilesClient\\CharStartOutfit.dbc (126 stock rows)"
)


def _load_table(path: Path) -> DbcTable:
    if path.suffix.lower() == ".dbc":
        return DbcTable.read_file(path, format_str=CHAR_START_OUTFIT)
    try:
        from mpyq import MPQArchive
    except ImportError as exc:
        msg = "mpyq is required to read .mpq sources (pip install mpyq)"
        raise SystemExit(msg) from exc
    raw = MPQArchive(str(path)).read_file("DBFilesClient\\CharStartOutfit.dbc")
    if raw is None:
        msg = f"CharStartOutfit.dbc not found in MPQ: {path}"
        raise SystemExit(msg)
    return DbcTable.read(raw, CHAR_START_OUTFIT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        type=Path,
        help="Path to patch-k.mpq or CharStartOutfit.dbc",
    )
    parser.add_argument(
        "--templates-out",
        type=Path,
        default=HD_OUTFIT_TEMPLATES_PATH,
        help=f"Output templates JSON (default: {HD_OUTFIT_TEMPLATES_PATH})",
    )
    parser.add_argument(
        "--stock-index-out",
        type=Path,
        default=HD_OUTFIT_STOCK_INDEX_PATH,
        help=f"Output stock index JSON (default: {HD_OUTFIT_STOCK_INDEX_PATH})",
    )
    parser.add_argument(
        "--source-label",
        default=DEFAULT_SOURCE,
        help="Provenance string stored in the JSON metadata",
    )
    args = parser.parse_args()

    table = _load_table(args.source)
    write_hd_outfit_catalog(
        table,
        args.templates_out,
        args.stock_index_out,
        source=args.source_label,
    )
    print(
        f"Wrote {args.templates_out} and {args.stock_index_out} "
        f"({table.record_count} stock rows)"
    )


if __name__ == "__main__":
    main()
