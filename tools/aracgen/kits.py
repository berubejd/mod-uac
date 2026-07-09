"""Resolve class kits and spawn locations for new race/class combos."""

from __future__ import annotations

from dataclasses import dataclass, field

from aracgen.charstartoutfit_export import (
    OutfitRecord,
    clone_reference_outfits,
    outfit_id_floor,
    stock_outfit_covers,
)
from aracgen.dbc import DbcTable
from aracgen.item_prototypes import ItemPrototypeStore
from aracgen.matrix import ComboMatrix
from aracgen.racial_catalog import RACIAL_BAR_SPELLS
from aracgen.starter_skills import StarterSkillRow, compute_starter_skills
from aracgen.stock_loader import ActionEntry, SpawnInfo, StockKitStore, spawn_for_race

ALLIANCE_RACES: frozenset[int] = frozenset({1, 3, 4, 7, 11})
HORDE_RACES: frozenset[int] = frozenset({2, 5, 6, 8, 10})

# Death Knight starter abilities occupy bar slots that overlap racial detection.
DK_ABILITY_BUTTONS: frozenset[int] = frozenset({0, 1, 2, 3, 4, 5, 6})
DK_ABILITY_SPELLS: frozenset[int] = frozenset({49576, 45477, 45462, 45902, 47541, 50613})

# Action bar slots commonly used for racials in stock playercreateinfo_action.
RACIAL_BUTTON_SLOTS: frozenset[int] = frozenset({2, 3, 9, 10, 11, 74, 75, 82})


@dataclass(frozen=True, slots=True)
class ComboKit:
    race_id: int
    class_id: int
    spawn: SpawnInfo
    actions: tuple[ActionEntry, ...]
    outfit_records: tuple[OutfitRecord, ...]
    skills: tuple[StarterSkillRow, ...]


@dataclass(frozen=True, slots=True)
class RacialIndex:
    """Racial action metadata derived from stock playercreateinfo_action."""

    universal_class_bar: dict[tuple[int, int], int]
    spell_ids_by_race: dict[int, frozenset[int]]
    spell_by_race_class: dict[tuple[int, int], int]
    spell_frequency_by_race: dict[int, dict[int, int]]


@dataclass(slots=True)
class CanonicalKitResolver:
    matrix: ComboMatrix
    store: StockKitStore
    outfit: DbcTable
    item_prototypes: ItemPrototypeStore
    db_max_outfit_id: int = 0
    _racial_index: RacialIndex = field(init=False)
    _reference_race_cache: dict[tuple[int, str], int] = field(default_factory=dict, init=False)
    _next_outfit_id: int = field(init=False)
    _dbc_max_outfit_id: int = field(init=False)

    def __post_init__(self) -> None:
        self._racial_index = _build_racial_index(self.store)
        dbc_max, _db_max, next_id = outfit_id_floor(self.outfit, self.db_max_outfit_id)
        self._dbc_max_outfit_id = dbc_max
        self._next_outfit_id = next_id

    @property
    def dbc_max_outfit_id(self) -> int:
        return self._dbc_max_outfit_id

    def resolve(self, race_id: int, class_id: int) -> ComboKit:
        if not self.matrix.is_new(race_id, class_id):
            msg = f"Combo ({race_id}, {class_id}) is not a new combo"
            raise ValueError(msg)

        ref_race = self.reference_race_for_class(class_id, race_id)
        spawn = spawn_for_race(self.store, race_id)
        actions = self._compose_actions(race_id, class_id, ref_race)
        outfit_records: tuple[OutfitRecord, ...] = ()
        if not stock_outfit_covers(self.outfit, race_id, class_id):
            outfit_records, self._next_outfit_id = clone_reference_outfits(
                self.outfit,
                race_id=race_id,
                class_id=class_id,
                ref_race=ref_race,
                next_record_id=self._next_outfit_id,
            )
        item_ids = frozenset(
            item_id
            for record in outfit_records
            for item_id in record.positive_item_ids()
        )
        skills = compute_starter_skills(
            race_id,
            class_id,
            item_ids,
            self.store,
            self.item_prototypes,
            ref_race=ref_race,
        )
        return ComboKit(
            race_id=race_id,
            class_id=class_id,
            spawn=spawn,
            actions=actions,
            outfit_records=outfit_records,
            skills=skills,
        )

    def resolve_all(self) -> list[ComboKit]:
        return [self.resolve(race, class_id) for race, class_id in sorted(self.matrix.new_combos)]

    def reference_race_for_class(self, class_id: int, target_race: int) -> int:
        faction_name = "alliance" if target_race in ALLIANCE_RACES else "horde"
        cache_key = (class_id, faction_name)
        if cache_key in self._reference_race_cache:
            return self._reference_race_cache[cache_key]

        faction = _faction_of(target_race)
        candidates = sorted(
            race
            for race, combo_class in self.matrix.existing
            if combo_class == class_id and race in faction
        )
        if not candidates:
            msg = f"No stock reference for class {class_id} in faction {faction_name}"
            raise ValueError(msg)
        ref = candidates[0]
        self._reference_race_cache[cache_key] = ref
        return ref

    def _compose_actions(
        self, race_id: int, class_id: int, ref_race: int
    ) -> tuple[ActionEntry, ...]:
        ref_key = (ref_race, class_id)
        if ref_key not in self.store.actions:
            msg = f"No stock actions for reference combo {ref_key}"
            raise ValueError(msg)

        index = self._racial_index

        merged: dict[int, ActionEntry] = {}
        stripped_racial_buttons: list[int] = []

        for entry in self.store.actions[ref_key]:
            if _is_ref_racial_entry(entry, class_id, ref_race, index):
                stripped_racial_buttons.append(entry.button)
                continue
            merged[entry.button] = entry

        for button in sorted(set(stripped_racial_buttons)):
            if button in merged:
                continue
            spell = _resolve_racial_spell(race_id, class_id, index)
            merged[button] = ActionEntry(button, spell, 0)
            break

        return tuple(merged[button] for button in sorted(merged))


