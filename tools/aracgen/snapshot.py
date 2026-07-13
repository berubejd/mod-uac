"""Capture and load versioned world DB snapshots for mod-uac emitters."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aracgen.snapshot_dsn import DatabaseDsn, resolve_world_database_info
from aracgen.snapshot_model import (
    LATEST_POINTER_FILE,
    MOD_UAC_CREATURE_GUID_MAX,
    MOD_UAC_CREATURE_GUID_MIN,
    SCHEMA_TABLES,
    ColumnDef,
    Snapshot,
    TableSchema,
    build_spawn_defaults,
    creature_entry_column,
    sanitize_db_version,
    snapshot_filename_version,
)
from aracgen.snapshot_zones import (
    STARTER_SPAWN_BOX_RADIUS,
    build_starter_zone_boxes,
    spawn_in_starter_box,
    starter_zone_sql_clause,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshot"


def capture_item_prototypes(
    connection,
    item_ids: frozenset[int],
) -> dict[int, tuple[int, int]]:
    """Load (class, subclass) for outfit item IDs from the world DB."""
    if not item_ids:
        return {}
    sorted_ids = sorted(item_ids)
    placeholders = ", ".join(["%s"] * len(sorted_ids))
    query = (
        f"SELECT entry, class, subclass FROM item_template "
        f"WHERE entry IN ({placeholders})"
    )
    with connection.cursor() as cursor:
        cursor.execute(query, sorted_ids)
        rows = cursor.fetchall()
    found = {
        int(row["entry"]): (int(row["class"]), int(row["subclass"])) for row in rows
    }
    missing = set(item_ids) - found.keys()
    if missing:
        msg = f"item_template missing entries: {sorted(missing)}"
        raise ValueError(msg)
    return found


def refresh_item_prototypes(
    dsn: DatabaseDsn,
    outfit,
    *,
    output_path: Path | None = None,
    version: str | None = None,
) -> tuple[Path, int]:
    """Capture minimal item class/subclass data for mod-uac outfit overlays."""
    from aracgen.item_prototypes import DEFAULT_ITEM_PROTOTYPES_PATH, write_item_prototypes_file
    from aracgen.outfit_items import collect_mod_uac_outfit_item_ids

    item_ids = collect_mod_uac_outfit_item_ids(outfit)
    connection = _connect(dsn)
    try:
        items = capture_item_prototypes(connection, item_ids)
    finally:
        connection.close()
    target = output_path or DEFAULT_ITEM_PROTOTYPES_PATH
    write_item_prototypes_file(
        target,
        items,
        source=dsn.redacted,
        version=version,
    )
    return target, len(items)


def _connect(dsn: DatabaseDsn):
    try:
        import pymysql
    except ImportError as exc:
        msg = "PyMySQL is required for snapshot capture (pip install PyMySQL)"
        raise RuntimeError(msg) from exc

    return pymysql.connect(
        host=dsn.host,
        port=dsn.port,
        user=dsn.user,
        password=dsn.password,
        database=dsn.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _normalize_default(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def is_mod_uac_creature_guid(guid: int) -> bool:
    return MOD_UAC_CREATURE_GUID_MIN <= guid <= MOD_UAC_CREATURE_GUID_MAX


def capture_table_schema(connection, database: str, table: str) -> TableSchema:
    query = """
        SELECT COLUMN_NAME AS name,
               ORDINAL_POSITION AS ordinal,
               COLUMN_TYPE AS type,
               IS_NULLABLE AS nullable,
               COLUMN_DEFAULT AS default_value
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (database, table))
        rows = cursor.fetchall()

    if not rows:
        msg = f"Table {table!r} not found in database {database!r}"
        raise ValueError(msg)

    columns = tuple(
        ColumnDef(
            name=row["name"],
            ordinal=int(row["ordinal"]),
            type=row["type"],
            nullable=str(row["nullable"]).upper() == "YES",
            default=_normalize_default(row["default_value"]),
        )
        for row in rows
    )
    return TableSchema(table=table, columns=columns)


