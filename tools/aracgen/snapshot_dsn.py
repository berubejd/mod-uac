"""Parse AzerothCore-style database connection strings for snapshot capture."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

ENV_CONFIG_PATH = "MOD_UAC_SNAPSHOT_CONFIG"
ENV_WORLD_DATABASE_INFO = "MOD_UAC_WORLD_DATABASE_INFO"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "snapshot.conf"


@dataclass(frozen=True, slots=True)
class DatabaseDsn:
    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def parse(cls, value: str) -> DatabaseDsn:
        parts = [part.strip() for part in value.split(";")]
        if len(parts) != 5:
            msg = (
                "Database DSN must be '<host>;<port>;<user>;<password>;<database>' "
                f"(got {len(parts)} parts)"
            )
            raise ValueError(msg)
        host, port_raw, user, password, database = parts
        try:
            port = int(port_raw)
        except ValueError as exc:
            msg = f"Invalid database port: {port_raw!r}"
            raise ValueError(msg) from exc
        if not host or not user or not database:
            msg = "Database DSN host, user, and database must be non-empty"
            raise ValueError(msg)
        return cls(host=host, port=port, user=user, password=password, database=database)

    @property
    def redacted(self) -> str:
        return f"{self.host};{self.port};{self.user};***;{self.database}"


_CONFIG_LINE = re.compile(
    r"^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.+?)\s*$"
)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def read_config_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        msg = f"Snapshot config not found: {path}"
        raise FileNotFoundError(msg)

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _CONFIG_LINE.match(stripped)
        if not match:
            continue
        values[match.group("key")] = _strip_quotes(match.group("value"))
    return values


def resolve_world_database_info(
    *,
    config_path: Path | None = None,
    cli_dsn: str | None = None,
) -> DatabaseDsn:
    if cli_dsn:
        return DatabaseDsn.parse(cli_dsn)

    env_dsn = os.environ.get(ENV_WORLD_DATABASE_INFO)
    if env_dsn:
        return DatabaseDsn.parse(env_dsn)

    config_file = config_path
    if config_file is None:
        env_config = os.environ.get(ENV_CONFIG_PATH)
        config_file = Path(env_config) if env_config else DEFAULT_CONFIG_PATH

    config = read_config_file(config_file)
    for key in ("WorldDatabaseInfo", "world_database_info", "WORLD_DATABASE_INFO"):
        if key in config:
            return DatabaseDsn.parse(config[key])

    msg = (
        f"No WorldDatabaseInfo in {config_file}. "
        f"Set {ENV_WORLD_DATABASE_INFO} or pass --dsn."
    )
    raise ValueError(msg)