def _faction_of(race_id: int) -> frozenset[int]:
    if race_id in ALLIANCE_RACES:
        return ALLIANCE_RACES
    if race_id in HORDE_RACES:
        return HORDE_RACES
    msg = f"Race {race_id} is not in a known faction"
    raise ValueError(msg)


def _skip_action_for_racial_scan(class_id: int, entry: ActionEntry) -> bool:
    if class_id != 6:
        return False
    return entry.button in DK_ABILITY_BUTTONS or entry.action in DK_ABILITY_SPELLS


def _build_universal_class_bar(store: StockKitStore) -> dict[tuple[int, int], int]:
    """Class abilities that occupy the same racial bar slot for every stock race."""
    by_class_button: dict[tuple[int, int], dict[int, int]] = {}
    for (race_id, class_id), actions in store.actions.items():
        for entry in actions:
            if _skip_action_for_racial_scan(class_id, entry):
                continue
            if entry.button not in RACIAL_BUTTON_SLOTS:
                continue
            key = (class_id, entry.button)
            by_class_button.setdefault(key, {})[race_id] = entry.action
    return {
        key: next(iter(set(race_actions.values())))
        for key, race_actions in by_class_button.items()
        if len(race_actions) >= 2 and len(set(race_actions.values())) == 1
    }


def _build_racial_index(store: StockKitStore) -> RacialIndex:
    universal_class_bar = _build_universal_class_bar(store)
    spell_by_race_class: dict[tuple[int, int], int] = {}
    spell_ids_by_race: dict[int, set[int]] = {}
    spell_frequency_by_race: dict[int, dict[int, int]] = {}

    for (race_id, class_id), actions in store.actions.items():
        for entry in actions:
            if _skip_action_for_racial_scan(class_id, entry):
                continue
            if entry.button not in RACIAL_BUTTON_SLOTS:
                continue
            universal = universal_class_bar.get((class_id, entry.button))
            if universal is not None and entry.action == universal:
                continue
            spell_by_race_class[(race_id, class_id)] = entry.action
            spell_ids_by_race.setdefault(race_id, set()).add(entry.action)
            race_freq = spell_frequency_by_race.setdefault(race_id, {})
            race_freq[entry.action] = race_freq.get(entry.action, 0) + 1

    return RacialIndex(
        universal_class_bar=universal_class_bar,
        spell_ids_by_race={race: frozenset(spells) for race, spells in spell_ids_by_race.items()},
        spell_by_race_class=spell_by_race_class,
        spell_frequency_by_race=spell_frequency_by_race,
    )


def _is_ref_racial_entry(
    entry: ActionEntry,
    class_id: int,
    ref_race: int,
    index: RacialIndex,
) -> bool:
    if entry.action in index.spell_ids_by_race.get(ref_race, frozenset()):
        return True
    if entry.button not in RACIAL_BUTTON_SLOTS:
        return False
    universal = index.universal_class_bar.get((class_id, entry.button))
    return universal is None or entry.action != universal


def _resolve_racial_spell(race_id: int, class_id: int, index: RacialIndex) -> int:
    # Class-variant racials: match the skilllineability_dbc grant, not a stock
    # sibling's variant the character can never learn (e.g. warrior Blood Fury
    # on an orc mage's bar).
    if (race_id, class_id) in RACIAL_BAR_SPELLS:
        return RACIAL_BAR_SPELLS[(race_id, class_id)]
    if (race_id, class_id) in index.spell_by_race_class:
        return index.spell_by_race_class[(race_id, class_id)]
    frequencies = index.spell_frequency_by_race.get(race_id, {})
    if not frequencies:
        msg = f"No racial spell data for race {race_id}"
        raise ValueError(msg)
    repeated = {spell: count for spell, count in frequencies.items() if count >= 2}
    if len(repeated) == 1:
        return next(iter(repeated))
    if repeated:
        return max(repeated, key=repeated.get)
    if len(frequencies) == 1:
        return next(iter(frequencies))
    # Per-class variants (Draenei Gift of the Naaru, Orc Blood Fury ranks): use base rank.
    return min(frequencies)
