"""Load stock AzerothCore playercreateinfo kit data from bundled SQL snapshots."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

STOCK_SQL_DIR = Path(__file__).resolve().parents[2] / "data" / "stock" / "db_world"

_FLOAT = r"-?\d+(?:\.\d+)?"


@dataclass(frozen=True, slots=True)
class SpawnInfo:
    map_id: int
    zone_id: int
    x: float
    y: float
    z: float
    orientation: float


@dataclass(frozen=True, slots=True)
class ActionEntry:
    button: int
    action: int
    action_type: int


@dataclass(slots=True)
class StockKitStore:
    spawns: dict[tuple[int, int], SpawnInfo] = field(default_factory=dict)
    actions: dict[tuple[int, int], list[ActionEntry]] = field(default_factory=dict)

    @classmethod
    def load(cls, sql_dir: Path | None = None) -> StockKitStore:
        root = sql_dir or STOCK_SQL_DIR
        store = cls()
        store._load_spawns(root / "playercreateinfo.sql")
        store._load_actions(root / "playercreateinfo_action.sql")
        return store

    def _load_spawns(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(
            rf"\((\d+),(\d+),(\d+),(\d+),({_FLOAT}),({_FLOAT}),({_FLOAT}),({_FLOAT})\)"
        )
        for match in pattern.finditer(text):
            race, class_id, map_id, zone_id, x, y, z, orient = match.groups()
            key = (int(race), int(class_id))
            self.spawns[key] = SpawnInfo(
                int(map_id), int(zone_id), float(x), float(y), float(z), float(orient)
            )

    def _load_actions(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(r"\((\d+),(\d+),(\d+),(\d+),(\d+)\)")
        for match in pattern.finditer(text):
            race, class_id, button, action, action_type = (int(v) for v in match.groups())
            key = (race, class_id)
            self.actions.setdefault(key, []).append(
                ActionEntry(button=button, action=action, action_type=action_type)
            )


def spawn_for_race(store: StockKitStore, race_id: int) -> SpawnInfo:
    """Location from any stock combo of this race (lowest class id wins)."""
    matches = [
        (class_id, store.spawns[(race_id, class_id)])
        for class_id in _classes_for_race(store, race_id)
    ]
    if not matches:
        msg = f"No stock spawn for race {race_id}"
        raise ValueError(msg)
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def _classes_for_race(store: StockKitStore, race_id: int) -> list[int]:
    return sorted(class_id for race, class_id in store.spawns if race == race_id)
