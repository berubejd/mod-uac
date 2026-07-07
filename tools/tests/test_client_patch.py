from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.charstartoutfit_export import find_outfit_record, read_outfit_record
from aracgen.dbc import DbcTable
from aracgen.emit_client import (
    CHAR_BASE_INFO_MPQ_PATH,
    CHAR_START_OUTFIT_MPQ_PATH,
    CLIENT_PATCH_ENHANCED_DIR,
    CLIENT_PATCH_STANDARD_DIR,
    CLIENT_PATCH_UNLOCK_ONLY_DIR,
    LISTFILE_MPQ_PATH,
    ClientPatchVariant,
    build_char_base_info_table,
    build_client_patch_bytes,
)
from aracgen.formats import CHAR_BASE_INFO, CHAR_START_OUTFIT
from aracgen.hd_outfit_baseline import (
    HD_OUTFIT_STOCK_INDEX_PATH,
    HD_OUTFIT_TEMPLATES_PATH,
    load_hd_charstartoutfit_baseline,
)
from aracgen.matrix import PLAYABLE_CLASSES, PLAYABLE_RACES
from aracgen.mpq import MpqFileEntry, build_mpq_v1, decrypt, encrypt, hash_string, read_mpq_file
from aracgen.sources import ZipDbcSource

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "cache" / "client-data-v19.zip"
ITEM_PROTOTYPES = Path(__file__).resolve().parents[2] / "data" / "item_prototypes.json"


def test_encrypt_decrypt_round_trip() -> None:
    key = hash_string("(hash table)", 3)
    plain = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    assert decrypt(encrypt(plain, key), key) == plain


def test_build_mpq_read_back_single_file() -> None:
    payload = build_mpq_v1((MpqFileEntry(path="DBFilesClient\\Foo.dbc", data=b"hello"),))
    assert read_mpq_file(payload, "DBFilesClient\\Foo.dbc") == b"hello"


def test_char_base_info_table_has_full_matrix() -> None:
    table = build_char_base_info_table()
    assert table.record_count == len(PLAYABLE_RACES) * len(PLAYABLE_CLASSES)
    combos = {(table.get_uint8(i, 0), table.get_uint8(i, 1)) for i in range(table.record_count)}
    expected = {(race, class_id) for race in PLAYABLE_RACES for class_id in PLAYABLE_CLASSES}
    assert combos == expected


def test_client_patch_variant_dirs() -> None:
    assert ClientPatchVariant.UNLOCK_ONLY.value == CLIENT_PATCH_UNLOCK_ONLY_DIR
    assert ClientPatchVariant.STANDARD.value == CLIENT_PATCH_STANDARD_DIR
    assert ClientPatchVariant.ENHANCED.value == CLIENT_PATCH_ENHANCED_DIR


@pytest.fixture(scope="session")
def dbc_source() -> ZipDbcSource:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    if not ITEM_PROTOTYPES.is_file():
        pytest.skip(f"Item prototypes not found: {ITEM_PROTOTYPES}")
    return ZipDbcSource(DATA_ZIP)


def test_unlock_only_patch_has_char_base_info_only(dbc_source: ZipDbcSource) -> None:
    payload = build_client_patch_bytes(
        dbc_source,
        variant=ClientPatchVariant.UNLOCK_ONLY,
    )
    raw = read_mpq_file(payload, CHAR_BASE_INFO_MPQ_PATH)
    table = DbcTable.read(raw, CHAR_BASE_INFO)
    assert table.record_count == 100
    listfile = read_mpq_file(payload, LISTFILE_MPQ_PATH).decode("ascii")
    assert CHAR_BASE_INFO_MPQ_PATH in listfile
    assert CHAR_START_OUTFIT_MPQ_PATH not in listfile


def test_standard_patch_appends_char_start_outfit_overlays(dbc_source: ZipDbcSource) -> None:
    stock = dbc_source.load_char_start_outfit()
    stock_count = stock.record_count
    payload = build_client_patch_bytes(dbc_source, variant=ClientPatchVariant.STANDARD)
    listfile = read_mpq_file(payload, LISTFILE_MPQ_PATH).decode("ascii")
    assert CHAR_START_OUTFIT_MPQ_PATH in listfile
    raw = read_mpq_file(payload, CHAR_START_OUTFIT_MPQ_PATH)
    patched = DbcTable.read(raw, CHAR_START_OUTFIT)
    assert patched.record_count > stock_count
    assert (6, 8, 0) in {
        (
            patched.get_uint8(index, 1),
            patched.get_uint8(index, 2),
            patched.get_uint8(index, 3),
        )
        for index in range(patched.record_count)
    }


@pytest.fixture(scope="session")
def hd_baseline() -> DbcTable:
    if not HD_OUTFIT_TEMPLATES_PATH.is_file() or not HD_OUTFIT_STOCK_INDEX_PATH.is_file():
        pytest.skip("HD outfit JSON catalog not found")
    return load_hd_charstartoutfit_baseline()


def test_enhanced_patch_preserves_hd_stock_rows(
    dbc_source: ZipDbcSource,
    hd_baseline: DbcTable,
) -> None:
    payload = build_client_patch_bytes(dbc_source, variant=ClientPatchVariant.ENHANCED)
    raw = read_mpq_file(payload, CHAR_START_OUTFIT_MPQ_PATH)
    patched = DbcTable.read(raw, CHAR_START_OUTFIT)
    assert patched.record_count == hd_baseline.record_count + 74
    for index in range(hd_baseline.record_count):
        assert patched.records[index] == hd_baseline.records[index]


def test_enhanced_overlay_uses_hd_preview_displays(
    dbc_source: ZipDbcSource,
    hd_baseline: DbcTable,
) -> None:
    standard = DbcTable.read(
        read_mpq_file(
            build_client_patch_bytes(dbc_source, variant=ClientPatchVariant.STANDARD),
            CHAR_START_OUTFIT_MPQ_PATH,
        ),
        CHAR_START_OUTFIT,
    )
    enhanced = DbcTable.read(
        read_mpq_file(
            build_client_patch_bytes(dbc_source, variant=ClientPatchVariant.ENHANCED),
            CHAR_START_OUTFIT_MPQ_PATH,
        ),
        CHAR_START_OUTFIT,
    )
    std_idx = find_outfit_record(standard, 6, 8, 0)
    enh_idx = find_outfit_record(enhanced, 6, 8, 0)
    std_rec = read_outfit_record(standard, std_idx)
    enh_rec = read_outfit_record(enhanced, enh_idx)
    ref_idx = find_outfit_record(hd_baseline, 5, 8, 0)
    ref_rec = read_outfit_record(hd_baseline, ref_idx)
    assert std_rec.item_ids == enh_rec.item_ids
    assert enh_rec.display_item_ids == ref_rec.display_item_ids
    assert std_rec.display_item_ids != enh_rec.display_item_ids
