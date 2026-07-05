"""Starter-zone geography for class-quest tier classification."""

from __future__ import annotations

from aracgen.stock_loader import StockKitStore, spawn_for_race

# WotLK starter-zone continent buckets (zone IDs from stock playercreateinfo / quest areas).
EASTERN_KINGDOMS_ZONES: frozenset[int] = frozenset(
    {
        1,  # Dun Morogh
        12,  # Elwynn Forest
        85,  # Tirisfal Glades
        130,  # Silverpine Forest (referenced by some chains)
        1497,  # Undercity
        1519,  # Stormwind
        1537,  # Ironforge
        3430,  # Eversong Woods
        3487,  # Silvermoon
    }
)

KALIMDOR_ZONES: frozenset[int] = frozenset(
    {
        14,  # Durotar
        17,  # The Barrens
        141,  # Teldrassil
        1657,  # Darnassus
        215,  # Mulgore
        3524,  # Azuremyst Isle
        3526,  # Bloodmyst Isle (Draenei spawn)
        3557,  # The Exodar
    }
)


def continent_for_zone(zone_id: int) -> str:
    if zone_id in EASTERN_KINGDOMS_ZONES:
        return "ek"
    if zone_id in KALIMDOR_ZONES:
        return "kalimdor"
    msg = f"Unknown continent for zone {zone_id}"
    raise ValueError(msg)


def spawn_zone_for_race(store: StockKitStore, race_id: int) -> int:
    return spawn_for_race(store, race_id).zone_id


def quest_access_tier(target_zone_id: int, quest_zone_id: int) -> str:
    """A = same zone, B = same continent, C = cross-continent (spell grant fallback)."""
    if target_zone_id == quest_zone_id:
        return "A"
    if continent_for_zone(target_zone_id) == continent_for_zone(quest_zone_id):
        return "B"
    return "C"
