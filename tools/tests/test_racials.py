from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.emit_racials import (
    RacialAbilityEmitter,
    _baseline_rows,
    compute_racial_overlay,
    render_install_sql,
    render_uninstall_sql,
)
from aracgen.matrix import ComboMatrix
from aracgen.racial_catalog import RACIAL_BAR_SPELLS, RACIAL_GRANTS
from aracgen.snapshot import load_snapshot
from aracgen.sources import ZipDbcSource

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "cache" / "client-data-v19.zip"
SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshot"
CHECKED_IN_INSTALL = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "sql"
    / "db-world"
    / "mod_uac_skilllineability_dbc.sql"
)
CHECKED_IN_UNINSTALL = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "sql"
    / "db-uninstall"
    / "mod_uac_skilllineability_dbc_uninstall.sql"
)

# Racial skill line per playable race (stock playercreateinfo_skills grants).
RACIAL_SKILL_BY_RACE = {
    1: 754,
    2: 125,
    3: 101,
    4: 126,
    5: 220,
    6: 124,
    7: 753,
    8: 733,
    10: 756,
    11: 760,
}


@pytest.fixture(scope="session")
def ability_table():
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    return ZipDbcSource(DATA_ZIP).load_skill_line_ability()


@pytest.fixture(scope="session")
def stock_matrix() -> ComboMatrix:
    return ComboMatrix.stock()


def test_all_grants_target_new_combos(stock_matrix: ComboMatrix) -> None:
    for grant in RACIAL_GRANTS:
        assert stock_matrix.is_new(grant.race_id, grant.class_id), grant


def test_grants_are_not_covered_by_stock(ability_table) -> None:
    rows = _baseline_rows(ability_table)
    for grant in RACIAL_GRANTS:
        covered = any(
            row.skill_id == grant.skill_id
            and row.spell_id == grant.spell_id
            and row.covers(grant.race_id, grant.class_id)
            for row in rows
        )
        assert not covered, grant


def test_every_class_masked_racial_gap_is_filled(
    ability_table,
    stock_matrix: ComboMatrix,
) -> None:
    """Every named class-variant racial reaches every new combo after the overlay.

    Groups variants by spell "family" via SupercededBySpell-independent
    heuristic: rows on the racial skill line sharing a nonzero ClassMask
    pattern are treated as one ability family when any stock class of the
    race learns one of them.
    """
    baseline = _baseline_rows(ability_table)
    result = compute_racial_overlay(ability_table)
    combined = baseline + list(result.rows)

    # Spell IDs per (race, ability family): variants of the same racial are the
    # class-masked rows on that race's skill line. A new combo is fine when it
    # matches at least one variant of each family that stock classes receive.
    families = {
        2: [
            {20572, 33697, 33702},  # Blood Fury
            {21563, 20575, 20576, 54562, 65222},  # Command (stock 21563 covers new combos)
        ],
        4: [{21009}],  # Elusiveness
        10: [{25046, 28730, 50613}],  # Arcane Torrent
        11: [
            {28880, 59542, 59543, 59544, 59545, 59547, 59548},  # Gift of the Naaru
            {6562, 28878},  # Heroic/Inspiring Presence
            {59221, 59535, 59536, 59538, 59539, 59540, 59541},  # Shadow Resistance
        ],
    }

    for race_id, class_id in sorted(stock_matrix.new_combos):
        skill_id = RACIAL_SKILL_BY_RACE[race_id]
        for family in families.get(race_id, []):
            matched = any(
                row.skill_id == skill_id
                and row.spell_id in family
                and row.covers(race_id, class_id)
                for row in combined
            )
            assert matched, (race_id, class_id, sorted(family))


def test_unmasked_racials_reach_new_combos_without_overlay(
    ability_table,
    stock_matrix: ComboMatrix,
) -> None:
    # Stoneform (dwarf) and Will of the Forsaken (undead) are class-unmasked;
    # the reported working combos never needed overlay rows.
    rows = _baseline_rows(ability_table)
    for race_id, spell_id in ((3, 20594), (5, 7744)):
        skill_id = RACIAL_SKILL_BY_RACE[race_id]
        new_classes = [c for r, c in stock_matrix.new_combos if r == race_id]
        assert new_classes
        for class_id in new_classes:
            assert any(
                row.skill_id == skill_id
                and row.spell_id == spell_id
                and row.covers(race_id, class_id)
                for row in rows
            )


