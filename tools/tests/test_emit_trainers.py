from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.emit_trainers import (
    NativeTrainer,
    TrainerEmitResult,
    TrainerEmitter,
    compute_capital_trainer_result,
    compute_trainer_rows,
    compute_zone_gaps,
    load_trainer_overrides,
    native_trainers_in_box,
    place_beside_anchor,
    place_on_side,
    plan_anchor_placement,
    render_install_sql,
    render_uninstall_sql,
    render_worksheet,
    select_anchor,
)
from aracgen.matrix import ComboMatrix
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import (
    MOD_UAC_CAPITAL_GUID_MAX,
    MOD_UAC_CAPITAL_GUID_MIN,
    MOD_UAC_CREATURE_GUID_MAX,
    MOD_UAC_STARTER_GUID_MAX,
    Snapshot,
)
from aracgen.snapshot_zones import build_starter_zone_boxes
from aracgen.trainer_catalog import PLACEMENT_GAP, TRAINER_GUID_BASE, TrainerOverride

ROOT = Path(__file__).resolve().parents[2]
MINIMAL_FIXTURE = ROOT / "tools" / "tests" / "fixtures" / "world_snapshot_minimal.json"
CHECKED_IN_INSTALL = ROOT / "data" / "sql" / "db-world" / "mod_uac_starter_trainers.sql"
CHECKED_IN_UNINSTALL = (
    ROOT / "data" / "sql" / "db-uninstall" / "mod_uac_starter_trainers_uninstall.sql"
)
CHECKED_IN_CAPITAL_INSTALL = (
    ROOT / "data" / "sql" / "db-world" / "mod_uac_capital_trainers.sql"
)
CHECKED_IN_CAPITAL_UNINSTALL = (
    ROOT / "data" / "sql" / "db-uninstall" / "mod_uac_capital_trainers_uninstall.sql"
)
OVERRIDES_PATH = ROOT / "data" / "trainer_overrides.yaml"

GOLDEN_ENTRIES: dict[tuple[str, str], int] = {
    ("Northshire", "Hunter"): 895,
    ("Northshire", "Shaman"): 17089,
    ("Northshire", "Druid"): 3597,
    ("Coldridge", "Shaman"): 17089,
    ("Coldridge", "Druid"): 3597,
    ("Shadowglen", "Paladin"): 925,
    ("Shadowglen", "Shaman"): 17089,
    ("Shadowglen", "Mage"): 198,
    ("Shadowglen", "Warlock"): 459,
    ("AmmenVale", "Rogue"): 915,
    ("AmmenVale", "Warlock"): 459,
    ("AmmenVale", "Druid"): 3597,
    ("ValleyOfTrials", "Paladin"): 15280,
    ("ValleyOfTrials", "Druid"): 3060,
    ("CampNarache", "Paladin"): 15280,
    ("CampNarache", "Rogue"): 2122,
    ("CampNarache", "Priest"): 2123,
    ("CampNarache", "Mage"): 2124,
    ("CampNarache", "Warlock"): 2126,
    ("Deathknell", "Paladin"): 15280,
    ("Deathknell", "Hunter"): 3061,
    ("Deathknell", "Shaman"): 3062,
    ("Deathknell", "Druid"): 3060,
    ("Sunstrider", "Warrior"): 2119,
    ("Sunstrider", "Shaman"): 3062,
    ("Sunstrider", "Druid"): 3060,
}

GOLDEN_ANCHORS: dict[tuple[str, str], str] = {
    ("Northshire", "Hunter"): "Rogue",
    ("Northshire", "Shaman"): "Priest",
    ("Northshire", "Druid"): "Priest",
    ("Coldridge", "Shaman"): "Priest",
    ("Coldridge", "Druid"): "Priest",
    ("Shadowglen", "Paladin"): "Warrior",
    ("Shadowglen", "Shaman"): "Druid",
    ("Shadowglen", "Mage"): "Priest",
    ("Shadowglen", "Warlock"): "Priest",
    ("AmmenVale", "Rogue"): "Hunter",
    ("AmmenVale", "Warlock"): "Mage",
    ("AmmenVale", "Druid"): "Shaman",
    ("ValleyOfTrials", "Paladin"): "Warrior",
    ("ValleyOfTrials", "Druid"): "Shaman",
    ("CampNarache", "Paladin"): "Warrior",
    ("CampNarache", "Rogue"): "Hunter",
    ("CampNarache", "Priest"): "Shaman",
    ("CampNarache", "Mage"): "Shaman",
    ("CampNarache", "Warlock"): "Shaman",
    ("Deathknell", "Paladin"): "Warrior",
    ("Deathknell", "Hunter"): "Rogue",
    ("Deathknell", "Shaman"): "Priest",
    ("Deathknell", "Druid"): "Priest",
    ("Sunstrider", "Warrior"): "Paladin",
    ("Sunstrider", "Shaman"): "Priest",
    ("Sunstrider", "Druid"): "Priest",
}


