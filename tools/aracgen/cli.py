"""Shared CLI helpers for generator front-ends."""

from __future__ import annotations

from pathlib import Path

from aracgen.emit_player import PlayerCreateEmitter, build_resolver
from aracgen.emit_skill import SkillOverlayEmitter
from aracgen.sources import DbcSource


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
) -> None:
    resolver = build_resolver(source.load_char_start_outfit())
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

    print(f"Generated playercreateinfo data for {len(result.kits)} combos")
