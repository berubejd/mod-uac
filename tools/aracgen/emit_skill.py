"""Emit skillraceclassinfo_dbc overlay SQL from SkillRaceClassInfo.dbc analysis."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from aracgen.dbc import DbcTable
from aracgen.formats import SKILL_RACE_CLASS_INFO
from aracgen.matrix import ComboMatrix, mask_covers_race_class, race_bit

# World DB columns aligned with skillraceclassinfo_dbc + SkillRaceClassInfofmt field order.
SKILL_RACE_CLASS_INFO_COLUMNS: tuple[str, ...] = (
    "ID",
    "SkillID",
    "RaceMask",
    "ClassMask",
    "Flags",
    "MinLevel",
    "SkillTierID",
    "SkillCostIndex",
)

# Format-char index for each column (see DBCfmt.h SkillRaceClassInfofmt = "diiiixix").
SKILL_RACE_CLASS_INFO_FIELD_INDEX: dict[str, int] = {
    name: index for index, name in enumerate(SKILL_RACE_CLASS_INFO_COLUMNS)
}


@dataclass(frozen=True, slots=True)
class SkillRaceClassInfoRow:
    record_id: int
    skill_id: int
    race_mask: int
    class_mask: int
    flags: int
    min_level: int
    skill_tier_id: int
    skill_cost_index: int

    @classmethod
    def from_dbc(cls, table: DbcTable, record_index: int) -> SkillRaceClassInfoRow:
        return cls(
            record_id=table.get_uint32(record_index, 0),
            skill_id=table.get_uint32(record_index, 1),
            race_mask=table.get_uint32(record_index, 2),
            class_mask=table.get_uint32(record_index, 3),
            flags=table.get_uint32(record_index, 4),
            min_level=table.get_uint32(record_index, 5),
            skill_tier_id=table.get_uint32(record_index, 6),
            skill_cost_index=table.get_uint32(record_index, 7),
        )

    def overlay_key(self) -> tuple[int, int, int, int, int, int]:
        """Merge key: same skill + class template can cover multiple new races."""
        return (
            self.skill_id,
            self.class_mask,
            self.flags,
            self.min_level,
            self.skill_tier_id,
            self.skill_cost_index,
        )

    def with_race_mask(self, record_id: int, race_mask: int) -> SkillRaceClassInfoRow:
        return SkillRaceClassInfoRow(
            record_id=record_id,
            skill_id=self.skill_id,
            race_mask=race_mask,
            class_mask=self.class_mask,
            flags=self.flags,
            min_level=self.min_level,
            skill_tier_id=self.skill_tier_id,
            skill_cost_index=self.skill_cost_index,
        )


@dataclass(frozen=True, slots=True)
class SkillOverlayResult:
    dbc_max_id: int
    db_max_id: int
    rows: tuple[SkillRaceClassInfoRow, ...]

    @property
    def base_max_id(self) -> int:
        """Highest ID already occupied before overlay assignment."""
        return max(self.dbc_max_id, self.db_max_id)

    @property
    def overlay_ids(self) -> tuple[int, ...]:
        return tuple(row.record_id for row in self.rows)

    @property
    def id_range(self) -> tuple[int, int] | None:
        if not self.rows:
            return None
        ids = self.overlay_ids
        return min(ids), max(ids)


def _baseline_rows(table: DbcTable) -> list[SkillRaceClassInfoRow]:
    if table.format_str != SKILL_RACE_CLASS_INFO:
        msg = "Expected SkillRaceClassInfo.dbc table"
        raise ValueError(msg)
    return [SkillRaceClassInfoRow.from_dbc(table, i) for i in range(table.record_count)]


def _class_skills(
    rows: list[SkillRaceClassInfoRow],
    existing_combos: frozenset[tuple[int, int]],
) -> dict[int, set[int]]:
    """Skill IDs each class receives via rows that cover a stock combo."""
    by_class: dict[int, set[int]] = {}
    for race_id, class_id in existing_combos:
        class_skills = by_class.setdefault(class_id, set())
        for row in rows:
            if mask_covers_race_class(row.race_mask, row.class_mask, race_id, class_id):
                class_skills.add(row.skill_id)
    return by_class


def _is_covered(
    rows: list[SkillRaceClassInfoRow],
    skill_id: int,
    race_id: int,
    class_id: int,
) -> bool:
    return any(
        row.skill_id == skill_id
        and mask_covers_race_class(row.race_mask, row.class_mask, race_id, class_id)
        for row in rows
    )


def _find_template(
    rows: list[SkillRaceClassInfoRow],
    existing_combos: frozenset[tuple[int, int]],
    skill_id: int,
    class_id: int,
) -> SkillRaceClassInfoRow | None:
    """Pick the baseline row with lowest record ID, then lowest reference race ID."""
    candidates: list[tuple[int, int, SkillRaceClassInfoRow]] = []
    for race_id, combo_class in existing_combos:
        if combo_class != class_id:
            continue
        for row in rows:
            if row.skill_id == skill_id and mask_covers_race_class(
                row.race_mask, row.class_mask, race_id, class_id
            ):
                candidates.append((row.record_id, race_id, row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def compute_skill_overlay(
    table: DbcTable,
    matrix: ComboMatrix,
    db_max_id: int = 0,
) -> SkillOverlayResult:
    rows = _baseline_rows(table)
    dbc_max_id = max(row.record_id for row in rows)
    if db_max_id < 0:
        msg = f"db_max_id must be >= 0, got {db_max_id}"
        raise ValueError(msg)
    id_floor = max(dbc_max_id, db_max_id)
    class_skills = _class_skills(rows, matrix.existing)

    merged: dict[tuple[int, int, int, int, int, int], int] = defaultdict(int)
    for race_id, class_id in sorted(matrix.new_combos):
        for skill_id in class_skills.get(class_id, ()):
            if _is_covered(rows, skill_id, race_id, class_id):
                continue
            template = _find_template(rows, matrix.existing, skill_id, class_id)
            if template is None:
                msg = f"No template for skill {skill_id} class {class_id}"
                raise ValueError(msg)
            merged[template.overlay_key()] |= race_bit(race_id)

    overlay_rows: list[SkillRaceClassInfoRow] = []
    next_id = id_floor + 1
    for key in sorted(merged):
        skill_id, class_mask, flags, min_level, skill_tier_id, skill_cost_index = key
        template = SkillRaceClassInfoRow(
            record_id=0,
            skill_id=skill_id,
            race_mask=0,
            class_mask=class_mask,
            flags=flags,
            min_level=min_level,
            skill_tier_id=skill_tier_id,
            skill_cost_index=skill_cost_index,
        )
        overlay_rows.append(template.with_race_mask(next_id, merged[key]))
        next_id += 1

    return SkillOverlayResult(dbc_max_id=dbc_max_id, db_max_id=db_max_id, rows=tuple(overlay_rows))


def _sql_value(column: str, row: SkillRaceClassInfoRow) -> int:
    return {
        "ID": row.record_id,
        "SkillID": row.skill_id,
        "RaceMask": row.race_mask,
        "ClassMask": row.class_mask,
        "Flags": row.flags,
        "MinLevel": row.min_level,
        "SkillTierID": row.skill_tier_id,
        "SkillCostIndex": row.skill_cost_index,
    }[column]


def render_install_sql(result: SkillOverlayResult) -> str:
    if not result.rows:
        return (
            "-- mod-uac: no skillraceclassinfo_dbc overlay rows required for this baseline.\n"
        )

    columns = ", ".join(f"`{name}`" for name in SKILL_RACE_CLASS_INFO_COLUMNS)
    id_list = ", ".join(str(record_id) for record_id in result.overlay_ids)
    lines = [
        "-- mod-uac: skillraceclassinfo_dbc overlay (Unlock All Classes)",
        f"-- dbc max ID: {result.dbc_max_id}; db max ID: {result.db_max_id}",
        f"-- overlay IDs: {id_list}",
        "",
    ]
    for row in result.rows:
        values = ", ".join(str(_sql_value(col, row)) for col in SKILL_RACE_CLASS_INFO_COLUMNS)
        lines.append(f"INSERT INTO `skillraceclassinfo_dbc` ({columns}) VALUES ({values});")
    lines.append("")
    return "\n".join(lines)


def render_uninstall_sql(result: SkillOverlayResult) -> str:
    if not result.rows:
        return (
            "-- mod-uac: no skillraceclassinfo_dbc overlay rows to remove for this baseline.\n"
        )

    id_list = ", ".join(str(record_id) for record_id in result.overlay_ids)
    return "\n".join(
        [
            "-- mod-uac: revert skillraceclassinfo_dbc overlay",
            f"-- removes exactly these IDs: {id_list}",
            "",
            f"DELETE FROM `skillraceclassinfo_dbc` WHERE `ID` IN ({id_list});",
            "",
        ]
    )


class SkillOverlayEmitter:
    def __init__(
        self,
        table: DbcTable,
        matrix: ComboMatrix | None = None,
        db_max_id: int = 0,
    ) -> None:
        self.table = table
        self.matrix = matrix or ComboMatrix.stock()
        self.db_max_id = db_max_id

    def compute(self) -> SkillOverlayResult:
        return compute_skill_overlay(self.table, self.matrix, db_max_id=self.db_max_id)

    def render_install(self, result: SkillOverlayResult | None = None) -> str:
        return render_install_sql(result or self.compute())

    def render_uninstall(self, result: SkillOverlayResult | None = None) -> str:
        return render_uninstall_sql(result or self.compute())