@pytest.fixture(scope="session")
def minimal_snapshot() -> Snapshot:
    return Snapshot.load(MINIMAL_FIXTURE)


@pytest.fixture(scope="session")
def baked_snapshot() -> Snapshot:
    return load_snapshot()


@pytest.fixture(scope="session")
def stock_matrix() -> ComboMatrix:
    return ComboMatrix.stock()


@pytest.fixture(scope="session")
def trainer_result(baked_snapshot: Snapshot, stock_matrix: ComboMatrix):
    overrides = load_trainer_overrides(OVERRIDES_PATH)
    return compute_trainer_rows(baked_snapshot, stock_matrix, overrides=overrides)


@pytest.fixture(scope="session")
def capital_result(baked_snapshot: Snapshot, stock_matrix: ComboMatrix):
    overrides = load_trainer_overrides(OVERRIDES_PATH)
    return compute_capital_trainer_result(baked_snapshot, stock_matrix, overrides=overrides)


def test_starter_result_is_starter_only(trainer_result) -> None:
    assert len(trainer_result.rows) == 26
    assert all(not row.is_capital for row in trainer_result.rows)
    assert trainer_result.guid_base == TRAINER_GUID_BASE
    assert trainer_result.guid_max == TRAINER_GUID_BASE + 25
    assert trainer_result.band == (TRAINER_GUID_BASE, MOD_UAC_STARTER_GUID_MAX)
    assert trainer_result.kind == "starter"


def test_capital_result_is_capital_only(capital_result) -> None:
    assert len(capital_result.rows) == 14
    assert all(row.is_capital for row in capital_result.rows)
    assert capital_result.guid_base == MOD_UAC_CAPITAL_GUID_MIN
    assert capital_result.guid_max == MOD_UAC_CAPITAL_GUID_MIN + 13
    assert capital_result.band == (MOD_UAC_CAPITAL_GUID_MIN, MOD_UAC_CAPITAL_GUID_MAX)
    assert capital_result.kind == "capital"


def test_golden_entry_matrix(trainer_result) -> None:
    observed = {(row.zone_label, row.class_name): row.entry for row in trainer_result.rows}
    assert observed == GOLDEN_ENTRIES


def test_golden_anchor_matrix(trainer_result) -> None:
    observed = {
        (row.zone_label, row.class_name): row.anchor_class for row in trainer_result.rows
    }
    assert observed == GOLDEN_ANCHORS


CAPITAL_GAP_KEYS = {
    ("Darnassus", "Shaman"), ("Darnassus", "Warlock"),
    ("Ironforge", "Druid"), ("Exodar", "Rogue"), ("Exodar", "Warlock"),
    ("Undercity", "Shaman"), ("Undercity", "Hunter"), ("Undercity", "Druid"),
    ("Orgrimmar", "Druid"), ("ThunderBluff", "Paladin"), ("ThunderBluff", "Rogue"),
    ("ThunderBluff", "Warlock"), ("Silvermoon", "Shaman"), ("Silvermoon", "Warrior"),
}


def test_capital_trainers_cover_audited_gaps(capital_result) -> None:
    capital = capital_result.rows
    by_key = {(row.zone_label, row.class_name): row for row in capital}
    assert set(by_key) == CAPITAL_GAP_KEYS
    # Capital GUIDs live in the dedicated capital sub-band.
    assert min(r.guid for r in capital) == MOD_UAC_CAPITAL_GUID_MIN
    assert capital_result.guid_max <= MOD_UAC_CAPITAL_GUID_MAX
    # Reuses a full class-trainer entry (e.g. Farseer Nobundo), and inherits
    # npcflag/equipment/health from the template via 0 columns.
    assert by_key[("Darnassus", "Shaman")].entry == 17204
    for row in capital:
        assert row.is_capital
        assert row.npcflag == 0
        assert row.equipment_id == 0
        assert row.curhealth == 0


