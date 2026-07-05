from __future__ import annotations

from aracgen.dbc import DbcTable
from aracgen.emit_client import (
    CHAR_BASE_INFO_MPQ_PATH,
    LISTFILE_MPQ_PATH,
    build_char_base_info_table,
    build_client_patch_bytes,
)
from aracgen.formats import CHAR_BASE_INFO
from aracgen.matrix import PLAYABLE_CLASSES, PLAYABLE_RACES
from aracgen.mpq import MpqFileEntry, build_mpq_v1, decrypt, encrypt, hash_string, read_mpq_file


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


def test_client_patch_mpq_contains_char_base_info() -> None:
    payload = build_client_patch_bytes()
    raw = read_mpq_file(payload, CHAR_BASE_INFO_MPQ_PATH)
    table = DbcTable.read(raw, CHAR_BASE_INFO)
    assert table.record_count == 100
    assert read_mpq_file(payload, LISTFILE_MPQ_PATH).decode("ascii") == (
        f"{CHAR_BASE_INFO_MPQ_PATH}\r\n"
    )
