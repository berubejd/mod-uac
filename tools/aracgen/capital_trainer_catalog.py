"""Capital-city geography for the snapshot-driven capital trainer pass (Phase 2c).

Starter-zone trainers cover levels ~1-10; a new combo then hits a wall at its
*home capital* if that capital never trained the class in stock. The capital
pass in emit_trainers.py closes that gap the same way the starter pass does:
it reads captured world data (see snapshot ``capital_trainers``) to find which
classes each capital already trains, which full trainer NPC to reuse, and where
to anchor -- nothing about entries, coverage, or coordinates is hardcoded.

The only thing curated here is *geography*, which has no data source (capitals
are not in ``playercreateinfo`` the way starter zones are): each capital's map,
center, capture radius, faction, and which races call it home. This mirrors the
starter zones' ``STARTER_ZONE_LABELS``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapitalZone:
    label: str
    map_id: int
    cx: float
    cy: float
    radius: float  # half-extent of the square capture/classify box (yards)
    faction: str  # "A" | "H"
    home_races: tuple[int, ...]


# Race ids: Human 1, Orc 2, Dwarf 3, Night Elf 4, Undead 5, Tauren 6, Gnome 7,
# Troll 8, Blood Elf 10, Draenei 11. Radii are tuned to enclose each city's
# trainer district without bleeding into adjacent zones (validated by the
# capital-gap test, which asserts the emitter reproduces the audited gap set).
CAPITAL_ZONES: tuple[CapitalZone, ...] = (
    CapitalZone("Stormwind", 0, -8850.0, 600.0, 700.0, "A", (1,)),
    CapitalZone("Ironforge", 0, -4830.0, -1090.0, 600.0, "A", (3, 7)),
    CapitalZone("Darnassus", 1, 9950.0, 2280.0, 800.0, "A", (4,)),
    CapitalZone("Exodar", 530, -3965.0, -11653.0, 500.0, "A", (11,)),
    CapitalZone("Orgrimmar", 1, 1600.0, -4400.0, 700.0, "H", (2, 8)),
    CapitalZone("Undercity", 0, 1590.0, 240.0, 450.0, "H", (5,)),
    CapitalZone("ThunderBluff", 1, -1200.0, 130.0, 450.0, "H", (6,)),
    CapitalZone("Silvermoon", 530, 9500.0, -7300.0, 500.0, "H", (10,)),
)


def capital_zone_sql_clause(
    zones: tuple[CapitalZone, ...],
    *,
    map_column: str = "c.map",
    x_column: str = "c.position_x",
    y_column: str = "c.position_y",
) -> tuple[str, list[float | int]]:
    """OR of per-capital square boxes (each with its own radius)."""
    parts: list[str] = []
    params: list[float | int] = []
    for zone in zones:
        parts.append(
            f"({map_column} = %s AND {x_column} BETWEEN %s AND %s "
            f"AND {y_column} BETWEEN %s AND %s)"
        )
        params.extend(
            [zone.map_id, zone.cx - zone.radius, zone.cx + zone.radius,
             zone.cy - zone.radius, zone.cy + zone.radius]
        )
    return " OR ".join(parts), params


def classify_capital(map_id: int, x: float, y: float) -> CapitalZone | None:
    """Return the capital whose box contains the point (boxes do not overlap)."""
    for zone in CAPITAL_ZONES:
        if (
            map_id == zone.map_id
            and abs(x - zone.cx) <= zone.radius
            and abs(y - zone.cy) <= zone.radius
        ):
            return zone
    return None
