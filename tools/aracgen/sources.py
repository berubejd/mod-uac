"""DBC file sources for the generator front-ends."""

from __future__ import annotations

import zipfile
from abc import ABC, abstractmethod
from pathlib import Path

import requests

from aracgen.dbc import DbcTable
from aracgen.formats import (
    CHAR_BASE_INFO,
    CHAR_START_OUTFIT,
    SKILL_LINE_ABILITY,
    SKILL_RACE_CLASS_INFO,
)

DEFAULT_CANONICAL_PIN = "v19"
CLIENT_DATA_REPO = "wowgaming/client-data"
CLIENT_DATA_ASSET = "Data.zip"
DOWNLOAD_CHUNK_BYTES = 1024 * 1024


def client_data_release_url(pin: str = DEFAULT_CANONICAL_PIN) -> str:
    return f"https://github.com/{CLIENT_DATA_REPO}/releases/download/{pin}/{CLIENT_DATA_ASSET}"


def cached_client_data_zip(cache_dir: Path, pin: str = DEFAULT_CANONICAL_PIN) -> Path:
    return cache_dir / f"client-data-{pin}.zip"


def validate_client_data_zip(path: Path) -> None:
    """Raise ValueError if path is not a readable wowgaming client-data zip."""
    if not path.is_file() or not zipfile.is_zipfile(path):
        msg = f"Invalid client-data cache (not a zip): {path}"
        raise ValueError(msg)
    with zipfile.ZipFile(path) as archive:
        try:
            archive.getinfo("dbc/SkillRaceClassInfo.dbc")
        except KeyError as exc:
            msg = f"Invalid client-data cache (missing DBC members): {path}"
            raise ValueError(msg) from exc


def download_client_data(
    dest: Path,
    pin: str = DEFAULT_CANONICAL_PIN,
    *,
    refresh: bool = False,
    timeout_seconds: float = 120.0,
) -> Path:
    """Download wowgaming/client-data release zip to dest if missing or refresh=True."""
    if dest.is_file() and not refresh:
        try:
            validate_client_data_zip(dest)
            return dest
        except ValueError:
            dest.unlink()

    dest.parent.mkdir(parents=True, exist_ok=True)
    url = client_data_release_url(pin)
    tmp = dest.with_suffix(".zip.part")

    try:
        with requests.get(url, stream=True, timeout=timeout_seconds) as response:
            response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    if chunk:
                        handle.write(chunk)
        validate_client_data_zip(tmp)
        tmp.replace(dest)
    except Exception:
        if tmp.is_file():
            tmp.unlink()
        raise

    return dest


class DbcSource(ABC):
    @abstractmethod
    def load_skill_race_class_info(self) -> DbcTable:
        raise NotImplementedError

    @abstractmethod
    def load_char_base_info(self) -> DbcTable:
        raise NotImplementedError

    @abstractmethod
    def load_char_start_outfit(self) -> DbcTable:
        raise NotImplementedError

    @abstractmethod
    def load_skill_line_ability(self) -> DbcTable:
        raise NotImplementedError


class LocalDbcSource(DbcSource):
    """Read DBC files from a directory (operator WoW Data/dbc or extracted client data)."""

    def __init__(self, dbc_dir: Path) -> None:
        self.dbc_dir = dbc_dir

    def _read(self, filename: str, format_str: str) -> DbcTable:
        path = self.dbc_dir / filename
        if not path.is_file():
            msg = f"DBC not found: {path}"
            raise FileNotFoundError(msg)
        return DbcTable.read_file(path, format_str=format_str)

    def load_skill_race_class_info(self) -> DbcTable:
        return self._read("SkillRaceClassInfo.dbc", SKILL_RACE_CLASS_INFO)

    def load_char_base_info(self) -> DbcTable:
        return self._read("CharBaseInfo.dbc", CHAR_BASE_INFO)

    def load_char_start_outfit(self) -> DbcTable:
        return self._read("CharStartOutfit.dbc", CHAR_START_OUTFIT)

    def load_skill_line_ability(self) -> DbcTable:
        return self._read("SkillLineAbility.dbc", SKILL_LINE_ABILITY)


class ZipDbcSource(DbcSource):
    """Read DBC files from a wowgaming-style Data.zip (dbc/ prefix)."""

    def __init__(self, zip_path: Path) -> None:
        self.zip_path = zip_path

    def _read(self, filename: str, format_str: str) -> DbcTable:
        with zipfile.ZipFile(self.zip_path) as archive:
            return DbcTable.read(archive.read(f"dbc/{filename}"), format_str=format_str)

    def load_skill_race_class_info(self) -> DbcTable:
        return self._read("SkillRaceClassInfo.dbc", SKILL_RACE_CLASS_INFO)

    def load_char_base_info(self) -> DbcTable:
        return self._read("CharBaseInfo.dbc", CHAR_BASE_INFO)

    def load_char_start_outfit(self) -> DbcTable:
        return self._read("CharStartOutfit.dbc", CHAR_START_OUTFIT)

    def load_skill_line_ability(self) -> DbcTable:
        return self._read("SkillLineAbility.dbc", SKILL_LINE_ABILITY)


class CanonicalDbcSource(DbcSource):
    """Fetch and cache pinned wowgaming/client-data, then read DBCs from the zip."""

    def __init__(
        self,
        pin: str = DEFAULT_CANONICAL_PIN,
        cache_dir: Path | None = None,
        *,
        refresh: bool = False,
    ) -> None:
        self.pin = pin
        self.cache_dir = cache_dir
        self.refresh = refresh
        self._zip_path = self._ensure_cache()

    def _ensure_cache(self) -> Path:
        cache_root = self.cache_dir or Path(__file__).resolve().parents[2] / "data" / "cache"
        dest = cached_client_data_zip(cache_root, self.pin)
        return download_client_data(dest, self.pin, refresh=self.refresh)

    @property
    def zip_path(self) -> Path:
        return self._zip_path

    def _zip_source(self) -> ZipDbcSource:
        return ZipDbcSource(self._zip_path)

    def load_skill_race_class_info(self) -> DbcTable:
        return self._zip_source().load_skill_race_class_info()

    def load_char_base_info(self) -> DbcTable:
        return self._zip_source().load_char_base_info()

    def load_char_start_outfit(self) -> DbcTable:
        return self._zip_source().load_char_start_outfit()

    def load_skill_line_ability(self) -> DbcTable:
        return self._zip_source().load_skill_line_ability()
