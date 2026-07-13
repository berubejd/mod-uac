"""World DB snapshot domain model for schema-driven SQL emitters."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Logical emitter fields -> physical columns (first match wins).
COLUMN_ALIASES: dict[str, dict[str, list[str]]] = {
    "creature": {"entry": ["id", "id1"]},
}

# Reserved mod-uac creature GUID band (trainer emitters), split into sub-bands so
# the starter and capital trainer SQL files each scope their own DELETE and never
# clobber each other regardless of apply order.
MOD_UAC_CREATURE_GUID_MIN = 6_000_000
MOD_UAC_CREATURE_GUID_MAX = 6_009_999
MOD_UAC_STARTER_GUID_MIN = 6_000_000
MOD_UAC_STARTER_GUID_MAX = 6_004_999
MOD_UAC_CAPITAL_GUID_MIN = 6_005_000
MOD_UAC_CAPITAL_GUID_MAX = 6_009_999

# Reserved mod-uac quest_template ID band (synthetic totem-access quests).
# Distinct namespace from creature.guid; stock quest IDs top out well below this.
MOD_UAC_QUEST_ID_MIN = 6_000_000
MOD_UAC_QUEST_ID_MAX = 6_009_999

LATEST_POINTER_FILE = "world.latest.json"

SCHEMA_TABLES: tuple[str, ...] = (
    "creature",
    "playercreateinfo",
    "playercreateinfo_action",
    "playercreateinfo_spell_custom",
    "playercreateinfo_skills",
    "charstartoutfit_dbc",
    "skillraceclassinfo_dbc",
    "skilllineability_dbc",
    "player_totem_model",
    "quest_template",
    "quest_template_addon",
    "quest_offer_reward",
    "creature_queststarter",
    "creature_questender",
    "spell_dbc",
)


@dataclass(frozen=True, slots=True)
class ColumnDef:
    name: str
    ordinal: int
    type: str
    nullable: bool
    default: Any

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ordinal": self.ordinal,
            "type": self.type,
            "nullable": self.nullable,
            "default": self.default,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> ColumnDef:
        return cls(
            name=str(payload["name"]),
            ordinal=int(payload["ordinal"]),
            type=str(payload["type"]),
            nullable=bool(payload["nullable"]),
            default=payload.get("default"),
        )


@dataclass(frozen=True, slots=True)
class TableSchema:
    table: str
    columns: tuple[ColumnDef, ...]

    def column_names(self) -> list[str]:
        return [column.name for column in self.columns]

    def has_column(self, name: str) -> bool:
        return any(column.name == name for column in self.columns)

    def default(self, name: str) -> Any:
        for column in self.columns:
            if column.name == name:
                return column.default
        msg = f"Column {name!r} not found on table {self.table!r}"
        raise KeyError(msg)

    def resolve_logical(self, logical: str) -> str:
        for candidate in COLUMN_ALIASES.get(self.table, {}).get(logical, (logical,)):
            if self.has_column(candidate):
                return candidate
        msg = f"Logical field {logical!r} not mapped for table {self.table!r}"
        raise KeyError(msg)

    def to_json(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "columns": [column.to_json() for column in self.columns],
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> TableSchema:
        columns = tuple(ColumnDef.from_json(item) for item in payload["columns"])
        return cls(table=str(payload["table"]), columns=columns)


@dataclass(frozen=True, slots=True)
class Snapshot:
    version: str
    version_raw: str
    core_version: str | None
    core_revision: str | None
    captured_at: str
    source: str
    schemas: dict[str, TableSchema]
    data: dict[str, Any]

    def schema(self, table: str) -> TableSchema:
        try:
            return self.schemas[table]
        except KeyError as exc:
            msg = f"Table {table!r} not present in snapshot schemas"
            raise KeyError(msg) from exc

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "version_raw": self.version_raw,
            "core_version": self.core_version,
            "core_revision": self.core_revision,
            "captured_at": self.captured_at,
            "source": self.source,
            "schemas": {name: schema.to_json() for name, schema in self.schemas.items()},
            "data": self.data,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> Snapshot:
        schemas = {
            name: TableSchema.from_json(schema_payload)
            for name, schema_payload in payload["schemas"].items()
        }
        return cls(
            version=str(payload["version"]),
            version_raw=str(payload["version_raw"]),
            core_version=payload.get("core_version"),
            core_revision=payload.get("core_revision"),
            captured_at=str(payload["captured_at"]),
            source=str(payload["source"]),
            schemas=schemas,
            data=dict(payload.get("data", {})),
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_json(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> Snapshot:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_json(payload)


def sanitize_db_version(db_version: str | None) -> str:
    if not db_version or not str(db_version).strip():
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"unknown-{stamp}"
    cleaned = re.sub(r"[^\w.\-]+", "_", str(db_version).strip())
    cleaned = cleaned.strip("._")
    return cleaned or "unknown"


def snapshot_filename_version(version_raw: str) -> str:
    """Filesystem key from db_version; hash suffix when sanitization is lossy."""
    sanitized = sanitize_db_version(version_raw)
    raw = version_raw.strip()
    if raw and sanitized != raw:
        digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
        return f"{sanitized}-{digest}"
    return sanitized


def build_spawn_defaults(
    spawn_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Pick lowest-guid spawn per entry for stable emission defaults."""
    defaults: dict[str, dict[str, Any]] = {}
    for row in sorted(spawn_rows, key=lambda item: (item["entry"], item["guid"])):
        defaults.setdefault(
            str(row["entry"]),
            {
                "equipment_id": row["equipment_id"],
                "curhealth": row["curhealth"],
                "curmana": row["curmana"],
                "npcflag": row["npcflag"],
            },
        )
    return defaults


