"""WDBC reader/writer with byte-exact round-trip for unmodified tables."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

WDBC_MAGIC = 0x43424457
WDBC_HEADER = struct.Struct("<4I")


class FieldKind(Enum):
    UINT8 = "uint8"
    UINT32 = "uint32"
    FLOAT = "float"
    STRING = "string"
    PAD_BYTE = "pad_byte"
    PAD_UINT32 = "pad_uint32"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    index: int
    char: str
    kind: FieldKind
    offset: int
    size: int


def _field_kind(char: str) -> FieldKind:
    if char == "b":
        return FieldKind.UINT8
    if char == "s":
        return FieldKind.STRING
    if char in "din":
        return FieldKind.UINT32
    if char == "f":
        return FieldKind.FLOAT
    if char == "X":
        return FieldKind.PAD_BYTE
    if char == "x":
        return FieldKind.PAD_UINT32
    msg = f"Unsupported DBC format character: {char!r}"
    raise ValueError(msg)


def parse_format(format_str: str) -> list[FieldSpec]:
    """Return per-field layout as stored in the WDBC record blob."""
    specs: list[FieldSpec] = []
    offset = 0
    for index, char in enumerate(format_str):
        kind = _field_kind(char)
        size = 1 if kind in {FieldKind.UINT8, FieldKind.PAD_BYTE} else 4
        specs.append(FieldSpec(index=index, char=char, kind=kind, offset=offset, size=size))
        offset += size
    return specs


def record_size_for_format(format_str: str) -> int:
    if not format_str:
        return 0
    specs = parse_format(format_str)
    last = specs[-1]
    return last.offset + last.size


class DbcTable:
    """Decoded WDBC table backed by raw record bytes for exact rewrite."""

    def __init__(
        self,
        *,
        format_str: str | None,
        record_count: int,
        field_count: int,
        record_size: int,
        string_block: bytes | bytearray,
        records: list[bytearray],
    ) -> None:
        self.format_str = format_str
        self.record_count = record_count
        self.field_count = field_count
        self.record_size = record_size
        self.string_block = bytearray(string_block)
        self.records = records
        self._fields = parse_format(format_str) if format_str else []

        if len(self.records) != self.record_count:
            msg = f"record_count {self.record_count} != len(records) {len(self.records)}"
            raise ValueError(msg)
        if any(len(rec) != self.record_size for rec in self.records):
            msg = "All records must match record_size"
            raise ValueError(msg)
        if format_str is not None:
            if len(format_str) != self.field_count:
                msg = f"format length {len(format_str)} != field_count {self.field_count}"
                raise ValueError(msg)
            if record_size_for_format(format_str) != self.record_size:
                msg = (
                    f"format implies record size {record_size_for_format(format_str)}, "
                    f"header says {self.record_size}"
                )
                raise ValueError(msg)

    @classmethod
    def read(cls, data: bytes | bytearray, format_str: str | None = None) -> DbcTable:
        if len(data) < WDBC_HEADER.size:
            msg = "Data too short for WDBC header"
            raise ValueError(msg)

        magic, record_count, field_count, record_size = WDBC_HEADER.unpack_from(data, 0)
        if magic != WDBC_MAGIC:
            msg = f"Bad WDBC magic: {magic:#x}"
            raise ValueError(msg)

        string_block_size = struct.unpack_from("<I", data, 16)[0]
        header_end = 20
        records_end = header_end + record_count * record_size
        expected_len = records_end + string_block_size
        if len(data) != expected_len:
            msg = f"Expected {expected_len} bytes, got {len(data)}"
            raise ValueError(msg)

        records: list[bytearray] = []
        for i in range(record_count):
            start = header_end + i * record_size
            end = start + record_size
            records.append(bytearray(data[start:end]))

        string_block = bytearray(data[records_end:records_end + string_block_size])
        return cls(
            format_str=format_str,
            record_count=record_count,
            field_count=field_count,
            record_size=record_size,
            string_block=string_block,
            records=records,
        )

    @classmethod
    def read_file(cls, path: Path, format_str: str | None = None) -> DbcTable:
        return cls.read(path.read_bytes(), format_str=format_str)

    @classmethod
    def create_empty(cls, format_str: str, record_count: int = 0) -> DbcTable:
        """Create a new table, optionally pre-allocated with zeroed records."""
        record_size = record_size_for_format(format_str)
        records = [bytearray(record_size) for _ in range(record_count)]
        return cls(
            format_str=format_str,
            record_count=record_count,
            field_count=len(format_str),
            record_size=record_size,
            string_block=bytearray(b"\0"),
            records=records,
        )

    def write(self) -> bytes:
        string_block_size = len(self.string_block)
        out = bytearray(20 + self.record_count * self.record_size + string_block_size)
        WDBC_HEADER.pack_into(
            out,
            0,
            WDBC_MAGIC,
            self.record_count,
            self.field_count,
            self.record_size,
        )
        struct.pack_into("<I", out, 16, string_block_size)

        cursor = 20
        for record in self.records:
            out[cursor : cursor + self.record_size] = record
            cursor += self.record_size
        out[cursor:] = self.string_block
        return bytes(out)

    def write_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.write())

    def append_record(self, record: bytes | bytearray | None = None) -> int:
        if record is None:
            record = bytearray(self.record_size)
        if len(record) != self.record_size:
            msg = f"Record must be {self.record_size} bytes, got {len(record)}"
            raise ValueError(msg)
        self.records.append(bytearray(record))
        self.record_count += 1
        return len(self.records) - 1

    def _validate_record_index(self, record_index: int) -> None:
        if record_index < 0 or record_index >= len(self.records):
            msg = f"Record index out of range: {record_index}"
            raise IndexError(msg)

    def _field_spec(self, field_index: int) -> FieldSpec:
        if not self._fields:
            msg = "Table has no format string"
            raise ValueError(msg)
        if field_index < 0 or field_index >= len(self._fields):
            msg = f"Field index out of range: {field_index}"
            raise IndexError(msg)
        return self._fields[field_index]

    def get_uint8(self, record_index: int, field_index: int) -> int:
        self._validate_record_index(record_index)
        spec = self._field_spec(field_index)
        if spec.kind != FieldKind.UINT8:
            msg = f"Field {field_index} is not uint8"
            raise TypeError(msg)
        return self.records[record_index][spec.offset]

    def get_uint32(self, record_index: int, field_index: int) -> int:
        self._validate_record_index(record_index)
        spec = self._field_spec(field_index)
        if spec.kind not in {FieldKind.UINT32, FieldKind.STRING}:
            msg = f"Field {field_index} is not uint32"
            raise TypeError(msg)
        return struct.unpack_from("<I", self.records[record_index], spec.offset)[0]

    def get_float(self, record_index: int, field_index: int) -> float:
        self._validate_record_index(record_index)
        spec = self._field_spec(field_index)
        if spec.kind != FieldKind.FLOAT:
            msg = f"Field {field_index} is not float"
            raise TypeError(msg)
        return struct.unpack_from("<f", self.records[record_index], spec.offset)[0]

    def get_string(self, record_index: int, field_index: int) -> str:
        self._validate_record_index(record_index)
        spec = self._field_spec(field_index)
        if spec.kind != FieldKind.STRING:
            msg = f"Field {field_index} is not string"
            raise TypeError(msg)
        offset = struct.unpack_from("<I", self.records[record_index], spec.offset)[0]
        if offset >= len(self.string_block):
            msg = f"String offset {offset} out of range"
            raise ValueError(msg)
        end = self.string_block.index(0, offset)
        return self.string_block[offset:end].decode("utf-8")

    def set_uint8(self, record_index: int, field_index: int, value: int) -> None:
        self._validate_record_index(record_index)
        spec = self._field_spec(field_index)
        if spec.kind != FieldKind.UINT8:
            msg = f"Field {field_index} is not uint8"
            raise TypeError(msg)
        self.records[record_index][spec.offset] = value & 0xFF

    def set_uint32(self, record_index: int, field_index: int, value: int) -> None:
        self._validate_record_index(record_index)
        spec = self._field_spec(field_index)
        if spec.kind not in {FieldKind.UINT32, FieldKind.PAD_UINT32, FieldKind.STRING}:
            msg = f"Field {field_index} is not uint32"
            raise TypeError(msg)
        struct.pack_into("<I", self.records[record_index], spec.offset, value & 0xFFFFFFFF)

    def set_float(self, record_index: int, field_index: int, value: float) -> None:
        self._validate_record_index(record_index)
        spec = self._field_spec(field_index)
        if spec.kind != FieldKind.FLOAT:
            msg = f"Field {field_index} is not float"
            raise TypeError(msg)
        struct.pack_into("<f", self.records[record_index], spec.offset, value)

    def set_string(self, record_index: int, field_index: int, value: str) -> None:
        self._validate_record_index(record_index)
        spec = self._field_spec(field_index)
        if spec.kind != FieldKind.STRING:
            msg = f"Field {field_index} is not string"
            raise TypeError(msg)
        encoded = value.encode("utf-8") + b"\0"
        offset = len(self.string_block)
        self.string_block.extend(encoded)
        struct.pack_into("<I", self.records[record_index], spec.offset, offset)
