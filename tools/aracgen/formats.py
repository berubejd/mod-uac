"""DBC format strings aligned with AzerothCore DBCfmt.h where applicable."""

# Client-only; inferred from record layout (2 × uint8).
CHAR_BASE_INFO = "bb"

# DBCStores.cpp / DBCfmt.h
SKILL_RACE_CLASS_INFO = "diiiixix"

# AC reads SkillLineAbility as "niiiixxiiiiixx"; we read every field as uint32
# so racial-grant rows can clone ExcludeRace/ExcludeClass/CharacterPoints into SQL.
SKILL_LINE_ABILITY = "niiiiiiiiiiiii"

# DBCfmt.h
CHAR_START_OUTFIT = (
    "dbbbXiiiiiiiiiiiiiiiiiiiiiiiixxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
)

# DBCfmt.h SpellEntryfmt — used for hunter pet spell-level patches (spell_dbc overlay).
SPELL = (
    "niiiiiiiiiiiixixiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiifxiiiiiiiiiiiiiiiiiiiiiiiiiiiifff"
    "iiiiiiiiiiiiiiiiiiiiifffiiiiiiiiiiiiiiifffiiiiiiiiiiiiiissssssssssssssssxssssssssssssssss"
    "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxiiiiiiiiiiixfffxxxiiiiixxfffxx"
)

SPELL_BASE_LEVEL_FIELD = 38
SPELL_SPELL_LEVEL_FIELD = 39
