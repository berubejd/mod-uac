from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.emit_skill import (
    SkillOverlayEmitter,
    SkillRaceClassInfoRow,
    _baseline_rows,
    _class_skills,
    _is_covered,
    compute_skill_overlay,
    render_install_sql,
    render_uninstall_sql,
)
from aracgen.matrix import ComboMatrix, mask_covers_race_class, race_bit
from aracgen.sources import ZipDbcSource

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "Data.zip"


@pytest.fixture(scope="session")
def canonical_skill_table():
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    return ZipDbcSource(DATA_ZIP).load_skill_race_class_info()


@pytest.fixture(scope="session")
def stock_matrix() -> ComboMatrix:
    return ComboMatrix.stock()


def test_stock_matrix_has_38_new_combos(stock_matrix: ComboMatrix) -> None:
    assert len(stock_matrix.new_combos) == 38
    assert len(stock_matrix.existing) == 62
    assert stock_matrix.is_new(6, 8)  # Tauren Mage
    assert not stock_matrix.is_new(1, 8)  # Human Mage exists


def test_mask_covers_all_races_when_zero() -> None:
    assert mask_covers_race_class(0, 128, 6, 8)


def test_overlay_ids_start_above_baseline(
    canonical_skill_table,
    stock_matrix: ComboMatrix,
) -> None:
    result = compute_skill_overlay(canonical_skill_table, stock_matrix)
    assert result.rows
    assert result.dbc_max_id == 970
    assert result.base_max_id == 970
    assert min(row.record_id for row in result.rows) == result.base_max_id + 1


def test_overlay_respects_db_max_id(
    canonical_skill_table,
    stock_matrix: ComboMatrix,
) -> None:
    result = compute_skill_overlay(canonical_skill_table, stock_matrix, db_max_id=1200)
    assert result.base_max_id == 1200
    assert min(row.record_id for row in result.rows) == 1201


def test_overlay_is_deterministic(
    canonical_skill_table,
    stock_matrix: ComboMatrix,
) -> None:
    first = compute_skill_overlay(canonical_skill_table, stock_matrix)
    second = compute_skill_overlay(canonical_skill_table, stock_matrix)
    assert first.overlay_ids == second.overlay_ids
    assert first.rows == second.rows


def test_overlay_covers_all_new_combo_skills(
    canonical_skill_table,
    stock_matrix: ComboMatrix,
) -> None:
    baseline = _baseline_rows(canonical_skill_table)
    result = compute_skill_overlay(canonical_skill_table, stock_matrix)
    combined = baseline + list(result.rows)
    class_skills = _class_skills(baseline, stock_matrix.existing)

    for race_id, class_id in stock_matrix.new_combos:
        for skill_id in class_skills.get(class_id, ()):
            assert _is_covered(combined, skill_id, race_id, class_id)


def test_overlay_merges_races_for_same_template(
    canonical_skill_table,
    stock_matrix: ComboMatrix,
) -> None:
    result = compute_skill_overlay(canonical_skill_table, stock_matrix)
    # 322 raw missing pairs collapse to 37 merged rows on canonical baseline.
    assert len(result.rows) == 37


def test_install_sql_shape(canonical_skill_table, stock_matrix: ComboMatrix) -> None:
    result = compute_skill_overlay(canonical_skill_table, stock_matrix)
    sql = render_install_sql(result)
    assert "INSERT INTO `skillraceclassinfo_dbc`" in sql
    assert "`SkillTierID`" in sql
    assert sql.count("INSERT INTO") == len(result.rows)


def test_uninstall_sql_deletes_exact_ids(canonical_skill_table, stock_matrix: ComboMatrix) -> None:
    result = compute_skill_overlay(canonical_skill_table, stock_matrix)
    sql = render_uninstall_sql(result)
    assert "DELETE FROM `skillraceclassinfo_dbc` WHERE `ID` IN (" in sql
    for record_id in result.overlay_ids:
        assert str(record_id) in sql
    assert " >= " not in sql


def test_emitter_end_to_end(canonical_skill_table) -> None:
    emitter = SkillOverlayEmitter(canonical_skill_table)
    result = emitter.compute()
    install = emitter.render_install(result)
    uninstall = emitter.render_uninstall(result)
    assert install.count("INSERT INTO") == len(result.rows)
    assert "DELETE FROM `skillraceclassinfo_dbc` WHERE `ID` IN (" in uninstall
    for record_id in result.overlay_ids:
        assert str(record_id) in uninstall


def test_overlay_row_with_race_mask() -> None:
    row = SkillRaceClassInfoRow(
        record_id=1,
        skill_id=6,
        race_mask=0,
        class_mask=128,
        flags=0,
        min_level=0,
        skill_tier_id=1040,
        skill_cost_index=0,
    )
    updated = row.with_race_mask(971, race_bit(6))
    assert updated.record_id == 971
    assert updated.race_mask == race_bit(6)
    assert updated.skill_id == 6