def capture_version_metadata(connection) -> tuple[str, str | None, str | None, str | None]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT db_version, core_version, core_revision FROM version LIMIT 1"
        )
        row = cursor.fetchone()

    if not row:
        warnings.warn("version table empty; using unknown snapshot version", stacklevel=2)
        return sanitize_db_version(None), None, None, None

    raw = row.get("db_version")
    if raw is None or not str(raw).strip():
        warnings.warn("db_version is NULL; using timestamp fallback", stacklevel=2)
        version_key = sanitize_db_version(None)
    else:
        version_key = snapshot_filename_version(str(raw))

    return (
        version_key,
        row.get("core_version"),
        row.get("core_revision"),
        raw,
    )


def _load_playercreateinfo(cursor) -> list[dict[str, Any]]:
    cursor.execute(
        "SELECT race, class, map, zone, position_x, position_y, position_z, orientation "
        "FROM playercreateinfo ORDER BY race, class"
    )
    return [
        {
            "race": int(row["race"]),
            "class": int(row["class"]),
            "map": int(row["map"]),
            "zone": int(row["zone"]),
            "x": float(row["position_x"]),
            "y": float(row["position_y"]),
            "z": float(row["position_z"]),
            "o": float(row["orientation"]),
        }
        for row in cursor.fetchall()
    ]


def _starter_zones_payload(boxes: tuple) -> list[dict[str, Any]]:
    return [
        {
            "map": box.map_id,
            "zone": box.zone_id,
            "x": box.cx,
            "y": box.cy,
            "faction": box.faction,
        }
        for box in boxes
    ]


def _trim_trainer_metadata(
    *,
    entries: set[int],
    creature_default_trainer: dict[int, int],
    trainer_spell_counts: dict[int, int],
    trainers: dict[int, dict[str, int]],
    creature_template: dict[int, dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int], dict[str, dict[str, int]], dict[str, dict[str, Any]]]:
    filtered_cdt = {
        creature_id: trainer_id
        for creature_id, trainer_id in creature_default_trainer.items()
        if creature_id in entries
    }
    trainer_ids = set(filtered_cdt.values())
    return (
        {str(creature_id): trainer_id for creature_id, trainer_id in filtered_cdt.items()},
        {
            str(trainer_id): count
            for trainer_id, count in trainer_spell_counts.items()
            if trainer_id in trainer_ids
        },
        {
            str(trainer_id): meta
            for trainer_id, meta in trainers.items()
            if trainer_id in trainer_ids
        },
        {str(entry): meta for entry, meta in creature_template.items() if entry in entries},
    )


def _exclude_gated_spawns(trainers: dict[str, Any]) -> dict[str, Any]:
    gated = {int(guid) for guid in trainers.pop("gated_guids", [])}
    if not gated:
        return trainers
    trainers["creature_spawns"] = [
        spawn
        for spawn in trainers["creature_spawns"]
        if int(spawn["guid"]) not in gated
    ]
    return trainers


def _apply_kept_spawns(
    trainers: dict[str, Any],
    kept_spawns: list[dict[str, Any]],
) -> dict[str, Any]:
    trainers["creature_spawns"] = kept_spawns
    kept_entries = {int(spawn["entry"]) for spawn in kept_spawns}

    cdt = {int(k): int(v) for k, v in trainers.get("creature_default_trainer", {}).items()}
    spell_counts = {int(k): int(v) for k, v in trainers.get("trainer_spell_counts", {}).items()}
    trainer_meta = {int(k): v for k, v in trainers.get("trainers", {}).items()}
    templates = {int(k): v for k, v in trainers.get("creature_template", {}).items()}
    trimmed_cdt, trimmed_counts, trimmed_trainers, trimmed_templates = _trim_trainer_metadata(
        entries=kept_entries,
        creature_default_trainer=cdt,
        trainer_spell_counts=spell_counts,
        trainers=trainer_meta,
        creature_template=templates,
    )
    trainers["creature_default_trainer"] = trimmed_cdt
    trainers["trainer_spell_counts"] = trimmed_counts
    trainers["trainers"] = trimmed_trainers
    trainers["creature_template"] = trimmed_templates

    if kept_spawns and "equipment_id" in kept_spawns[0]:
        trainers["spawn_defaults"] = build_spawn_defaults(
            [
                {
                    "guid": int(spawn["guid"]),
                    "entry": int(spawn["entry"]),
                    "equipment_id": int(spawn["equipment_id"]),
                    "curhealth": int(spawn["curhealth"]),
                    "curmana": int(spawn["curmana"]),
                    "npcflag": int(spawn["npcflag"]),
                }
                for spawn in kept_spawns
            ]
        )
    else:
        trainers["spawn_defaults"] = {
            key: value
            for key, value in trainers.get("spawn_defaults", {}).items()
            if int(key) in kept_entries
        }
    return trainers