def test_northshire_priest_anchored_trainers_are_one_step_from_anchor(
    trainer_result,
) -> None:
    import math

    rows = {
        (row.zone_label, row.class_name): row
        for row in trainer_result.rows
        if row.zone_label == "Northshire" and row.anchor_class == "Priest"
    }
    assert set(rows) == {("Northshire", "Shaman"), ("Northshire", "Druid")}
    for row in rows.values():
        # Native Priest anchor from baked snapshot (Priestess Anetta).
        priest_x, priest_y = -8853.59, -193.336
        distance = math.hypot(row.x - priest_x, row.y - priest_y)
        assert distance == pytest.approx(PLACEMENT_GAP, abs=0.01)


def test_plan_anchor_placement_uses_gap_on_second_side() -> None:
    anchor = NativeTrainer("Priest", 375, "Priestess Anetta", -8853.59, -193.336, 82.116, 2.5482)
    natives = (
        anchor,
        NativeTrainer("Rogue", 915, "Jorik Kerridan", -8863.47, -210.91, 80.755, 4.4157),
    )
    side_slots: dict[tuple[int, str], int] = {}
    shaman = plan_anchor_placement(anchor, natives, side_slots)
    druid = plan_anchor_placement(anchor, natives, side_slots)
    assert shaman[4] == "right"
    assert druid[4] == "left"
    assert side_slots[(375, "right")] == 1
    assert side_slots[(375, "left")] == 1
    right_x, right_y, _, _ = place_on_side(anchor, "right", 0)
    left_x, left_y, _, _ = place_on_side(anchor, "left", 0)
    assert (shaman[0], shaman[1]) == (right_x, right_y)
    assert (druid[0], druid[1]) == (left_x, left_y)


def test_northshire_hunter_anchors_rogue(trainer_result) -> None:
    row = next(
        row
        for row in trainer_result.rows
        if row.zone_label == "Northshire" and row.class_name == "Hunter"
    )
    assert row.anchor_class == "Rogue"
    assert row.entry == 895


def test_install_sql_matches_checked_in_artifact(
    baked_snapshot: Snapshot,
    trainer_result,
) -> None:
    if not CHECKED_IN_INSTALL.is_file():
        pytest.skip(f"Checked-in SQL not found: {CHECKED_IN_INSTALL}")
    generated = render_install_sql(trainer_result, snapshot=baked_snapshot)
    assert generated == CHECKED_IN_INSTALL.read_text(encoding="utf-8")


def test_uninstall_sql_matches_checked_in_artifact(trainer_result) -> None:
    if not CHECKED_IN_UNINSTALL.is_file():
        pytest.skip(f"Checked-in SQL not found: {CHECKED_IN_UNINSTALL}")
    generated = render_uninstall_sql(trainer_result)
    assert generated == CHECKED_IN_UNINSTALL.read_text(encoding="utf-8")


def test_worksheet_lists_all_trainers(trainer_result) -> None:
    worksheet = render_worksheet(trainer_result)
    for row in trainer_result.rows:
        assert row.zone_label in worksheet
        assert row.class_name in worksheet
        assert str(row.guid) in worksheet


def test_worksheet_shows_computed_and_emitted_for_overrides(trainer_result) -> None:
    worksheet = render_worksheet(trainer_result)
    overridden = [row for row in trainer_result.rows if row.computed is not None]
    assert len(overridden) == 3
    warlock = next(row for row in overridden if row.zone_label == "CampNarache")
    assert f"emitted: ({warlock.x}, {warlock.y}, {warlock.z}, o={warlock.o})" in worksheet
    assert (
        f"computed: ({warlock.computed.x}, {warlock.computed.y}, "
        f"{warlock.computed.z}, o={warlock.computed.o}) → overridden"
    ) in worksheet
    hunter = next(
        row
        for row in trainer_result.rows
        if row.zone_label == "Northshire" and row.class_name == "Hunter"
    )
    assert hunter.computed is None
    assert (
        f"**Hunter** guid `{hunter.guid}`: entry `{hunter.entry}` "
        f"({hunter.entry_name}) — anchor {hunter.anchor_class} ({hunter.anchor_name}) "
        f"@ ({hunter.x}, {hunter.y}, {hunter.z}, o={hunter.o})"
    ) in worksheet
    assert worksheet.count("→ overridden") == 3


