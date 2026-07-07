"""Shared CLI helpers for generator front-ends."""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

from aracgen.dbc import DbcTable
from aracgen.emit_class_quest import ClassQuestEmitter
from aracgen.emit_client import ClientPatchEmitter
from aracgen.emit_hunter_pet import HunterPetEmitter
from aracgen.emit_player import PlayerCreateEmitter, build_resolver
from aracgen.emit_skill import SkillOverlayEmitter
from aracgen.emit_totem import TotemEmitter
from aracgen.emit_trainers import (
    DEFAULT_TRAINER_OVERRIDES_PATH,
    TrainerEmitter,
    load_trainer_overrides,
)
from aracgen.matrix import ComboMatrix
from aracgen.snapshot import (
    DEFAULT_SNAPSHOT_DIR,
    capture_snapshot,
    load_snapshot,
    refresh_item_prototypes,
    write_snapshot,
)
from aracgen.snapshot_dsn import resolve_world_database_info
from aracgen.snapshot_model import MOD_UAC_CREATURE_GUID_MAX, Snapshot
from aracgen.sources import DbcSource
from aracgen.stock_loader import StockKitStore
from aracgen.trainer_catalog import TRAINER_GUID_BASE


def add_snapshot_cli_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("world snapshot (schema contract + starter trainers)")
    group.add_argument(
        "--snapshot",
        type=Path,
        help=(
            "Path to a world DB snapshot JSON "
            "(default: baked snapshot via data/snapshot/world.latest.json)"
        ),
    )
    group.add_argument(
        "--snapshot-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
        help=(
            "Directory containing world.latest.json when --snapshot is omitted "
            f"(default: {DEFAULT_SNAPSHOT_DIR})"
        ),
    )
    group.add_argument(
        "--refresh-snapshot",
        action="store_true",
        help="Capture a fresh world DB snapshot before emitting schema-contract SQL",
    )
    group.add_argument(
        "--snapshot-config",
        type=Path,
        dest="snapshot_config",
        help=(
            "Snapshot config file for --refresh-snapshot "
            "(default: tools/snapshot.conf or MOD_UAC_SNAPSHOT_CONFIG)"
        ),
    )
    group.add_argument(
        "--dsn",
        help=(
            "AC-style WorldDatabaseInfo for --refresh-snapshot: "
            "host;port;user;password;database"
        ),
    )


def add_trainer_cli_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("starter trainers")
    group.add_argument(
        "--trainer-guid-base",
        type=int,
        default=TRAINER_GUID_BASE,
        help=f"Base GUID for mod-uac starter trainers (default: {TRAINER_GUID_BASE})",
    )
    group.add_argument(
        "--trainer-overrides",
        type=Path,
        default=DEFAULT_TRAINER_OVERRIDES_PATH,
        help="YAML file with trainer placement/entry overrides",
    )


def resolve_generation_snapshot(
    args: argparse.Namespace,
    *,
    outfit: DbcTable | None = None,
) -> Snapshot:
    if getattr(args, "refresh_snapshot", False):
        dsn = resolve_world_database_info(
            config_path=getattr(args, "snapshot_config", None),
            cli_dsn=getattr(args, "dsn", None),
        )
        snapshot = capture_snapshot(dsn)
        output_dir = getattr(args, "snapshot_dir", None) or DEFAULT_SNAPSHOT_DIR
        versioned, pointer = write_snapshot(snapshot, output_dir)
        print(
            f"Refreshed snapshot version {snapshot.version_raw!r} -> {snapshot.version}"
        )
        print(f"Wrote {versioned}")
        print(f"Wrote pointer {pointer} -> {versioned.name}")
        if outfit is None:
            warnings.warn(
                "No CharStartOutfit.dbc source; skipped item_prototypes refresh",
                stacklevel=2,
            )
        else:
            item_path, item_count = refresh_item_prototypes(
                dsn,
                outfit,
                version=snapshot.version_raw,
            )
            print(f"Wrote {item_path} ({item_count} outfit item prototypes)")
        return snapshot

    snapshot_path = getattr(args, "snapshot", None)
    snapshot_dir = getattr(args, "snapshot_dir", None) or DEFAULT_SNAPSHOT_DIR
    if snapshot_path is not None:
        return load_snapshot(snapshot_path)
    return load_snapshot(snapshot_dir=snapshot_dir)