def filter_trainer_extract(
    trainer_data: dict[str, Any],
    *,
    radius: float = STARTER_SPAWN_BOX_RADIUS,
) -> dict[str, Any]:
    """Keep only starter-zone trainer spawns and their referenced metadata."""
    playercreateinfo = trainer_data["playercreateinfo"]
    boxes = build_starter_zone_boxes(playercreateinfo)

    spawn_rows: list[dict[str, Any]] = []
    creature_spawns: list[dict[str, Any]] = []
    for row in trainer_data["creature_spawns"]:
        if not spawn_in_starter_box(
            map_id=int(row["map"]),
            x=float(row["x"]),
            y=float(row["y"]),
            boxes=boxes,
            radius=radius,
        ):
            continue
        spawn_rows.append(row)
        creature_spawns.append(row)

    kept_entries = {int(row["entry"]) for row in spawn_rows}
    cdt = {int(k): int(v) for k, v in trainer_data["creature_default_trainer"].items()}
    spell_counts = {int(k): int(v) for k, v in trainer_data["trainer_spell_counts"].items()}
    trainer_meta = {int(k): v for k, v in trainer_data["trainers"].items()}
    templates = {int(k): v for k, v in trainer_data["creature_template"].items()}

    trimmed_cdt, trimmed_counts, trimmed_trainers, trimmed_templates = _trim_trainer_metadata(
        entries=kept_entries,
        creature_default_trainer=cdt,
        trainer_spell_counts=spell_counts,
        trainers=trainer_meta,
        creature_template=templates,
    )

    default_rows = [
        {
            "guid": int(row["guid"]),
            "entry": int(row["entry"]),
            "equipment_id": int(row["equipment_id"]),
            "curhealth": int(row["curhealth"]),
            "curmana": int(row["curmana"]),
            "npcflag": int(row["npcflag"]),
        }
        for row in spawn_rows
        if "equipment_id" in row
    ]

    return {
        "playercreateinfo": playercreateinfo,
        "starter_zones": _starter_zones_payload(boxes),
        "creature_spawns": creature_spawns,
        "spawn_defaults": build_spawn_defaults(default_rows) if default_rows else {},
        "creature_default_trainer": trimmed_cdt,
        "trainer_spell_counts": trimmed_counts,
        "trainers": trimmed_trainers,
        "creature_template": trimmed_templates,
    }


