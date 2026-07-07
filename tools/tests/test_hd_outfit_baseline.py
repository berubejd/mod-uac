from __future__ import annotations

import hashlib

import pytest

from aracgen.hd_outfit_baseline import (
    HD_OUTFIT_STOCK_INDEX_PATH,
    HD_OUTFIT_TEMPLATES_PATH,
    load_hd_charstartoutfit_baseline,
    load_hd_outfit_catalog,
)

# Byte-exact expansion of checked-in JSON (126 stock rows from HD patch-k).
EXPANDED_BASELINE_SHA256 = (
    "2c7ede0e0fc3c3449a846e92d3084657bd5d60fee46cdea5937fdbf3eb9bf8c2"
)
EXPANDED_BASELINE_BYTES = 37_317


@pytest.fixture(scope="session")
def hd_catalog():
    if not HD_OUTFIT_TEMPLATES_PATH.is_file() or not HD_OUTFIT_STOCK_INDEX_PATH.is_file():
        pytest.skip("HD outfit JSON catalog not found")
    return load_hd_outfit_catalog()


def test_hd_catalog_deduplication(hd_catalog) -> None:
    assert len(hd_catalog.stock) == 126
    assert len(hd_catalog.templates) == 54


def test_hd_catalog_expands_to_golden_dbc_bytes(hd_catalog) -> None:
    expanded = load_hd_charstartoutfit_baseline()
    assert expanded.record_count == len(hd_catalog.stock)
    payload = expanded.write()
    assert len(payload) == EXPANDED_BASELINE_BYTES
    assert hashlib.sha256(payload).hexdigest() == EXPANDED_BASELINE_SHA256
