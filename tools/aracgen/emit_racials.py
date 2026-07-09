"""Emit skilllineability_dbc overlay SQL granting class-variant racials.

AzerothCore learns racial spells by walking SkillLineAbility rows for the
racial skill line and filtering on RaceMask AND ClassMask
(Player::learnSkillRewardedSpells). Rows added to the world table
``skilllineability_dbc`` are loaded on top of the client DBC — the same pure
SQL override mechanism as ``skillraceclassinfo_dbc`` — so no binary DBC edit
is needed and existing characters pick up the grants on next login.
"""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.dbc import DbcTable
from aracgen.formats import SKILL_LINE_ABILITY
from aracgen.matrix import class_bit, mask_covers_race_class, race_bit
from aracgen.racial_catalog import RACIAL_GRANTS, RacialGrant
from aracgen.schema_emit import render_insert
from aracgen.snapshot_model import Snapshot, TableSchema, parse_create_table_ddl

RACIAL_ABILITY_TABLE = "skilllineability_dbc"

# Columns follow AC base DDL and match the client DBC field order 1:1.
SKILL_LINE_ABILITY_COLUMNS: tuple[str, ...] = (
    "ID",
    "SkillLine",
    "Spell",
    "RaceMask",
    "ClassMask",
    "ExcludeRace",
    "ExcludeClass",
    "MinSkillLineRank",
    "SupercededBySpell",
    "AcquireMethod",
    "TrivialSkillLineRankHigh",
    "TrivialSkillLineRankLow",
    "CharacterPoints_1",
    "CharacterPoints_2",
)

# Bootstrap schema for snapshots captured before this table joined
# SCHEMA_TABLES; mirrors azerothcore data/sql/base/db_world/skilllineability_dbc.sql.
_AC_BASE_DDL = (
    "CREATE TABLE `skilllineability_dbc` (\n"
    + "\n".join(f"  `{name}` int NOT NULL DEFAULT '0'," for name in SKILL_LINE_ABILITY_COLUMNS)
    + "\n  PRIMARY KEY (`ID`)\n) ENGINE=InnoDB;"
)


@dataclass(frozen=True, slots=True)
class SkillLineAbilityRow:
    values: tuple[int, ...]

    @classmethod
    def from_dbc(cls, table: DbcTable, record_index: int) -> SkillLineAbilityRow:
        return cls(
            values=tuple(
                table.get_uint32(record_index, field)
                for field in range(len(SKILL_LINE_ABILITY_COLUMNS))
            )
        )

    @property
    def record_id(self) -> int:
        return self.values[0]

    @property
    def skill_id(self) -> int:
        return self.values[1]

    @property
    def spell_id(self) -> int:
        return self.values[2]

    @property
    def race_mask(self) -> int:
        return self.values[3]

    @property
    def class_mask(self) -> int:
        return self.values[4]

    def covers(self, race_id: int, class_id: int) -> bool:
        return mask_covers_race_class(self.race_mask, self.class_mask, race_id, class_id)

    def with_masks(self, record_id: int, race_mask: int, class_mask: int) -> SkillLineAbilityRow:
        replaced = (record_id, self.values[1], self.values[2], race_mask, class_mask)
        return SkillLineAbilityRow(values=replaced + self.values[5:])

    def logical_values(self) -> dict[str, int]:
        return dict(zip(SKILL_LINE_ABILITY_COLUMNS, self.values, strict=True))


@dataclass(frozen=True, slots=True)
class RacialOverlayResult:
    dbc_max_id: int
    db_max_id: int
    rows: tuple[SkillLineAbilityRow, ...]
    row_grants: tuple[tuple[RacialGrant, ...], ...]

    @property
    def overlay_ids(self) -> tuple[int, ...]:
        return tuple(row.record_id for row in self.rows)


def _baseline_rows(table: DbcTable) -> list[SkillLineAbilityRow]:
    if table.format_str != SKILL_LINE_ABILITY:
        msg = "Expected SkillLineAbility.dbc table"
        raise ValueError(msg)
    return [SkillLineAbilityRow.from_dbc(table, i) for i in range(table.record_count)]


def _template_row(
    rows: list[SkillLineAbilityRow],
    grant: RacialGrant,
) -> SkillLineAbilityRow:
    candidates = [
        row for row in rows if row.skill_id == grant.skill_id and row.spell_id == grant.spell_id
    ]
    if not candidates:
        msg = (
            f"No SkillLineAbility template for spell {grant.spell_id} "
            f"on skill {grant.skill_id} ({grant.ability})"
        )
        raise ValueError(msg)
    return min(candidates, key=lambda row: row.record_id)