def capture_trainer_data(connection, creature_schema: TableSchema) -> dict[str, Any]:
    entry_col = creature_entry_column(creature_schema)

    with connection.cursor() as cursor:
        playercreateinfo = _load_playercreateinfo(cursor)
        zone_boxes = build_starter_zone_boxes(playercreateinfo)
        zone_sql, zone_params = starter_zone_sql_clause(zone_boxes)

        spawn_query = f"""
            SELECT c.guid,
                   c.{entry_col} AS entry,
                   c.map,
                   c.position_x,
                   c.position_y,
                   c.position_z,
                   c.orientation,
                   c.equipment_id,
                   c.curhealth,
                   c.curmana,
                   c.npcflag
            FROM creature c
            INNER JOIN creature_default_trainer cdt ON cdt.CreatureId = c.{entry_col}
            LEFT JOIN game_event_creature gec ON gec.guid = c.guid
            WHERE gec.guid IS NULL
              AND c.guid NOT BETWEEN %s AND %s
              AND (c.Comment IS NULL OR c.Comment NOT LIKE 'mod-uac%%')
              AND ({zone_sql})
            ORDER BY c.{entry_col}, c.guid
        """
        cursor.execute(
            spawn_query,
            (MOD_UAC_CREATURE_GUID_MIN, MOD_UAC_CREATURE_GUID_MAX, *zone_params),
        )

        spawn_rows: list[dict[str, Any]] = []
        creature_spawns: list[dict[str, Any]] = []
        kept_entries: set[int] = set()
        for row in cursor.fetchall():
            entry = int(row["entry"])
            kept_entries.add(entry)
            spawn_row = {
                "guid": int(row["guid"]),
                "entry": entry,
                "map": int(row["map"]),
                "x": float(row["position_x"]),
                "y": float(row["position_y"]),
                "z": float(row["position_z"]),
                "o": float(row["orientation"]),
                "equipment_id": int(row["equipment_id"]),
                "curhealth": int(row["curhealth"]),
                "curmana": int(row["curmana"]),
                "npcflag": int(row["npcflag"]),
            }
            spawn_rows.append(spawn_row)
            creature_spawns.append(dict(spawn_row))

        if not kept_entries:
            return {
                "playercreateinfo": playercreateinfo,
                "starter_zones": _starter_zones_payload(zone_boxes),
                "creature_spawns": [],
                "spawn_defaults": {},
                "creature_default_trainer": {},
                "trainer_spell_counts": {},
                "trainers": {},
                "creature_template": {},
            }

        entry_placeholders = ", ".join(["%s"] * len(kept_entries))
        entry_list = sorted(kept_entries)

        cursor.execute(
            f"SELECT CreatureId, TrainerId FROM creature_default_trainer "
            f"WHERE CreatureId IN ({entry_placeholders})",
            entry_list,
        )
        creature_default_trainer = {
            int(row["CreatureId"]): int(row["TrainerId"]) for row in cursor.fetchall()
        }
        trainer_ids = sorted(set(creature_default_trainer.values()))

        trainer_placeholders = ", ".join(["%s"] * len(trainer_ids))
        cursor.execute(
            f"SELECT TrainerId, COUNT(*) AS spell_count FROM trainer_spell "
            f"WHERE TrainerId IN ({trainer_placeholders}) GROUP BY TrainerId",
            trainer_ids,
        )
        trainer_spell_counts = {
            int(row["TrainerId"]): int(row["spell_count"]) for row in cursor.fetchall()
        }

        cursor.execute(
            f"SELECT Id, Type, Requirement FROM trainer "
            f"WHERE Id IN ({trainer_placeholders})",
            trainer_ids,
        )
        trainers = {
            int(row["Id"]): {
                "type": int(row["Type"]),
                "requirement": int(row["Requirement"]),
            }
            for row in cursor.fetchall()
        }

        cursor.execute(
            f"SELECT entry, name, subname, faction, npcflag FROM creature_template "
            f"WHERE entry IN ({entry_placeholders})",
            entry_list,
        )
        creature_template = {
            int(row["entry"]): {
                "name": row["name"],
                "subname": row["subname"],
                "faction": int(row["faction"]),
                "npcflag": int(row["npcflag"]),
            }
            for row in cursor.fetchall()
        }

        capital_trainers = _capture_capital_trainers(cursor, entry_col)

    return {
        "playercreateinfo": playercreateinfo,
        "starter_zones": _starter_zones_payload(zone_boxes),
        "creature_spawns": creature_spawns,
        "spawn_defaults": build_spawn_defaults(spawn_rows),
        "creature_default_trainer": {
            str(creature_id): trainer_id
            for creature_id, trainer_id in creature_default_trainer.items()
        },
        "trainer_spell_counts": {
            str(trainer_id): count for trainer_id, count in trainer_spell_counts.items()
        },
        "trainers": {str(trainer_id): meta for trainer_id, meta in trainers.items()},
        "creature_template": {
            str(entry): meta for entry, meta in creature_template.items()
        },
        "capital_trainers": capital_trainers,
    }


CLASS_TRAINER_SUBNAME_REGEXP = (
    "(Warrior|Paladin|Hunter|Rogue|Priest|Shaman|Mage|Warlock|Druid) Trainer"
)


