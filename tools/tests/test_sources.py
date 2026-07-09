from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aracgen.sources import (
    DEFAULT_CANONICAL_PIN,
    CanonicalDbcSource,
    LocalDbcSource,
    ZipDbcSource,
    cached_client_data_zip,
    client_data_release_url,
    download_client_data,
    validate_client_data_zip,
)

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "cache" / "client-data-v19.zip"


def test_client_data_release_url() -> None:
    assert client_data_release_url("v19") == (
        "https://github.com/wowgaming/client-data/releases/download/v19/Data.zip"
    )


def test_cached_client_data_zip_name() -> None:
    assert cached_client_data_zip(Path("/tmp/cache"), "v19") == Path(
        "/tmp/cache/client-data-v19.zip"
    )


def test_validate_client_data_zip_rejects_zip_missing_dbc(tmp_path: Path) -> None:
    import zipfile as zf

    bad = tmp_path / "empty.zip"
    with zf.ZipFile(bad, "w") as archive:
        archive.writestr("readme.txt", "no dbc here")

    with pytest.raises(ValueError, match="missing DBC members"):
        validate_client_data_zip(bad)


def test_validate_client_data_zip_rejects_garbage(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not-a-zip")
    with pytest.raises(ValueError, match="Invalid client-data cache"):
        validate_client_data_zip(bad)


def test_validate_client_data_zip_accepts_fixture() -> None:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Fixture zip not found: {DATA_ZIP}")
    validate_client_data_zip(DATA_ZIP)


def test_download_client_data_redownloads_corrupt_cache(tmp_path: Path) -> None:
    dest = tmp_path / "client-data-v19.zip"
    dest.write_bytes(b"corrupt")

    payload = b"still-not-a-zip"
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    response.raise_for_status.return_value = None
    response.iter_content.return_value = [payload]

    with patch("aracgen.sources.requests.get", return_value=response):
        with pytest.raises(ValueError, match="Invalid client-data cache"):
            download_client_data(dest, "v19", refresh=False)

    assert not dest.exists()


def test_download_client_data_uses_cache_without_network(tmp_path: Path) -> None:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Fixture zip not found: {DATA_ZIP}")

    dest = tmp_path / "client-data-v19.zip"
    shutil.copy(DATA_ZIP, dest)
    validate_client_data_zip(dest)

    with patch("aracgen.sources.requests.get") as mock_get:
        result = download_client_data(dest, DEFAULT_CANONICAL_PIN, refresh=False)
        mock_get.assert_not_called()

    assert result == dest


def test_download_client_data_fetches_when_missing(tmp_path: Path) -> None:
    dest = tmp_path / "client-data-v19.zip"
    if not DATA_ZIP.is_file():
        pytest.skip(f"Fixture zip not found: {DATA_ZIP}")

    payload = DATA_ZIP.read_bytes()

    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    response.raise_for_status.return_value = None
    response.iter_content.return_value = [payload]

    with patch("aracgen.sources.requests.get", return_value=response) as mock_get:
        result = download_client_data(dest, "v19", refresh=False)

    mock_get.assert_called_once_with(client_data_release_url("v19"), stream=True, timeout=120.0)
    validate_client_data_zip(result)


def test_canonical_dbc_source_reads_from_cache(tmp_path: Path) -> None:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Fixture zip not found: {DATA_ZIP}")

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    shutil.copy(DATA_ZIP, cached_client_data_zip(cache_dir, DEFAULT_CANONICAL_PIN))

    with patch("aracgen.sources.requests.get") as mock_get:
        source = CanonicalDbcSource(pin=DEFAULT_CANONICAL_PIN, cache_dir=cache_dir)
        table = source.load_skill_race_class_info()
        mock_get.assert_not_called()

    assert table.record_count == 241


def test_zip_and_local_sources_match_on_extracted_dbc(tmp_path: Path) -> None:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Fixture zip not found: {DATA_ZIP}")

    import zipfile

    dbc_dir = tmp_path / "dbc"
    dbc_dir.mkdir()
    with zipfile.ZipFile(DATA_ZIP) as archive:
        for name in (
            "dbc/SkillRaceClassInfo.dbc",
            "dbc/CharBaseInfo.dbc",
            "dbc/CharStartOutfit.dbc",
        ):
            target = dbc_dir / Path(name).name
            target.write_bytes(archive.read(name))

    zip_source = ZipDbcSource(DATA_ZIP)
    local_source = LocalDbcSource(dbc_dir)

    assert (
        zip_source.load_skill_race_class_info().write()
        == local_source.load_skill_race_class_info().write()
    )
