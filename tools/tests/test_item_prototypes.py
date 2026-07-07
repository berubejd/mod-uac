from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.item_prototypes import (
    DEFAULT_ITEM_PROTOTYPES_PATH,
    ItemPrototype,
    ItemPrototypeStore,
    extract_item_prototypes_from_ac_sql,
    items_payload_to_prototypes,
    write_item_prototypes_file,
)
from aracgen.outfit_items import collect_mod_uac_outfit_item_ids
from aracgen.sources import ZipDbcSource

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "cache" / "client-data-v19.zip"
AC_ITEM_TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "azerothcore-wotlk"
    / "data"
    / "sql"
    / "base"
    / "db_world"
    / "item_template.sql"
)


def test_items_payload_to_prototypes() -> None:
    prototypes = items_payload_to_prototypes({"1395": [2, 10]})
    assert prototypes[1395] == ItemPrototype(1395, 2, 10)


def test_item_prototype_store_loads_baked_file() -> None:
    if not DEFAULT_ITEM_PROTOTYPES_PATH.is_file():
        pytest.skip(f"Baked item prototypes not found: {DEFAULT_ITEM_PROTOTYPES_PATH}")
    store = ItemPrototypeStore()
    assert store.get(6948) == ItemPrototype(6948, 15, 0)


def test_collect_mod_uac_outfit_item_ids_from_canonical_dbc() -> None:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    outfit = ZipDbcSource(DATA_ZIP).load_char_start_outfit()
    item_ids = collect_mod_uac_outfit_item_ids(outfit)
    assert 6948 in item_ids  # hearthstone in cloned reference outfits
    assert len(item_ids) < 300


def test_write_item_prototypes_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "item_prototypes.json"
    write_item_prototypes_file(path, {42: (2, 7)}, source="test", version="v1")
    store = ItemPrototypeStore(path)
    assert store.get(42) == ItemPrototype(42, 2, 7)


def test_extract_item_prototypes_from_ac_sql_subset() -> None:
    if not AC_ITEM_TEMPLATE.is_file():
        pytest.skip(f"AC item_template.sql not found: {AC_ITEM_TEMPLATE}")
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    outfit = ZipDbcSource(DATA_ZIP).load_char_start_outfit()
    item_ids = collect_mod_uac_outfit_item_ids(outfit)
    extracted = extract_item_prototypes_from_ac_sql(AC_ITEM_TEMPLATE, item_ids)
    assert len(extracted) == len(item_ids)