def _capture_capital_trainers(cursor, entry_col: str) -> list[dict[str, Any]]:
    """Capture active class-trainer spawns in each capital box for the capital pass.

    Excludes mod-uac's own spawns (Comment / reserved GUID band) so re-capturing a
    world that already has mod-uac applied still reads the clean AC-base trainers.
    Only class trainers (subname ``<Class> Trainer``) are kept, to stay lean.
    """
    from aracgen.capital_trainer_catalog import CAPITAL_ZONES, capital_zone_sql_clause

    clause, params = capital_zone_sql_clause(CAPITAL_ZONES)
    cursor.execute(
        f"""
        SELECT c.{entry_col} AS entry, ct.name, ct.subname, c.map,
               c.position_x AS x, c.position_y AS y, c.position_z AS z, c.orientation AS o,
               COALESCE(ts.spells, 0) AS spells
        FROM creature c
        JOIN creature_template ct ON ct.entry = c.{entry_col}
        JOIN creature_default_trainer cdt ON cdt.CreatureId = c.{entry_col}
        LEFT JOIN game_event_creature gec ON gec.guid = c.guid
        LEFT JOIN (
            SELECT TrainerId, COUNT(*) AS spells FROM trainer_spell GROUP BY TrainerId
        ) ts ON ts.TrainerId = cdt.TrainerId
        WHERE gec.guid IS NULL
          AND (c.Comment IS NULL OR c.Comment NOT LIKE 'mod-uac%%')
          AND c.guid NOT BETWEEN %s AND %s
          AND (ct.npcflag & 16) AND (c.spawnMask & 1)
          AND ct.subname REGEXP %s
          AND ({clause})
        ORDER BY c.{entry_col}, c.guid
        """,
        (MOD_UAC_CREATURE_GUID_MIN, MOD_UAC_CREATURE_GUID_MAX,
         CLASS_TRAINER_SUBNAME_REGEXP, *params),
    )
    return [
        {
            "entry": int(row["entry"]),
            "name": row["name"],
            "subname": row["subname"],
            "map": int(row["map"]),
            "x": float(row["x"]),
            "y": float(row["y"]),
            "z": float(row["z"]),
            "o": float(row["o"]),
            "spells": int(row["spells"]),
        }
        for row in cursor.fetchall()
    ]


def capture_snapshot(dsn: DatabaseDsn) -> Snapshot:
    connection = _connect(dsn)
    try:
        version, core_version, core_revision, version_raw = capture_version_metadata(
            connection
        )
        schemas = {
            table: capture_table_schema(connection, dsn.database, table)
            for table in SCHEMA_TABLES
        }
        trainer_data = capture_trainer_data(connection, schemas["creature"])
    finally:
        connection.close()

    return Snapshot(
        version=version,
        version_raw=str(version_raw or version),
        core_version=core_version,
        core_revision=core_revision,
        captured_at=datetime.now(UTC).isoformat(),
        source=dsn.redacted,
        schemas=schemas,
        data={"trainers": trainer_data},
    )


def write_latest_pointer(output_dir: Path, versioned_filename: str) -> Path:
    pointer = output_dir / LATEST_POINTER_FILE
    pointer.write_text(
        json.dumps({"file": versioned_filename}, indent=2) + "\n",
        encoding="utf-8",
    )
    return pointer


def resolve_baked_snapshot_path(root: Path) -> Path:
    latest = root / LATEST_POINTER_FILE
    if not latest.is_file():
        msg = f"No baked snapshot pointer at {latest}"
        raise FileNotFoundError(msg)

    payload = json.loads(latest.read_text(encoding="utf-8"))
    if "schemas" in payload:
        return latest

    filename = payload.get("file")
    if not filename:
        msg = f"Invalid snapshot pointer (missing file): {latest}"
        raise ValueError(msg)

    target = root / filename
    if not target.is_file():
        msg = f"Snapshot pointer targets missing file: {target}"
        raise FileNotFoundError(msg)
    return target


