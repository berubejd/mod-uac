from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.class_quest_catalog import HUNTER_PET_SPELL_IDS
from aracgen.emit_hunter_pet import HunterPetEmitter, compute_hunter_pet_spells
from aracgen.matrix import class_bit
from aracgen.sources import cached_client_data_zip


def test_hunter_pet_grants_all_hunters_classwide() -> None:
    result = compute_hunter_pet_spells()
    assert len(result.spell_rows) == len(HUNTER_PET_SPELL_IDS)
    assert {row.spell_id for row in result.spell_rows} == set(HUNTER_PET_SPELL_IDS)


def test_hunter_pet_install_uses_class_mask_only() -> None:
    install = HunterPetEmitter().render_install_files()["hunter_pet_spell_custom"]
    assert f"VALUES (0, {class_bit(3)}, 1515," in install
    assert "PlayerStart.CustomSpells = 1" in install


def test_hunter_pet_uninstall_targets_classwide_rows() -> None:
    emitter = HunterPetEmitter()
    uninstall = emitter.render_uninstall_files()["hunter_pet_spell_custom"]
    assert (
        f"DELETE FROM `playercreateinfo_spell_custom` "
        f"WHERE `racemask` = 0 AND `classmask` = {class_bit(3)} AND `Spell` = 1515;"
    ) in uninstall


@pytest.mark.skipif(
    not cached_client_data_zip(Path(__file__).resolve().parents[2] / "data" / "cache").exists(),
    reason="canonical client-data cache not present",
)
def test_hunter_pet_spell_dbc_sets_level_one() -> None:
    emitter = HunterPetEmitter()
    sql = emitter.render_install_files()["hunter_pet_spell_dbc"]
    assert "REPLACE INTO `spell_dbc`" in sql
    assert "DELETE FROM `spell_dbc`" in emitter.render_uninstall_files()["hunter_pet_spell_dbc"]
    assert "4294967295" not in sql
    for spell_id in HUNTER_PET_SPELL_IDS:
        assert f"-- spell {spell_id}" in sql
    # Tame Beast (1515): patched row should expose level 1 in aligned BaseLevel/SpellLevel slots.
    tame_beast = sql.split("-- spell 1515", maxsplit=1)[1].split("-- spell ", maxsplit=1)[0]
    assert ", 1, 1," in tame_beast or ", 1, 1, " in tame_beast
