"""Class-variant racial ability grants for new race/class combos.

Most racials carry ``ClassMask = 0`` in SkillLineAbility.dbc and apply to every
class of the race. Four do not — Blood Fury, Elusiveness, Arcane Torrent, and
the Draenei kit (Gift of the Naaru / Heroic Presence / Shadow Resistance) ship
one spell variant per stock class. New combos match none of those rows, so the
character reaches max level with no racial at all. This catalog assigns each
affected combo an existing 3.3.5 spell variant, following Blizzard's later
class rules where precedent exists:

- Blood Fury (Cataclysm Orc Mage precedent): casters get the spell-power
  variant 33702, hybrids get the AP+SP variant 33697 like shaman/monk.
- Elusiveness: Cataclysm-era Night Elves have it on every class (21009).
- Arcane Torrent: Cataclysm minted a rage variant (69179) for BE Warrior that
  does not exist in the 3.3.5 client, so warrior shares the mana variant 28730
  with the wotlk mana users; the AoE silence — the meaningful half — is
  identical on every variant.
- Gift of the Naaru: retail unified all classes onto the base spell 28880
  (modern Draenei Rogues use it), and since 3.0.2 every variant heals from
  max(AP, SP), so 28880 is faithful for the three new Draenei classes.
  Presence/Shadow Resistance passives follow the stock melee/caster split.
"""

from __future__ import annotations

from dataclasses import dataclass

ORC_RACIAL_SKILL = 125
NIGHT_ELF_RACIAL_SKILL = 126
BLOOD_ELF_RACIAL_SKILL = 756
DRAENEI_RACIAL_SKILL = 760


@dataclass(frozen=True, slots=True)
class RacialGrant:
    race_id: int
    class_id: int
    skill_id: int
    spell_id: int
    ability: str
    on_bar: bool = False


RACIAL_GRANTS: tuple[RacialGrant, ...] = (
    # Orc: Blood Fury (AP+SP hybrid 33697 / spell-power 33702).
    RacialGrant(2, 2, ORC_RACIAL_SKILL, 33697, "Blood Fury (AP+SP)", on_bar=True),
    RacialGrant(2, 5, ORC_RACIAL_SKILL, 33702, "Blood Fury (spell power)", on_bar=True),
    RacialGrant(2, 8, ORC_RACIAL_SKILL, 33702, "Blood Fury (spell power)", on_bar=True),
    RacialGrant(2, 11, ORC_RACIAL_SKILL, 33697, "Blood Fury (AP+SP)", on_bar=True),
    # Night Elf: Elusiveness passive.
    RacialGrant(4, 2, NIGHT_ELF_RACIAL_SKILL, 21009, "Elusiveness"),
    RacialGrant(4, 7, NIGHT_ELF_RACIAL_SKILL, 21009, "Elusiveness"),
    RacialGrant(4, 8, NIGHT_ELF_RACIAL_SKILL, 21009, "Elusiveness"),
    RacialGrant(4, 9, NIGHT_ELF_RACIAL_SKILL, 21009, "Elusiveness"),
    # Blood Elf: Arcane Torrent (mana variant; silence works for all).
    RacialGrant(10, 1, BLOOD_ELF_RACIAL_SKILL, 28730, "Arcane Torrent (mana)", on_bar=True),
    RacialGrant(10, 7, BLOOD_ELF_RACIAL_SKILL, 28730, "Arcane Torrent (mana)", on_bar=True),
    RacialGrant(10, 11, BLOOD_ELF_RACIAL_SKILL, 28730, "Arcane Torrent (mana)", on_bar=True),
    # Draenei Rogue: melee kit.
    RacialGrant(11, 4, DRAENEI_RACIAL_SKILL, 28880, "Gift of the Naaru", on_bar=True),
    RacialGrant(11, 4, DRAENEI_RACIAL_SKILL, 6562, "Heroic Presence (melee/ranged hit)"),
    RacialGrant(11, 4, DRAENEI_RACIAL_SKILL, 59221, "Shadow Resistance"),
    # Draenei Warlock: caster kit (mage-variant Shadow Resistance).
    RacialGrant(11, 9, DRAENEI_RACIAL_SKILL, 28880, "Gift of the Naaru", on_bar=True),
    RacialGrant(11, 9, DRAENEI_RACIAL_SKILL, 28878, "Heroic Presence (spell hit)"),
    RacialGrant(11, 9, DRAENEI_RACIAL_SKILL, 59541, "Shadow Resistance"),
    # Draenei Druid: hybrid follows the stock shaman (caster presence) kit.
    RacialGrant(11, 11, DRAENEI_RACIAL_SKILL, 28880, "Gift of the Naaru", on_bar=True),
    RacialGrant(11, 11, DRAENEI_RACIAL_SKILL, 28878, "Heroic Presence (spell hit)"),
    RacialGrant(11, 11, DRAENEI_RACIAL_SKILL, 59540, "Shadow Resistance"),
)

# Active racial to place on the new combo's stripped racial bar slot; keeps
# kits.py action bars in lockstep with the skilllineability_dbc grants.
RACIAL_BAR_SPELLS: dict[tuple[int, int], int] = {
    (grant.race_id, grant.class_id): grant.spell_id
    for grant in RACIAL_GRANTS
    if grant.on_bar
}