def write_snapshot(snapshot: Snapshot, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    versioned = output_dir / f"world.{snapshot.version}.json"
    if versioned.exists():
        existing = Snapshot.load(versioned)
        if existing.version_raw != snapshot.version_raw:
            digest = hashlib.sha256(snapshot.version_raw.encode()).hexdigest()[:8]
            versioned = output_dir / f"world.{snapshot.version}-{digest}.json"
    snapshot.write(versioned)
    pointer = write_latest_pointer(output_dir, versioned.name)
    return versioned, pointer


def slim_trainer_snapshot(snapshot: Snapshot) -> Snapshot:
    """Drop legacy bulk fields and re-filter trainer data to starter zones."""
    trainers = _exclude_gated_spawns(dict(snapshot.data["trainers"]))
    filtered = filter_trainer_extract(trainers)
    return Snapshot(
        version=snapshot.version,
        version_raw=snapshot.version_raw,
        core_version=snapshot.core_version,
        core_revision=snapshot.core_revision,
        captured_at=snapshot.captured_at,
        source=snapshot.source,
        schemas=snapshot.schemas,
        data={"trainers": filtered},
    )


def scrub_mod_uac_trainer_spawns(snapshot: Snapshot) -> Snapshot:
    """Remove mod-uac reserved GUID spawns from a loaded snapshot."""
    trainers = _exclude_gated_spawns(dict(snapshot.data["trainers"]))
    kept_spawns = [
        spawn
        for spawn in trainers["creature_spawns"]
        if not is_mod_uac_creature_guid(int(spawn["guid"]))
    ]
    trainers = _apply_kept_spawns(trainers, kept_spawns)

    return Snapshot(
        version=snapshot.version,
        version_raw=snapshot.version_raw,
        core_version=snapshot.core_version,
        core_revision=snapshot.core_revision,
        captured_at=snapshot.captured_at,
        source=snapshot.source,
        schemas=snapshot.schemas,
        data={**snapshot.data, "trainers": trainers},
    )


def load_snapshot(path: Path | None = None, snapshot_dir: Path | None = None) -> Snapshot:
    if path is not None:
        return Snapshot.load(path)
    root = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    return Snapshot.load(resolve_baked_snapshot_path(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture a versioned mod-uac world DB snapshot (schema + trainer extracts).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Snapshot config file (default: tools/snapshot.conf or MOD_UAC_SNAPSHOT_CONFIG)",
    )
    parser.add_argument(
        "--dsn",
        help="AC-style WorldDatabaseInfo override: host;port;user;password;database",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
        help=f"Directory for world.<version>.json (default: {DEFAULT_SNAPSHOT_DIR})",
    )
    args = parser.parse_args(argv)

    dsn = resolve_world_database_info(config_path=args.config, cli_dsn=args.dsn)
    snapshot = capture_snapshot(dsn)
    versioned, pointer = write_snapshot(snapshot, args.output_dir)

    trainers = snapshot.data["trainers"]
    print(f"Captured snapshot version {snapshot.version_raw!r} -> {snapshot.version}")
    print(f"Source: {snapshot.source}")
    print(f"Wrote {versioned}")
    print(f"Wrote pointer {pointer} -> {versioned.name}")
    print(f"Starter zones: {len(trainers['starter_zones'])}")
    print(f"Trainer spawns (starter zones): {len(trainers['creature_spawns'])}")

    from aracgen.sources import DEFAULT_CANONICAL_PIN, CanonicalDbcSource, cached_client_data_zip

    cache_dir = REPO_ROOT / "data" / "cache"
    zip_path = cached_client_data_zip(cache_dir)
    if zip_path.is_file():
        outfit = CanonicalDbcSource(
            pin=DEFAULT_CANONICAL_PIN,
            cache_dir=cache_dir,
        ).load_char_start_outfit()
        item_path, item_count = refresh_item_prototypes(
            dsn,
            outfit,
            version=snapshot.version_raw,
        )
        print(f"Wrote {item_path} ({item_count} outfit item prototypes)")
    else:
        warnings.warn(
            "client-data cache missing; skipped item_prototypes refresh "
            f"(expected {zip_path})",
            stacklevel=2,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