def test_compute_zone_gaps_northshire(baked_snapshot: Snapshot, stock_matrix: ComboMatrix) -> None:
    data = baked_snapshot.data["trainers"]
    box = next(
        box
        for box in build_starter_zone_boxes(data["playercreateinfo"])
        if box.zone_id == 12
    )
    natives = native_trainers_in_box(
        box,
        creature_spawns=data["creature_spawns"],
        creature_default_trainer={
            int(k): int(v) for k, v in data["creature_default_trainer"].items()
        },
        trainer_spell_counts={
            int(k): int(v) for k, v in data["trainer_spell_counts"].items()
        },
        creature_template={
            int(k): v for k, v in data["creature_template"].items()
        },
    )
    gaps = compute_zone_gaps(box, stock_matrix, natives, playercreateinfo=data["playercreateinfo"])
    assert gaps == ("Hunter", "Shaman", "Druid")


def test_place_beside_anchor_uses_anchor_orientation() -> None:
    anchor = NativeTrainer("Rogue", 915, "Jorik", 0.0, 0.0, 1.0, 1.570796)
    natives = (anchor,)
    x, y, z, o = place_beside_anchor(anchor, 0, natives)
    assert z == 1.0
    assert o == 1.5708
    assert x != 0.0 or y != 0.0


def test_select_anchor_skips_gap_kin() -> None:
    natives = (
        NativeTrainer("Priest", 1, "Priest", 0.0, 0.0, 0.0, 0.0),
        NativeTrainer("Rogue", 2, "Rogue", 5.0, 0.0, 0.0, 0.0),
    )
    anchor = select_anchor(
        "Shaman",
        natives,
        gap_classes=frozenset({"Shaman", "Druid"}),
        fallback_x=0.0,
        fallback_y=0.0,
    )
    assert anchor.class_name == "Priest"


def test_load_trainer_overrides_from_checked_in_file() -> None:
    overrides = load_trainer_overrides(OVERRIDES_PATH)
    assert len(overrides) == 6
    by_key = {(item.zone, item.class_name): item for item in overrides}
    warlock = by_key[("CampNarache", "Warlock")]
    assert warlock.x == pytest.approx(-2950.7625)
    paladin = by_key[("Deathknell", "Paladin")]
    assert paladin.x == pytest.approx(1849.2815)
    hunter = by_key[("Deathknell", "Hunter")]
    assert hunter.x == pytest.approx(1875.4225)


def test_deathknell_overrides_apply_to_emitter(
    baked_snapshot: Snapshot,
    stock_matrix: ComboMatrix,
) -> None:
    overrides = load_trainer_overrides(OVERRIDES_PATH)
    result = compute_trainer_rows(baked_snapshot, stock_matrix, overrides=overrides)
    rows = {
        (row.zone_label, row.class_name): row
        for row in result.rows
        if row.zone_label == "Deathknell"
    }
    assert rows[("Deathknell", "Paladin")].x == pytest.approx(1849.2815)
    assert rows[("Deathknell", "Hunter")].x == pytest.approx(1875.4225)


def test_camp_narache_warlock_uses_override_position(
    baked_snapshot: Snapshot,
    stock_matrix: ComboMatrix,
) -> None:
    overrides = load_trainer_overrides(OVERRIDES_PATH)
    result = compute_trainer_rows(baked_snapshot, stock_matrix, overrides=overrides)
    row = next(
        row
        for row in result.rows
        if row.zone_label == "CampNarache" and row.class_name == "Warlock"
    )
    assert row.x == pytest.approx(-2950.7625)
    assert row.y == pytest.approx(-143.74812)
    assert row.z == pytest.approx(67.069466)
    assert row.o == pytest.approx(4.708466)


def test_empty_emit_still_deletes_guid_band() -> None:
    empty = TrainerEmitResult(
        rows=(),
        guid_base=TRAINER_GUID_BASE,
        guid_max=TRAINER_GUID_BASE - 1,
        band=(TRAINER_GUID_BASE, MOD_UAC_STARTER_GUID_MAX),
        kind="starter",
    )
    install = render_install_sql(empty)
    uninstall = render_uninstall_sql(empty)
    delete_clause = (
        f"DELETE FROM `creature` WHERE `guid` BETWEEN "
        f"{TRAINER_GUID_BASE} AND {MOD_UAC_STARTER_GUID_MAX};"
    )
    assert delete_clause in install
    assert delete_clause in uninstall


