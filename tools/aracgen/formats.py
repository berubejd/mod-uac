"""DBC format strings aligned with AzerothCore DBCfmt.h where applicable."""

# Client-only; inferred from record layout (2 × uint8).
CHAR_BASE_INFO = "bb"

# DBCStores.cpp / DBCfmt.h
SKILL_RACE_CLASS_INFO = "diiiixix"

# DBCfmt.h
CHAR_START_OUTFIT = (
    "dbbbXiiiiiiiiiiiiiiiiiiiiiiiixxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
)
