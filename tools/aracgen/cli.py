"""Shared CLI helpers for generator front-ends."""

from __future__ import annotations

from pathlib import Path

from aracgen.emit_class_quest import ClassQuestEmitter
from aracgen.emit_client import ClientPatchEmitter
from aracgen.emit_hunter_pet import HunterPetEmitter
from aracgen.emit_player import PlayerCreateEmitter, build_resolver
from aracgen.emit_skill import SkillOverlayEmitter
from aracgen.emit_totem import TotemEmitter
from aracgen.matrix import ComboMatrix
from aracgen.sources import DbcSource
from aracgen.stock_loader import StockKitStore


def write_skill_overlay_sql(
    source: DbcSource,
    install_path: Path,
    uninstall_path: Path,
    *,
    db_max_id: int = 0,
) -> None:
    table = source.load_skill_race_class_info()
    emitter = SkillOverlayEmitter(table, db_max_id=db_max_id)
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
) -> None:
    resolver = build_resolver(
        source.load_char_start_outfit(),
        db_max_outfit_id=db_max_outfit_id,
    )
    emitter = PlayerCreateEmitter(resolver)
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
) -> None:
    matrix = ComboMatrix.stock()
    emitter = TotemEmitter(matrix)
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
) -> None:
    matrix = ComboMatrix.stock()
    store = StockKitStore.load()
    emitter = ClassQuestEmitter(matrix, store)
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
) -> None:
    emitter = HunterPetEmitter(dbc_source=dbc_source)
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
