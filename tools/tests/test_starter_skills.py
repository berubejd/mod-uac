from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.emit_player import PlayerCreateEmitter, build_resolver
from aracgen.item_prototypes import DEFAULT_ITEM_PROTOTYPES_PATH, ItemPrototypeStore
from aracgen.sources import ZipDbcSource
from aracgen.starter_skills import compute_starter_skills
from aracgen.stock_loader import StockKitStore

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "cache" / "client-data-v19.zip"
STOCK_DIR = Path(__file__).resolve().parents[2] / "data" / "stock" / "db_world"
ITEM_PROTOTYPES = DEFAULT_ITEM_PROTOTYPES_PATH


@pytest.fixture(scope="session")
def item_prototypes() -> ItemPrototypeStore:
    if not ITEM_PROTOTYPES.is_file():
        pytest.skip(f"Item prototypes not found: {ITEM_PROTOTYPES}")
    return ItemPrototypeStore(ITEM_PROTOTYPES)


@pytest.fixture(scope="session")
def resolver(item_prototypes: ItemPrototypeStore):
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    source = ZipDbcSource(DATA_ZIP)
    return build_resolver(
        source.load_char_start_outfit(),
        stock_dir=STOCK_DIR,
        item_prototypes_path=ITEM_PROTOTYPES,
    )


def test_human_hunter_gets_gun_skill(resolver) -> None:
    kit = resolver.resolve(1, 3)
    skill_ids = {row.skill_id for row in kit.skills}
    assert 46 in skill_ids


def test_undead_hunter_gets_bow_skill(resolver) -> None:
    kit = resolver.resolve(5, 3)
    skill_ids = {row.skill_id for row in kit.skills}
    assert 45 in skill_ids


def test_dwarf_mage_with_native_outfit_skips_item_skills(
    item_prototypes: ItemPrototypeStore,
) -> None:
    store = StockKitStore.load(STOCK_DIR)
    skills = compute_starter_skills(
        3,
        8,
        (),
        store,
        item_prototypes,
        ref_race=5,
    )
    assert skills == ()


def test_starter_skills_install_sql_includes_human_hunter_gun(resolver) -> None:
    install = PlayerCreateEmitter(resolver).render_install_files()["playercreateinfo_skills"]
    assert "VALUES (1, 4, 46, 0" in install
    uninstall = PlayerCreateEmitter(resolver).render_uninstall_files()["playercreateinfo_skills"]
    assert "raceMask` = 1" in uninstall
    assert "skill` IN (46)" in uninstall
