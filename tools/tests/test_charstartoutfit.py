"""Tests for charstartoutfit_dbc overlay generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.charstartoutfit_export import dbc_max_outfit_id, stock_outfit_covers
from aracgen.emit_player import PlayerCreateEmitter, build_resolver
from aracgen.item_prototypes import DEFAULT_ITEM_PROTOTYPES_PATH
from aracgen.kits import CanonicalKitResolver
from aracgen.sources import ZipDbcSource

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "cache" / "client-data-v19.zip"
STOCK_DIR = Path(__file__).resolve().parents[2] / "data" / "stock" / "db_world"
ITEM_PROTOTYPES = DEFAULT_ITEM_PROTOTYPES_PATH


@pytest.fixture(scope="session")
def resolver() -> CanonicalKitResolver:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    if not ITEM_PROTOTYPES.is_file():
        pytest.skip(f"Item prototypes not found: {ITEM_PROTOTYPES}")
    source = ZipDbcSource(DATA_ZIP)
    return build_resolver(
        source.load_char_start_outfit(),
        stock_dir=STOCK_DIR,
        item_prototypes_path=ITEM_PROTOTYPES,
    )


@pytest.fixture(scope="session")
def stock_max_id(resolver: CanonicalKitResolver) -> int:
    return dbc_max_outfit_id(resolver.outfit)


def test_dwarf_mage_stock_outfit_covers(resolver: CanonicalKitResolver) -> None:
    assert stock_outfit_covers(resolver.outfit, 3, 8)


def test_dwarf_mage_emits_no_overlay_row(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(3, 8)
    assert kit.outfit_records == ()
    install = PlayerCreateEmitter(resolver).render_install_files()["charstartoutfit_dbc"]
    assert "-- (3, 8," not in install
    assert ", 3, 8," not in install.split("REPLACE INTO", 1)[-1]


def test_human_druid_clones_night_elf_outfits_both_genders(
    resolver: CanonicalKitResolver,
    stock_max_id: int,
) -> None:
    kit = resolver.resolve(1, 11)
    assert len(kit.outfit_records) == 2
    sexes = {record.sex_id for record in kit.outfit_records}
    assert sexes == {0, 1}

    from aracgen.charstartoutfit_export import find_outfit_record, read_outfit_record

    for record in kit.outfit_records:
        ref_index = find_outfit_record(resolver.outfit, 4, 11, record.sex_id)
        ref = read_outfit_record(resolver.outfit, ref_index)
        assert record.item_ids == ref.item_ids
        assert record.display_item_ids == ref.display_item_ids
        assert record.inventory_types == ref.inventory_types
        assert record.race_id == 1
        assert record.class_id == 11
        assert record.record_id > stock_max_id


def test_overlay_ids_above_stock_max(resolver: CanonicalKitResolver, stock_max_id: int) -> None:
    result = PlayerCreateEmitter(resolver).compute()
    for record in result.outfit_records:
        assert record.record_id > stock_max_id


def test_no_playercreateinfo_item_anywhere(resolver: CanonicalKitResolver) -> None:
    emitter = PlayerCreateEmitter(resolver)
    install = emitter.render_install_files()
    uninstall = emitter.render_uninstall_files()
    assert "playercreateinfo_item" not in uninstall
    for table, sql in install.items():
        if table == "charstartoutfit_dbc":
            assert "DELETE FROM `playercreateinfo_item`" in sql
            assert "REPLACE INTO `charstartoutfit_dbc`" in sql
        else:
            assert "playercreateinfo_item" not in sql


def test_outfit_overlay_respects_db_max_id(resolver: CanonicalKitResolver) -> None:
    from aracgen.kits import CanonicalKitResolver as Resolver

    elevated = Resolver(
        matrix=resolver.matrix,
        store=resolver.store,
        outfit=resolver.outfit,
        item_prototypes=resolver.item_prototypes,
        db_max_outfit_id=1200,
    )
    result = PlayerCreateEmitter(elevated).compute()
    assert all(record.record_id > 1200 for record in result.outfit_records)


def test_charstartoutfit_uninstall_targets_overlay_ids(
    resolver: CanonicalKitResolver,
    stock_max_id: int,
) -> None:
    result = PlayerCreateEmitter(resolver).compute()
    uninstall = PlayerCreateEmitter(resolver).render_uninstall_files(result)["charstartoutfit_dbc"]
    assert "DELETE FROM `charstartoutfit_dbc` WHERE `ID` IN" in uninstall
    for record in result.outfit_records:
        assert str(record.record_id) in uninstall
        assert record.record_id > stock_max_id
