"""Starter-zone boxes derived from playercreateinfo for trainer snapshot extracts."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.kits import ALLIANCE_RACES, HORDE_RACES

# Matches trainer emitter / prototype scripts (docs/temp).
STARTER_SPAWN_BOX_RADIUS = 280

# WotLK race starter continents only (exclude DK Ebon Hold and other instances).
STARTER_MAPS: frozenset[int] = frozenset({0, 1, 530})


@dataclass(frozen=True, slots=True)
class StarterZoneBox:
    map_id: int
    zone_id: int
    cx: float
    cy: float
    faction: str  # "A" or "H"


def _faction_for_race(race_id: int) -> str:
    if race_id in ALLIANCE_RACES:
        return "A"
    if race_id in HORDE_RACES:
        return "H"
    msg = f"Race {race_id} has no starter faction"
    raise ValueError(msg)


def build_starter_zone_boxes(playercreateinfo: list[dict]) -> tuple[StarterZoneBox, ...]:
    """One anchor box per (map, zone) from stock-style starter spawns."""
    grouped: dict[tuple[int, int], StarterZoneBox] = {}
    for row in playercreateinfo:
        race_id = int(row["race"])
        class_id = int(row["class"])
        map_id = int(row["map"])
        zone_id = int(row["zone"])
        if class_id == 6 or map_id not in STARTER_MAPS:
            continue
        key = (map_id, zone_id)
        if key in grouped:
            continue
        grouped[key] = StarterZoneBox(
            map_id=map_id,
            zone_id=zone_id,
            cx=float(row["x"]),
            cy=float(row["y"]),
            faction=_faction_for_race(race_id),
        )
    return tuple(sorted(grouped.values(), key=lambda box: (box.map_id, box.zone_id)))


def spawn_in_starter_box(
    *,
    map_id: int,
    x: float,
    y: float,
    boxes: tuple[StarterZoneBox, ...],
    radius: float = STARTER_SPAWN_BOX_RADIUS,
) -> bool:
    return any(
        map_id == box.map_id
        and abs(x - box.cx) <= radius
        and abs(y - box.cy) <= radius
        for box in boxes
    )


def starter_zone_sql_clause(
    boxes: tuple[StarterZoneBox, ...],
    *,
    map_column: str = "c.map",
    x_column: str = "c.position_x",
    y_column: str = "c.position_y",
    radius: float = STARTER_SPAWN_BOX_RADIUS,
) -> tuple[str, list]:
    if not boxes:
        msg = "No starter zone boxes to filter against"
        raise ValueError(msg)

    parts: list[str] = []
    params: list[float | int] = []
    for box in boxes:
        parts.append(
            f"({map_column} = %s AND {x_column} BETWEEN %s AND %s "
            f"AND {y_column} BETWEEN %s AND %s)"
        )
        params.extend(
            [
                box.map_id,
                box.cx - radius,
                box.cx + radius,
                box.cy - radius,
                box.cy + radius,
            ]
        )
    return " OR ".join(parts), params