def compute_racial_overlay(
    table: DbcTable,
    db_max_id: int = 0,
    grants: tuple[RacialGrant, ...] = RACIAL_GRANTS,
) -> RacialOverlayResult:
    rows = _baseline_rows(table)
    dbc_max_id = max(row.record_id for row in rows)
    if db_max_id < 0:
        msg = f"db_max_id must be >= 0, got {db_max_id}"
        raise ValueError(msg)

    # One overlay row per (race, skill, spell); classes merge into one mask.
    merged: dict[tuple[int, int, int], list[RacialGrant]] = {}
    for grant in grants:
        already_covered = any(
            row.skill_id == grant.skill_id
            and row.spell_id == grant.spell_id
            and row.covers(grant.race_id, grant.class_id)
            for row in rows
        )
        if already_covered:
            continue
        key = (grant.race_id, grant.skill_id, grant.spell_id)
        merged.setdefault(key, []).append(grant)

    overlay_rows: list[SkillLineAbilityRow] = []
    row_grants: list[tuple[RacialGrant, ...]] = []
    next_id = max(dbc_max_id, db_max_id) + 1
    for key in sorted(merged):
        race_id, _skill_id, _spell_id = key
        row_grant_list = merged[key]
        template = _template_row(rows, row_grant_list[0])
        class_mask = 0
        for grant in row_grant_list:
            class_mask |= class_bit(grant.class_id)
        overlay_rows.append(template.with_masks(next_id, race_bit(race_id), class_mask))
        row_grants.append(tuple(row_grant_list))
        next_id += 1

    return RacialOverlayResult(
        dbc_max_id=dbc_max_id,
        db_max_id=db_max_id,
        rows=tuple(overlay_rows),
        row_grants=tuple(row_grants),
    )


def _resolve_schema(snapshot: Snapshot | None) -> TableSchema:
    if snapshot is not None:
        try:
            return snapshot.schema(RACIAL_ABILITY_TABLE)
        except KeyError:
            pass
    return parse_create_table_ddl(_AC_BASE_DDL, RACIAL_ABILITY_TABLE)


def render_install_sql(
    result: RacialOverlayResult,
    *,
    snapshot: Snapshot | None = None,
) -> str:
    if not result.rows:
        return "-- mod-uac: no skilllineability_dbc racial grants required for this baseline.\n"

    schema = _resolve_schema(snapshot)
    id_list = ", ".join(str(record_id) for record_id in result.overlay_ids)
    lines = [
        "-- mod-uac: skilllineability_dbc racial ability grants (Unlock All Classes)",
        "-- Class-variant racials (Blood Fury, Elusiveness, Arcane Torrent, Draenei kit)",
        "-- for new combos; existing characters learn them on next login.",
        f"-- dbc max ID: {result.dbc_max_id}; db max ID: {result.db_max_id}",
        f"-- overlay IDs: {id_list}",
        "",
        "-- reapply-safe: clear mod-uac overlay IDs before insert",
        f"DELETE FROM `{RACIAL_ABILITY_TABLE}` WHERE `ID` IN ({id_list});",
        "",
    ]
    for row, grant_list in zip(result.rows, result.row_grants, strict=True):
        combos = ", ".join(f"({grant.race_id}, {grant.class_id})" for grant in grant_list)
        lines.append(f"-- {grant_list[0].ability} for {combos}")
        lines.append(render_insert(RACIAL_ABILITY_TABLE, schema, row.logical_values()))
    lines.append("")
    return "\n".join(lines)


def render_uninstall_sql(result: RacialOverlayResult) -> str:
    if not result.rows:
        return "-- mod-uac: no skilllineability_dbc racial grants to remove for this baseline.\n"

    id_list = ", ".join(str(record_id) for record_id in result.overlay_ids)
    return "\n".join(
        [
            "-- mod-uac: revert skilllineability_dbc racial ability grants",
            f"-- removes exactly these IDs: {id_list}",
            "",
            f"DELETE FROM `{RACIAL_ABILITY_TABLE}` WHERE `ID` IN ({id_list});",
            "",
        ]
    )


class RacialAbilityEmitter:
    def __init__(
        self,
        table: DbcTable,
        db_max_id: int = 0,
        snapshot: Snapshot | None = None,
    ) -> None:
        self.table = table
        self.db_max_id = db_max_id
        self.snapshot = snapshot

    def compute(self) -> RacialOverlayResult:
        return compute_racial_overlay(self.table, db_max_id=self.db_max_id)

    def render_install(self, result: RacialOverlayResult | None = None) -> str:
        return render_install_sql(result or self.compute(), snapshot=self.snapshot)

    def render_uninstall(self, result: RacialOverlayResult | None = None) -> str:
        return render_uninstall_sql(result or self.compute())