def test_override_missing_class_raises(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("overrides:\n  - zone: Northshire\n    x: 1.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Trainer override requires class"):
        load_trainer_overrides(bad_yaml)


def test_starter_and_capital_deletes_are_disjoint_subbands(trainer_result, capital_result) -> None:
    starter_sql = render_install_sql(trainer_result)
    capital_sql = render_install_sql(capital_result)
    assert (
        f"DELETE FROM `creature` WHERE `guid` BETWEEN "
        f"{TRAINER_GUID_BASE} AND {MOD_UAC_STARTER_GUID_MAX};"
    ) in starter_sql
    assert (
        f"DELETE FROM `creature` WHERE `guid` BETWEEN "
        f"{MOD_UAC_CAPITAL_GUID_MIN} AND {MOD_UAC_CAPITAL_GUID_MAX};"
    ) in capital_sql
    # The starter DELETE must not reach into the capital sub-band (no clobber on re-apply).
    assert f"AND {MOD_UAC_CREATURE_GUID_MAX};" not in starter_sql


def test_capital_install_sql_matches_checked_in_artifact(
    baked_snapshot: Snapshot, capital_result
) -> None:
    if not CHECKED_IN_CAPITAL_INSTALL.is_file():
        pytest.skip(f"Checked-in SQL not found: {CHECKED_IN_CAPITAL_INSTALL}")
    generated = render_install_sql(capital_result, snapshot=baked_snapshot)
    assert generated == CHECKED_IN_CAPITAL_INSTALL.read_text(encoding="utf-8")


def test_capital_uninstall_sql_matches_checked_in_artifact(capital_result) -> None:
    if not CHECKED_IN_CAPITAL_UNINSTALL.is_file():
        pytest.skip(f"Checked-in SQL not found: {CHECKED_IN_CAPITAL_UNINSTALL}")
    generated = render_uninstall_sql(capital_result)
    assert generated == CHECKED_IN_CAPITAL_UNINSTALL.read_text(encoding="utf-8")


def test_invalid_override_anchor_raises(minimal_snapshot: Snapshot) -> None:
    overrides = (
        TrainerOverride(
            zone="Northshire",
            class_name="Shaman",
            entry=17089,
            anchor="Warrior",
        ),
    )
    matrix = ComboMatrix(existing=frozenset(), new_combos=frozenset({(1, 7)}))
    with pytest.raises(ValueError, match="Override anchor 'Warrior' not present"):
        compute_trainer_rows(minimal_snapshot, matrix, overrides=overrides)


def test_emitter_end_to_end(baked_snapshot: Snapshot, stock_matrix: ComboMatrix) -> None:
    overrides = load_trainer_overrides(OVERRIDES_PATH)
    emitter = TrainerEmitter(
        snapshot=baked_snapshot,
        matrix=stock_matrix,
        overrides=overrides,
    )
    result = emitter.compute()
    capital = emitter.compute_capital()
    assert len(result.rows) == 26
    assert len(capital.rows) == 14
    assert "DELETE FROM `creature`" in emitter.render_install(result)
    assert "DELETE FROM `creature`" in emitter.render_uninstall(result)
    assert "DELETE FROM `creature`" in emitter.render_install(capital)


def test_minimal_snapshot_gap_for_shaman(minimal_snapshot: Snapshot) -> None:
    matrix = ComboMatrix(existing=frozenset(), new_combos=frozenset({(1, 7)}))
    data = minimal_snapshot.data["trainers"]
    box = build_starter_zone_boxes(data["playercreateinfo"])[0]
    natives = native_trainers_in_box(
        box,
        creature_spawns=data["creature_spawns"],
        creature_default_trainer={
            int(k): int(v) for k, v in data["creature_default_trainer"].items()
        },
        trainer_spell_counts={
            int(k): int(v) for k, v in data["trainer_spell_counts"].items()
        },
        creature_template={
            int(k): v for k, v in data["creature_template"].items()
        },
    )
    gaps = compute_zone_gaps(box, matrix, natives, playercreateinfo=data["playercreateinfo"])
    assert gaps == ("Shaman",)
