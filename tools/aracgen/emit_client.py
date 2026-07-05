"""Emit the universal client MPQ patch (Phase 1e)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aracgen.dbc import DbcTable
from aracgen.formats import CHAR_BASE_INFO
from aracgen.matrix import PLAYABLE_CLASSES, PLAYABLE_RACES
from aracgen.mpq import MpqFileEntry, build_mpq_v1

# WoW 3.3.5a client lookup path for CharBaseInfo.dbc.
CHAR_BASE_INFO_MPQ_PATH = "DBFilesClient\\CharBaseInfo.dbc"
LISTFILE_MPQ_PATH = "(listfile)"


def build_char_base_info_table() -> DbcTable:
    """Full playable race × class matrix (100 records including DK)."""
    table = DbcTable.create_empty(CHAR_BASE_INFO)
    for race_id in sorted(PLAYABLE_RACES):
        for class_id in sorted(PLAYABLE_CLASSES):
            index = table.record_count
            table.append_record()
            table.set_uint8(index, 0, race_id)
            table.set_uint8(index, 1, class_id)
    return table


def build_client_patch_bytes() -> bytes:
    char_base_info = build_char_base_info_table().write()
    listfile = f"{CHAR_BASE_INFO_MPQ_PATH}\r\n".encode("ascii")
    return build_mpq_v1(
        (
            MpqFileEntry(path=LISTFILE_MPQ_PATH, data=listfile),
            MpqFileEntry(path=CHAR_BASE_INFO_MPQ_PATH, data=char_base_info),
        )
    )


@dataclass(slots=True)
class ClientPatchEmitter:
    def compute(self) -> bytes:
        return build_client_patch_bytes()

    def write(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.compute())