def test_overlay_ids_start_above_baseline(ability_table) -> None:
    result = compute_racial_overlay(ability_table)
    assert result.rows
    assert min(result.overlay_ids) == result.dbc_max_id + 1


def test_overlay_respects_db_max_id(ability_table) -> None:
    result = compute_racial_overlay(ability_table, db_max_id=30000)
    assert min(result.overlay_ids) == 30001


def test_overlay_is_deterministic(ability_table) -> None:
    first = compute_racial_overlay(ability_table)
    second = compute_racial_overlay(ability_table)
    assert first.rows == second.rows


def test_overlay_clones_template_fields(ability_table) -> None:
    baseline = _baseline_rows(ability_table)
    result = compute_racial_overlay(ability_table)
    by_spell = {}
    for row in baseline:
        by_spell.setdefault((row.skill_id, row.spell_id), row)
    for row in result.rows:
        template = by_spell[(row.skill_id, row.spell_id)]
        # AcquireMethod and skill-rank fields must carry over verbatim.
        assert row.values[7:] == template.values[7:]


def test_bar_spells_match_grants() -> None:
    granted = {(g.race_id, g.class_id, g.spell_id) for g in RACIAL_GRANTS}
    for (race_id, class_id), spell_id in RACIAL_BAR_SPELLS.items():
        assert (race_id, class_id, spell_id) in granted


def test_install_sql_shape(ability_table) -> None:
    result = compute_racial_overlay(ability_table)
    sql = render_install_sql(result)
    assert "INSERT INTO `skilllineability_dbc`" in sql
    assert "`AcquireMethod`" in sql
    assert sql.count("INSERT INTO") == len(result.rows)
    # Reapply-safe: the AC updater re-runs changed files against a populated table.
    delete_stmt = sql.index("DELETE FROM `skilllineability_dbc`")
    assert delete_stmt < sql.index("INSERT INTO")


def test_uninstall_sql_deletes_exact_ids(ability_table) -> None:
    result = compute_racial_overlay(ability_table)
    sql = render_uninstall_sql(result)
    assert "DELETE FROM `skilllineability_dbc` WHERE `ID` IN (" in sql
    for record_id in result.overlay_ids:
        assert str(record_id) in sql


def test_emitter_uses_ddl_fallback_when_snapshot_lacks_table(ability_table) -> None:
    try:
        snapshot = load_snapshot(snapshot_dir=SNAPSHOT_DIR)
    except FileNotFoundError:
        pytest.skip("baked world snapshot not present")
    emitter = RacialAbilityEmitter(ability_table, snapshot=snapshot)
    install = emitter.render_install()
    assert "INSERT INTO `skilllineability_dbc`" in install


def test_install_sql_matches_checked_in_artifact(ability_table) -> None:
    if not CHECKED_IN_INSTALL.is_file():
        pytest.skip(f"Checked-in SQL not found: {CHECKED_IN_INSTALL}")
    try:
        snapshot = load_snapshot(snapshot_dir=SNAPSHOT_DIR)
    except FileNotFoundError:
        snapshot = None
    result = compute_racial_overlay(ability_table)
    generated = render_install_sql(result, snapshot=snapshot)
    assert generated == CHECKED_IN_INSTALL.read_text(encoding="utf-8")


def test_uninstall_sql_matches_checked_in_artifact(ability_table) -> None:
    if not CHECKED_IN_UNINSTALL.is_file():
        pytest.skip(f"Checked-in SQL not found: {CHECKED_IN_UNINSTALL}")
    result = compute_racial_overlay(ability_table)
    generated = render_uninstall_sql(result)
    assert generated == CHECKED_IN_UNINSTALL.read_text(encoding="utf-8")