def validate_trainer_guid_base(guid_base: int) -> None:
    if not (TRAINER_GUID_BASE <= guid_base <= MOD_UAC_CREATURE_GUID_MAX):
        msg = (
            f"--trainer-guid-base must be within the mod-uac reserved creature band "
            f"({TRAINER_GUID_BASE}-{MOD_UAC_CREATURE_GUID_MAX}), got {guid_base}"
        )
        raise ValueError(msg)


def write_trainer_sql(
    install_path: Path,
    uninstall_path: Path,
    worksheet_path: Path,
    *,
    snapshot: Snapshot,
    overrides_path: Path | None = None,
    guid_base: int = TRAINER_GUID_BASE,
) -> None:
    validate_trainer_guid_base(guid_base)
    overrides = load_trainer_overrides(overrides_path)
    emitter = TrainerEmitter(
        snapshot=snapshot,
        guid_base=guid_base,
        overrides=overrides,
    )
    result = emitter.compute()
    if result.guid_max > MOD_UAC_CREATURE_GUID_MAX:
        msg = (
            f"Trainer emission exceeds reserved GUID band "
            f"({TRAINER_GUID_BASE}-{MOD_UAC_CREATURE_GUID_MAX}): "
            f"last guid {result.guid_max}"
        )
        raise ValueError(msg)

    install_path.parent.mkdir(parents=True, exist_ok=True)
    uninstall_path.parent.mkdir(parents=True, exist_ok=True)
    worksheet_path.parent.mkdir(parents=True, exist_ok=True)
    install_path.write_text(emitter.render_install(result), encoding="utf-8")
    uninstall_path.write_text(emitter.render_uninstall(result), encoding="utf-8")
    worksheet_path.write_text(emitter.render_worksheet(result), encoding="utf-8")

    print(
        f"Wrote {install_path} ({len(result.rows)} trainers, "
        f"guids {result.guid_base}-{result.guid_max})"
    )
    print(f"Wrote {uninstall_path}")
    print(f"Wrote {worksheet_path}")


def write_skill_overlay_sql(
    source: DbcSource,
    install_path: Path,
    uninstall_path: Path,
    *,
    db_max_id: int = 0,
    snapshot: Snapshot | None = None,
) -> None:
    table = source.load_skill_race_class_info()
    emitter = SkillOverlayEmitter(table, db_max_id=db_max_id, snapshot=snapshot)
    result = emitter.compute()

    install_path.parent.mkdir(parents=True, exist_ok=True)
    uninstall_path.parent.mkdir(parents=True, exist_ok=True)
    install_path.write_text(emitter.render_install(result), encoding="utf-8")
    uninstall_path.write_text(emitter.render_uninstall(result), encoding="utf-8")

    print(
        f"Wrote {install_path} ({len(result.rows)} overlay rows, "
        f"dbc max {result.dbc_max_id}, db max {result.db_max_id})"
    )
    print(f"Wrote {uninstall_path}")


