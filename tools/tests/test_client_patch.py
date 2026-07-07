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
    SKILL_RACE_CLASS_INFO_MPQ_PATH,
    ClientPatchVariant,
    build_char_base_info_table,
    build_client_patch_bytes,
    build_skill_race_class_info_table,
)
from aracgen.emit_skill import (
    compute_client_language_overlay,
    compute_skill_overlay,
    merge_skill_overlays,
)
from aracgen.formats import CHAR_BASE_INFO, CHAR_START_OUTFIT, SKILL_RACE_CLASS_INFO
from aracgen.hd_outfit_baseline import (
    HD_OUTFIT_STOCK_INDEX_PATH,
    HD_OUTFIT_TEMPLATES_PATH,
    load_hd_charstartoutfit_baseline,
)
from aracgen.matrix import (
    PLAYABLE_CLASSES,
    PLAYABLE_RACES,
    ComboMatrix,
    mask_covers_race_class,
    race_bit,
)
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


def test_unlock_only_patch_has_char_base_info_and_skill_overlay(
    dbc_source: ZipDbcSource,
) -> None:
    stock_skill = dbc_source.load_skill_race_class_info()
    payload = build_client_patch_bytes(
        dbc_source,
        variant=ClientPatchVariant.UNLOCK_ONLY,
    )
    raw = read_mpq_file(payload, CHAR_BASE_INFO_MPQ_PATH)
    table = DbcTable.read(raw, CHAR_BASE_INFO)
    assert table.record_count == 100
    listfile = read_mpq_file(payload, LISTFILE_MPQ_PATH).decode("ascii")
    assert CHAR_BASE_INFO_MPQ_PATH in listfile
    assert SKILL_RACE_CLASS_INFO_MPQ_PATH in listfile
    assert CHAR_START_OUTFIT_MPQ_PATH not in listfile
    skill_raw = read_mpq_file(payload, SKILL_RACE_CLASS_INFO_MPQ_PATH)
    patched_skill = DbcTable.read(skill_raw, SKILL_RACE_CLASS_INFO)
    overlay = compute_skill_overlay(stock_skill, ComboMatrix.stock())
    language_overlay = compute_client_language_overlay(
        merge_skill_overlays(stock_skill, overlay.rows)
    )
    assert patched_skill.record_count == (
        stock_skill.record_count + len(overlay.rows) + len(language_overlay)
    )
    for index in range(stock_skill.record_count):
        assert patched_skill.records[index] == stock_skill.records[index]


def test_all_patch_variants_include_skill_race_class_info(dbc_source: ZipDbcSource) -> None:
    for variant in ClientPatchVariant:
        payload = build_client_patch_bytes(dbc_source, variant=variant)
        listfile = read_mpq_file(payload, LISTFILE_MPQ_PATH).decode("ascii")
        assert SKILL_RACE_CLASS_INFO_MPQ_PATH in listfile
        patched = DbcTable.read(
            read_mpq_file(payload, SKILL_RACE_CLASS_INFO_MPQ_PATH),
            SKILL_RACE_CLASS_INFO,
        )
        assert patched.record_count == 288


def test_skill_overlay_covers_night_elf_shaman_mail_gate(dbc_source: ZipDbcSource) -> None:
    table = build_skill_race_class_info_table(dbc_source)
    mail_rows = [
        (
            table.get_uint32(index, 0),
            table.get_uint32(index, 5),
        )
        for index in range(table.record_count)
        if table.get_uint32(index, 1) == 413
        and mask_covers_race_class(
            table.get_uint32(index, 2),
            table.get_uint32(index, 3),
            4,
            7,
        )
    ]
    assert mail_rows
    assert all(min_level == 40 for _, min_level in mail_rows)


def _language_rows(
    table: DbcTable,
    skill_id: int,
    race_id: int,
    *,
    flags: int = 128,
) -> list[int]:
    bit = race_bit(race_id)
    return [
        table.get_uint32(index, 0)
        for index in range(table.record_count)
        if table.get_uint32(index, 1) == skill_id
        and table.get_uint32(index, 2) == bit
        and table.get_uint32(index, 4) == flags
    ]


def test_client_language_overlay_adds_per_race_faction_languages(
    dbc_source: ZipDbcSource,
) -> None:
    stock_skill = dbc_source.load_skill_race_class_info()
    equip_overlay = compute_skill_overlay(stock_skill, ComboMatrix.stock())
    merged = build_skill_race_class_info_table(dbc_source)
    language_overlay = compute_client_language_overlay(
        merge_skill_overlays(stock_skill, equip_overlay.rows)
    )
    assert len(language_overlay) == 10
    assert merged.record_count == stock_skill.record_count + len(equip_overlay.rows) + 10

    for race_id in (1, 3, 4, 7, 11):
        assert _language_rows(merged, 98, race_id)
    for race_id in (2, 5, 6, 8, 10):
        assert _language_rows(merged, 109, race_id)


def test_new_combo_night_elf_hunter_has_chat_language_rows(dbc_source: ZipDbcSource) -> None:
    table = build_skill_race_class_info_table(dbc_source)
    assert _language_rows(table, 98, 4)
    darnassian = next(
        index
        for index in range(table.record_count)
        if table.get_uint32(index, 1) == 113 and table.get_uint32(index, 2) == race_bit(4)
    )
    assert mask_covers_race_class(
        table.get_uint32(darnassian, 2),
        table.get_uint32(darnassian, 3),
        4,
        3,
    )


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
