from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pytest

from aracgen.dbc import DbcTable, FieldKind, parse_format, record_size_for_format
from aracgen.formats import CHAR_BASE_INFO, CHAR_START_OUTFIT, SKILL_RACE_CLASS_INFO

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "cache" / "client-data-v19.zip"

DBC_CASES = [
    ("dbc/CharBaseInfo.dbc", CHAR_BASE_INFO),
    ("dbc/SkillRaceClassInfo.dbc", SKILL_RACE_CLASS_INFO),
    ("dbc/CharStartOutfit.dbc", CHAR_START_OUTFIT),
]


@pytest.fixture(scope="session")
def data_zip() -> zipfile.ZipFile:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    return zipfile.ZipFile(DATA_ZIP)


@pytest.fixture(params=DBC_CASES, ids=[name.split("/")[-1] for name, _ in DBC_CASES])
def dbc_blob(data_zip: zipfile.ZipFile, request: pytest.FixtureRequest) -> tuple[str, str, bytes]:
    path, fmt = request.param
    return path, fmt, data_zip.read(path)


def test_format_record_sizes_match_headers(dbc_blob: tuple[str, str, bytes]) -> None:
    _path, fmt, raw = dbc_blob
    record_size = struct.unpack_from("<I", raw, 12)[0]
    assert record_size_for_format(fmt) == record_size


def test_byte_exact_round_trip(dbc_blob: tuple[str, str, bytes]) -> None:
    _path, fmt, raw = dbc_blob
    table = DbcTable.read(raw, format_str=fmt)
    assert table.write() == raw


def test_round_trip_via_file(tmp_path: Path, dbc_blob: tuple[str, str, bytes]) -> None:
    _path, fmt, raw = dbc_blob
    src = tmp_path / "src.dbc"
    dst = tmp_path / "dst.dbc"
    src.write_bytes(raw)

    table = DbcTable.read_file(src, format_str=fmt)
    table.write_file(dst)
    assert dst.read_bytes() == raw


def test_typed_field_access_char_base_info(data_zip: zipfile.ZipFile) -> None:
    raw = data_zip.read("dbc/CharBaseInfo.dbc")
    table = DbcTable.read(raw, format_str=CHAR_BASE_INFO)
    assert table.get_uint8(0, 0) == 1
    assert table.get_uint8(0, 1) == 1


def test_typed_field_access_skill_race_class_info(data_zip: zipfile.ZipFile) -> None:
    raw = data_zip.read("dbc/SkillRaceClassInfo.dbc")
    table = DbcTable.read(raw, format_str=SKILL_RACE_CLASS_INFO)
    skill_id = table.get_uint32(0, 1)
    assert skill_id > 0


def test_create_empty_char_base_info_round_trip() -> None:
    table = DbcTable.create_empty(CHAR_BASE_INFO)
    table.append_record()
    table.set_uint8(0, 0, 6)
    table.set_uint8(0, 1, 8)

    round_tripped = DbcTable.read(table.write(), format_str=CHAR_BASE_INFO)
    assert round_tripped.record_count == 1
    assert round_tripped.get_uint8(0, 0) == 6
    assert round_tripped.get_uint8(0, 1) == 8


def test_format_string_field_not_classified_as_uint32() -> None:
    specs = parse_format("is")
    assert specs[1].char == "s"
    assert specs[1].kind == FieldKind.STRING


def test_set_string_writes_offset_and_round_trips() -> None:
    fmt = "is"
    table = DbcTable.create_empty(fmt)
    table.append_record()
    table.set_uint32(0, 0, 42)
    table.set_string(0, 1, "Mulgore")

    assert table.get_uint32(0, 0) == 42
    assert table.get_string(0, 1) == "Mulgore"

    round_tripped = DbcTable.read(table.write(), format_str=fmt)
    assert round_tripped.get_string(0, 1) == "Mulgore"


def test_set_string_appends_without_corrupting_existing() -> None:
    fmt = "is"
    table = DbcTable.create_empty(fmt)
    table.append_record()
    table.set_uint32(0, 0, 1)
    table.set_string(0, 1, "first")

    table.append_record()
    table.set_uint32(1, 0, 2)
    table.set_string(1, 1, "second")

    assert table.get_string(0, 1) == "first"
    assert table.get_string(1, 1) == "second"

    round_tripped = DbcTable.read(table.write(), format_str=fmt)
    assert round_tripped.record_count == 2
    assert round_tripped.get_string(0, 1) == "first"
    assert round_tripped.get_string(1, 1) == "second"


def test_set_string_rejects_non_string_field_without_mutation() -> None:
    table = DbcTable.create_empty("is")
    table.append_record()
    block_before = bytes(table.string_block)

    with pytest.raises(TypeError, match="not string"):
        table.set_string(0, 0, "bad")

    assert bytes(table.string_block) == block_before


def test_get_string_rejects_non_string_field() -> None:
    table = DbcTable.create_empty("is")
    table.append_record()
    table.set_uint32(0, 0, 0)

    with pytest.raises(TypeError, match="not string"):
        table.get_string(0, 0)


def test_set_string_rejects_bad_record_index_without_mutation() -> None:
    table = DbcTable.create_empty("is")
    table.append_record()
    block_before = bytes(table.string_block)

    with pytest.raises(IndexError, match="Record index out of range"):
        table.set_string(1, 1, "orphan")

    assert bytes(table.string_block) == block_before

    with pytest.raises(IndexError, match="Record index out of range"):
        table.set_string(-1, 1, "orphan")

    assert bytes(table.string_block) == block_before