def write_player_create_sql(
    source: DbcSource,
    install_dir: Path,
    uninstall_dir: Path,
    *,
    db_max_outfit_id: int = 0,
    snapshot: Snapshot | None = None,
) -> None:
    resolver = build_resolver(
        source.load_char_start_outfit(),
        db_max_outfit_id=db_max_outfit_id,
    )
    emitter = PlayerCreateEmitter(resolver, snapshot=snapshot)
    result = emitter.compute()
    install_files = emitter.render_install_files(result)
    uninstall_files = emitter.render_uninstall_files(result)

    install_dir.mkdir(parents=True, exist_ok=True)
    uninstall_dir.mkdir(parents=True, exist_ok=True)

    for table, sql in install_files.items():
        path = install_dir / f"mod_uac_{table}.sql"
        path.write_text(sql, encoding="utf-8")
        print(f"Wrote {path}")

    for table, sql in uninstall_files.items():
        path = uninstall_dir / f"mod_uac_{table}_uninstall.sql"
        path.write_text(sql, encoding="utf-8")
        print(f"Wrote {path}")

    print(
        f"Generated playercreateinfo data for {len(result.kits)} combos "
        f"(outfit dbc max {resolver.dbc_max_outfit_id}, db max {db_max_outfit_id})"
    )


def write_totem_sql(
    install_path: Path,
    uninstall_path: Path,
    *,
    snapshot: Snapshot | None = None,
) -> None:
    matrix = ComboMatrix.stock()
    emitter = TotemEmitter(matrix, snapshot=snapshot)
    result = emitter.compute()

    install_path.parent.mkdir(parents=True, exist_ok=True)
    uninstall_path.parent.mkdir(parents=True, exist_ok=True)
    install_path.write_text(emitter.render_install(result), encoding="utf-8")
    uninstall_path.write_text(emitter.render_uninstall(result), encoding="utf-8")

    race_ids = sorted({row.race_id for row in result.rows})
    print(f"Wrote {install_path} ({len(result.rows)} totem rows, races {race_ids})")
    print(f"Wrote {uninstall_path}")


def write_class_quest_sql(
    install_dir: Path,
    uninstall_dir: Path,
    *,
    snapshot: Snapshot | None = None,
) -> None:
    matrix = ComboMatrix.stock()
    store = StockKitStore.load()
    emitter = ClassQuestEmitter(matrix, store, snapshot=snapshot)
    result = emitter.compute()
    install_files = emitter.render_install_files(result)
    uninstall_files = emitter.render_uninstall_files(result)

    install_dir.mkdir(parents=True, exist_ok=True)
    uninstall_dir.mkdir(parents=True, exist_ok=True)

    for table, sql in install_files.items():
        path = install_dir / f"mod_uac_{table}.sql"
        path.write_text(sql, encoding="utf-8")
        print(f"Wrote {path}")

    for table, sql in uninstall_files.items():
        path = uninstall_dir / f"mod_uac_{table}_uninstall.sql"
        path.write_text(sql, encoding="utf-8")
        print(f"Wrote {path}")

    print(
        f"Generated class quest data: {len(result.quest_patches)} quest patches, "
        f"{len(result.addon_patches)} addon patches, "
        f"{len(result.spell_grants)} spell grants"
    )


def write_hunter_pet_sql(
    install_dir: Path,
    uninstall_dir: Path,
    *,
    dbc_source: Path | None = None,
    snapshot: Snapshot | None = None,
) -> None:
    emitter = HunterPetEmitter(dbc_source=dbc_source, snapshot=snapshot)
    result = emitter.compute()
    install_files = emitter.render_install_files(result)
    uninstall_files = emitter.render_uninstall_files(result)

    install_dir.mkdir(parents=True, exist_ok=True)
    uninstall_dir.mkdir(parents=True, exist_ok=True)

    for stem, sql in install_files.items():
        path = install_dir / f"mod_uac_{stem}.sql"
        path.write_text(sql, encoding="utf-8")
        print(f"Wrote {path}")

    for stem, sql in uninstall_files.items():
        path = uninstall_dir / f"mod_uac_{stem}_uninstall.sql"
        path.write_text(sql, encoding="utf-8")
        print(f"Wrote {path}")

    print(f"Generated hunter pet data: {len(result.spell_rows)} spell grants (all hunters)")


def write_client_patch(output_path: Path) -> None:
    emitter = ClientPatchEmitter()
    payload = emitter.compute()
    emitter.write(output_path)
    print(f"Wrote {output_path} ({len(payload)} bytes)")
