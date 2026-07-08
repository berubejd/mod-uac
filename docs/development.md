# mod-uac — Development Guide

Regenerating checked-in artifacts, generator tooling reference, and the manual QA checklist.
For architecture and design rationale, see the
[Engineering Implementation](mod-uac-engineering-implementation.md).

## Environment setup

```bash
cd tools
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Run generators from the **mod-uac repo root** (paths below are relative to that root).

PyMySQL is required only for snapshot capture (`pip install -r tools/requirements.txt`).
Emitters read the JSON snapshot and do not connect to MySQL.

## `generate_canonical.py`

Writes checked-in SQL under `data/sql/`, all three client MPQs under `client-patch/`, and
`docs/trainer_worksheet.md`. Uses pinned
[wowgaming/client-data](https://github.com/wowgaming/client-data) tag **v19** (cached under
`data/cache/`), the baked world snapshot under `data/snapshot/`, and minimal outfit item
metadata in `data/item_prototypes.json`.

```bash
pip install -r tools/requirements.txt
python tools/generate_canonical.py
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--pin` | `v19` | wowgaming/client-data release tag |
| `--cache-dir` | `data/cache/` | Download cache for client-data zip |
| `--refresh` | off | Re-download client data even if cached |
| `--dbc-dir` | *(download)* | Offline override: read DBCs from this directory instead |
| `--db-max-id` | `0` | `MAX(ID)` already in `skillraceclassinfo_dbc` on your world DB |
| `--outfit-db-max-id` | `0` | `MAX(ID)` already in `charstartoutfit_dbc` on your world DB |
| `--snapshot` | baked pointer | Path to a world DB snapshot JSON |
| `--snapshot-dir` | `data/snapshot/` | Directory with `world.latest.json` when `--snapshot` is omitted |
| `--refresh-snapshot` | off | Capture a fresh snapshot from your world DB before emitting SQL |
| `--snapshot-config` | `tools/snapshot.conf` | Config file for `--refresh-snapshot` (see below) |
| `--dsn` | *(from config)* | AC-style `WorldDatabaseInfo`: `host;port;user;password;database` |
| `--trainer-guid-base` | `6000000` | Base GUID for mod-uac starter trainer spawns |
| `--trainer-overrides` | `data/trainer_overrides.yaml` | YAML placement/entry overrides |

Refresh the snapshot from your live world DB, then regenerate everything:

```bash
python tools/generate_canonical.py --refresh-snapshot \
  --dsn "127.0.0.1;3306;acore;password;acore_world"
```

Or copy [tools/snapshot.conf.dist](../tools/snapshot.conf.dist) to `tools/snapshot.conf`, set
`WorldDatabaseInfo`, and run with `--refresh-snapshot` (no `--dsn` needed). You can also set
`MOD_UAC_WORLD_DATABASE_INFO` or `MOD_UAC_SNAPSHOT_CONFIG` instead of editing the file.

## `generate_local.py`

Operator-specific output when your DBC baseline or overlay max IDs differ from stock. Writes
SQL and a `standard`-style `patch-z.mpq` to `tools/output/` by default (not the checked-in
`data/sql/` tree).

```bash
python tools/generate_local.py /path/to/dbc --db-max-id 970
python tools/generate_local.py /path/to/dbc -o /tmp/mod-uac-sql
```

| Flag | Default | Purpose |
|------|---------|---------|
| `dbc_dir` | *(required)* | Path to your `dbc/` directory (e.g. server `Data/dbc/`) |
| `-o`, `--output-dir` | `tools/output/` | Directory for generated SQL and MPQ |
| `--db-max-id` | `0` | `MAX(ID)` from `skillraceclassinfo_dbc` on your world DB |
| `--outfit-db-max-id` | `0` | `MAX(ID)` from `charstartoutfit_dbc` on your world DB |
| `--snapshot` | baked pointer | Same as `generate_canonical.py` |
| `--snapshot-dir` | `data/snapshot/` | Same as `generate_canonical.py` |
| `--refresh-snapshot` | off | Same as `generate_canonical.py` |
| `--snapshot-config` | `tools/snapshot.conf` | Same as `generate_canonical.py` |
| `--dsn` | *(from config)* | Same as `generate_canonical.py` |
| `--trainer-guid-base` | `6000000` | Same as `generate_canonical.py` |
| `--trainer-overrides` | `data/trainer_overrides.yaml` | Same as `generate_canonical.py` |

Local run with a fresh snapshot and custom overrides:

```bash
python tools/generate_local.py /path/to/dbc \
  --refresh-snapshot --trainer-overrides data/trainer_overrides.yaml
```

## `capture_snapshot.py`

Standalone snapshot capture (schema + trainer extracts + outfit item prototypes). The
generator front-ends call the same logic when you pass `--refresh-snapshot`; use this tool
when you only want to refresh the baked JSON artifacts.

```bash
python tools/capture_snapshot.py --dsn "127.0.0.1;3306;acore;password;acore_world"
python tools/capture_snapshot.py --config tools/snapshot.conf --output-dir data/snapshot/
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--config` | `tools/snapshot.conf` | Snapshot config (`WorldDatabaseInfo = "host;port;user;pass;db"`) |
| `--dsn` | *(from config)* | AC-style world DB connection string |
| `--output-dir` | `data/snapshot/` | Writes `world.<version>.json` and updates `world.latest.json` |

Also writes `data/item_prototypes.json` (62 outfit item class/subclass pairs) when canonical
client-data is cached under `data/cache/`.

## HD outfit baseline refresh

The `enhanced/` client patch keeps a deduplicated HD `CharStartOutfit` baseline in
`data/client/hd_outfit_templates.json` and `hd_outfit_stock_index.json`, extracted from the
official HD `patch-k`. Refresh from a new `patch-k.mpq` via
`tools/extract_hd_outfit_baseline.py`, then regenerate.

## Trainer overrides

Edit [data/trainer_overrides.yaml](../data/trainer_overrides.yaml) to tweak entry, anchor
class, or spawn coordinates for specific zone/class rows (labels match
[trainer_worksheet.md](trainer_worksheet.md)). Regenerate SQL after changes. Full emitter
design: [mod-uac-trainer-emitter-spec.md](mod-uac-trainer-emitter-spec.md).

## Manual QA checklist

- [ ] Apply install SQL on a stock AC world DB; worldserver starts cleanly
- [ ] Remove client patch; off-race combos absent on creation screen
- [ ] Install one `client-patch/*/patch-z.mpq`; all race/class tiles selectable
- [ ] On an off-race combo (e.g. Night Elf Shaman), item tooltips show red for gear you cannot wear yet (mail at level 1, daggers)
- [ ] Dressing-room preview shows starter gear on a new combo (e.g. Tauren Mage), not naked
- [ ] Create off-race shaman; totems display with faction-appropriate models (not invisible)
- [ ] Create Dwarf Warlock; complete imp quest chain in Dun Morogh (tier A)
- [ ] Create Night Elf Warlock; has Summon Imp at creation (tier C spell grant)
- [ ] Create off-race warrior/shaman/druid/paladin; reference class quest chain is available after travel (§8.3)
- [ ] Create an off-race combo with a new starter trainer (e.g. Human Shaman); trainer is present in Northshire
- [ ] Set `PlayerStart.CustomSpells = 1`; create any hunter at level 1; Tame Beast works on a nearby beast
- [ ] Run hunter pet uninstall SQL only; new hunters lose pet spells until level 10
- [ ] Run uninstall SQL; new combos no longer creatable; overlay IDs gone
- [ ] Remove MPQ; client reverts to stock creation screen