def creature_entry_column(schema: TableSchema) -> str:
    return schema.resolve_logical("entry")


_CREATE_TABLE = re.compile(
    r"CREATE TABLE `(?P<table>[^`]+)` \((?P<body>.*?)\) ENGINE",
    re.S | re.I,
)
_COLUMN_LINE = re.compile(r"^\s*`(?P<name>[^`]+)`\s+(?P<def>.+?)\s*,?\s*$")


def _parse_column_default(definition: str) -> Any:
    upper = definition.upper()
    if "DEFAULT" not in upper:
        return None
    default_idx = upper.index("DEFAULT")
    default_raw = definition[default_idx + len("DEFAULT") :].strip()
    if default_raw.upper().startswith("NULL"):
        return None
    if default_raw.startswith("'") and default_raw.endswith("'"):
        return default_raw[1:-1]
    if default_raw.startswith('"') and default_raw.endswith('"'):
        return default_raw[1:-1]
    try:
        if "." in default_raw:
            return float(default_raw)
        return int(default_raw)
    except ValueError:
        return default_raw


def _parse_column_type(definition: str) -> tuple[str, bool]:
    upper = definition.upper()
    nullable = "NOT NULL" not in upper or "DEFAULT NULL" in upper
    type_part = definition.split(" NOT NULL", 1)[0]
    type_part = type_part.split(" DEFAULT ", 1)[0]
    type_part = type_part.split(" CHARACTER SET ", 1)[0]
    type_part = type_part.split(" COLLATE ", 1)[0]
    return type_part.strip(), nullable


def parse_create_table_ddl(ddl: str, table: str) -> TableSchema:
    match = _CREATE_TABLE.search(ddl)
    if match is None or match.group("table") != table:
        msg = f"Could not parse CREATE TABLE for {table!r}"
        raise ValueError(msg)

    columns: list[ColumnDef] = []
    for ordinal, raw_line in enumerate(match.group("body").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("PRIMARY") or line.startswith("KEY"):
            continue
        col_match = _COLUMN_LINE.match(line)
        if col_match is None:
            continue
        name = col_match.group("name")
        definition = col_match.group("def")
        column_type, nullable = _parse_column_type(definition)
        columns.append(
            ColumnDef(
                name=name,
                ordinal=ordinal,
                type=column_type,
                nullable=nullable,
                default=_parse_column_default(definition),
            )
        )

    if not columns:
        msg = f"No columns parsed for table {table!r}"
        raise ValueError(msg)
    return TableSchema(table=table, columns=tuple(columns))


def load_table_schema_from_ac_base(ac_base_dir: Path, table: str) -> TableSchema:
    sql_path = ac_base_dir / f"{table}.sql"
    if not sql_path.is_file():
        msg = f"AC base schema file not found: {sql_path}"
        raise FileNotFoundError(msg)
    return parse_create_table_ddl(sql_path.read_text(encoding="utf-8", errors="replace"), table)
