from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from aracgen.cli import (
    add_snapshot_cli_args,
    add_trainer_cli_args,
    resolve_generation_snapshot,
    validate_trainer_guid_base,
    write_trainer_sql,
)
from aracgen.emit_trainers import regenerate_checked_in_trainer_sql
from aracgen.snapshot import load_snapshot, resolve_baked_snapshot_path
from aracgen.snapshot_model import MOD_UAC_CREATURE_GUID_MAX
from aracgen.trainer_catalog import TRAINER_GUID_BASE

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = ROOT / "data" / "snapshot"
OVERRIDES_PATH = ROOT / "data" / "trainer_overrides.yaml"
CHECKED_IN_INSTALL = ROOT / "data" / "sql" / "db-world" / "mod_uac_starter_trainers.sql"
CHECKED_IN_UNINSTALL = (
    ROOT / "data" / "sql" / "db-uninstall" / "mod_uac_starter_trainers_uninstall.sql"
)
CHECKED_IN_WORKSHEET = ROOT / "docs" / "trainer_worksheet.md"


def _trainer_args(**overrides: object) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_snapshot_cli_args(parser)
    add_trainer_cli_args(parser)
    defaults = {
        "snapshot": None,
        "snapshot_dir": SNAPSHOT_DIR,
        "refresh_snapshot": False,
        "snapshot_config": None,
        "dsn": None,
        "trainer_guid_base": TRAINER_GUID_BASE,
        "trainer_overrides": OVERRIDES_PATH,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture(scope="module")
def baked_snapshot():
    try:
        return load_snapshot(snapshot_dir=SNAPSHOT_DIR)
    except FileNotFoundError:
        pytest.skip("baked world snapshot not present")


def test_resolve_generation_snapshot_uses_baked_pointer(baked_snapshot) -> None:
    args = _trainer_args()
    snapshot = resolve_generation_snapshot(args)
    assert snapshot.version == baked_snapshot.version


def test_resolve_generation_snapshot_from_explicit_path(baked_snapshot) -> None:
    versioned = resolve_baked_snapshot_path(SNAPSHOT_DIR)
    args = _trainer_args(snapshot=versioned)
    snapshot = resolve_generation_snapshot(args)
    assert snapshot.version == baked_snapshot.version


def test_write_trainer_sql_matches_checked_in_artifacts(
    baked_snapshot,
    tmp_path: Path,
) -> None:
    install = tmp_path / "mod_uac_starter_trainers.sql"
    uninstall = tmp_path / "mod_uac_starter_trainers_uninstall.sql"
    worksheet = tmp_path / "trainer_worksheet.md"

    write_trainer_sql(
        install,
        uninstall,
        worksheet,
        snapshot=baked_snapshot,
        overrides_path=OVERRIDES_PATH,
    )

    expected_install, expected_uninstall, expected_worksheet = (
        regenerate_checked_in_trainer_sql()
    )
    assert install.read_text(encoding="utf-8") == expected_install
    assert uninstall.read_text(encoding="utf-8") == expected_uninstall
    assert worksheet.read_text(encoding="utf-8") == expected_worksheet


@pytest.mark.skipif(
    not CHECKED_IN_INSTALL.is_file(),
    reason="checked-in trainer SQL not present",
)
def test_checked_in_trainer_sql_matches_regeneration() -> None:
    install, uninstall, worksheet = regenerate_checked_in_trainer_sql()
    assert CHECKED_IN_INSTALL.read_text(encoding="utf-8") == install
    assert CHECKED_IN_UNINSTALL.read_text(encoding="utf-8") == uninstall
    assert CHECKED_IN_WORKSHEET.read_text(encoding="utf-8") == worksheet


def test_validate_trainer_guid_base_rejects_outside_band() -> None:
    with pytest.raises(ValueError, match="reserved creature band"):
        validate_trainer_guid_base(MOD_UAC_CREATURE_GUID_MAX + 1)
