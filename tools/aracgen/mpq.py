"""Pure-Python MPQ v1 writer (and minimal reader for tests)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

MPQ_MAGIC = b"MPQ\x1a"
MPQ_HEADER_SIZE = 32
MPQ_HASH_ENTRY_SIZE = 16
MPQ_BLOCK_ENTRY_SIZE = 16

MPQ_FILE_EXISTS = 0x80000000
MPQ_FILE_SINGLE_UNIT = 0x01000000

HASH_TABLE_KEY = "(hash table)"
BLOCK_TABLE_KEY = "(block table)"

HASH_TABLE_OFFSET = 0
HASH_NAME_A = 1
HASH_NAME_B = 2
HASH_FILE_KEY = 3


def _prepare_encryption_table() -> list[int]:
    table: list[int] = [0] * 0x500
    seed = 0x00100001
    for index1 in range(0x100):
        index2 = index1
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp1 = (seed & 0xFFFF) << 0x10
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp2 = seed & 0xFFFF
            table[index2] = temp1 | temp2
            index2 += 0x100
    return table


ENCRYPTION_TABLE = _prepare_encryption_table()


def hash_string(value: str, hash_type: int) -> int:
    seed1 = 0x7FED7FED
    seed2 = 0xEEEEEEEE
    for ch in value.upper():
        code = ord(ch)
        lookup = ENCRYPTION_TABLE[(hash_type << 8) + code]
        seed1 = (lookup ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed2 = (code + seed1 + seed2 + ((seed2 << 5) + 3)) & 0xFFFFFFFF
    return seed1


def encrypt(data: bytes, key: int) -> bytes:
    if len(data) % 4:
        msg = "encrypt length must be a multiple of 4"
        raise ValueError(msg)
    out = bytearray()
    dw_key = key & 0xFFFFFFFF
    seed = 0xEEEEEEEE
    for offset in range(0, len(data), 4):
        plain = struct.unpack_from("<I", data, offset)[0]
        seed = (seed + ENCRYPTION_TABLE[0x400 + (dw_key & 0xFF)]) & 0xFFFFFFFF
        cipher = (plain ^ (dw_key + seed)) & 0xFFFFFFFF
        dw_key = (((~dw_key) << 0x15) + 0x11111111) | (dw_key >> 0x0B)
        dw_key &= 0xFFFFFFFF
        seed = (plain + seed + ((seed << 5) + 3)) & 0xFFFFFFFF
        out.extend(struct.pack("<I", cipher))
    return bytes(out)


def decrypt(data: bytes, key: int) -> bytes:
    if len(data) % 4:
        msg = "decrypt length must be a multiple of 4"
        raise ValueError(msg)
    out = bytearray()
    dw_key = key & 0xFFFFFFFF
    seed = 0xEEEEEEEE
    for offset in range(0, len(data), 4):
        cipher = struct.unpack_from("<I", data, offset)[0]
        seed = (seed + ENCRYPTION_TABLE[0x400 + (dw_key & 0xFF)]) & 0xFFFFFFFF
        plain = (cipher ^ (dw_key + seed)) & 0xFFFFFFFF
        dw_key = (((~dw_key) << 0x15) + 0x11111111) | (dw_key >> 0x0B)
        dw_key &= 0xFFFFFFFF
        seed = (plain + seed + ((seed << 5) + 3)) & 0xFFFFFFFF
        out.extend(struct.pack("<I", plain))
    return bytes(out)


def _next_power_of_two(value: int) -> int:
    power = 1
    while power < value:
        power <<= 1
    return power


@dataclass(frozen=True, slots=True)
class _HashEntry:
    hash_a: int
    hash_b: int
    locale: int
    platform: int
    block_index: int

    def pack(self) -> bytes:
        return struct.pack(
            "<2I2HI",
            self.hash_a,
            self.hash_b,
            self.locale,
            self.platform,
            self.block_index,
        )


@dataclass(frozen=True, slots=True)
class _BlockEntry:
    offset: int
    archived_size: int
    size: int
    flags: int

    def pack(self) -> bytes:
        return struct.pack("<4I", self.offset, self.archived_size, self.size, self.flags)


@dataclass(frozen=True, slots=True)
class MpqFileEntry:
    path: str
    data: bytes


def build_mpq_v1(files: tuple[MpqFileEntry, ...], *, hash_table_size: int | None = None) -> bytes:
    """Build an uncompressed MPQ v1 archive containing the given files."""
    if not files:
        msg = "MPQ archive requires at least one file"
        raise ValueError(msg)

    table_size = hash_table_size or _next_power_of_two(max(len(files) * 4, 256))
    if table_size < len(files):
        msg = "hash table is too small for the file count"
        raise ValueError(msg)

    hash_table = [
        _HashEntry(0, 0, 0xFFFF, 0, 0xFFFFFFFF) for _ in range(table_size)
    ]
    block_table: list[_BlockEntry] = []

    file_data = bytearray()
    data_cursor = MPQ_HEADER_SIZE

    for entry in files:
        block_index = len(block_table)
        block_table.append(
            _BlockEntry(
                offset=data_cursor,
                archived_size=len(entry.data),
                size=len(entry.data),
                flags=MPQ_FILE_EXISTS | MPQ_FILE_SINGLE_UNIT,
            )
        )
        file_data.extend(entry.data)
        data_cursor += len(entry.data)

        hash_a = hash_string(entry.path, HASH_NAME_A)
        hash_b = hash_string(entry.path, HASH_NAME_B)
        home = hash_string(entry.path, HASH_TABLE_OFFSET) & (table_size - 1)
        placed = False
        for probe in range(table_size):
            slot = (home + probe) & (table_size - 1)
            if hash_table[slot].block_index == 0xFFFFFFFF:
                hash_table[slot] = _HashEntry(hash_a, hash_b, 0, 0, block_index)
                placed = True
                break
        if not placed:
            msg = f"hash table overflow inserting {entry.path!r}"
            raise RuntimeError(msg)

    hash_table_offset = MPQ_HEADER_SIZE + len(file_data)
    block_table_offset = hash_table_offset + table_size * MPQ_HASH_ENTRY_SIZE

    hash_blob = b"".join(entry.pack() for entry in hash_table)
    block_blob = b"".join(entry.pack() for entry in block_table)
    hash_key = hash_string(HASH_TABLE_KEY, HASH_FILE_KEY)
    block_key = hash_string(BLOCK_TABLE_KEY, HASH_FILE_KEY)

    archive_size = block_table_offset + len(block_table) * MPQ_BLOCK_ENTRY_SIZE
    header = struct.pack(
        "<4s2I2H4I",
        MPQ_MAGIC,
        MPQ_HEADER_SIZE,
        archive_size,
        0,  # format version (original MPQ)
        3,  # sector size shift -> 4096-byte sectors
        hash_table_offset,
        block_table_offset,
        table_size,
        len(block_table),
    )

    return (
        header
        + bytes(file_data)
        + encrypt(hash_blob, hash_key)
        + encrypt(block_blob, block_key)
    )


def read_mpq_file(archive: bytes, filename: str) -> bytes:
    """Read one uncompressed single-unit file from an MPQ v1 archive (test helper)."""
    if archive[:4] != MPQ_MAGIC:
        msg = "not an MPQ archive"
        raise ValueError(msg)

    (
        _magic,
        header_size,
        archive_size,
        _format_version,
        _sector_shift,
        hash_table_offset,
        block_table_offset,
        hash_table_entries,
        block_table_entries,
    ) = struct.unpack("<4s2I2H4I", archive[:32])

    if header_size != MPQ_HEADER_SIZE or archive_size > len(archive):
        msg = "unsupported MPQ header"
        raise ValueError(msg)

    hash_key = hash_string(HASH_TABLE_KEY, HASH_FILE_KEY)
    block_key = hash_string(BLOCK_TABLE_KEY, HASH_FILE_KEY)

    hash_blob = decrypt(
        archive[hash_table_offset : hash_table_offset + hash_table_entries * MPQ_HASH_ENTRY_SIZE],
        hash_key,
    )
    block_end = block_table_offset + block_table_entries * MPQ_BLOCK_ENTRY_SIZE
    block_blob = decrypt(archive[block_table_offset:block_end], block_key)

    hash_a = hash_string(filename, HASH_NAME_A)
    hash_b = hash_string(filename, HASH_NAME_B)
    home = hash_string(filename, HASH_TABLE_OFFSET) & (hash_table_entries - 1)

    block_index: int | None = None
    for probe in range(hash_table_entries):
        slot = (home + probe) & (hash_table_entries - 1)
        entry_hash_a, entry_hash_b, _locale, _platform, entry_block = struct.unpack_from(
            "<2I2HI",
            hash_blob,
            slot * MPQ_HASH_ENTRY_SIZE,
        )
        if entry_block == 0xFFFFFFFF:
            break
        if entry_hash_a == hash_a and entry_hash_b == hash_b:
            block_index = entry_block
            break

    if block_index is None:
        msg = f"{filename!r} not found in MPQ"
        raise KeyError(msg)

    offset, archived_size, size, flags = struct.unpack_from(
        "<4I",
        block_blob,
        block_index * MPQ_BLOCK_ENTRY_SIZE,
    )
    if not (flags & MPQ_FILE_EXISTS):
        msg = f"{filename!r} block is not a file"
        raise KeyError(msg)

    data = archive[offset : offset + archived_size]
    if len(data) != size:
        msg = f"{filename!r} size mismatch"
        raise ValueError(msg)
    return data
