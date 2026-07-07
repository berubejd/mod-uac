# mod-uac

Unlock All Classes — AzerothCore WotLK 3.3.5a module.

## Purpose

Allow any playable WotLK race to create and play any playable class — the combinations Blizzard
did not ship in 3.3.5a (e.g. Tauren Mage, Human Shaman, Blood Elf Warrior). The module is built for
**operators running stock or lightly customized AzerothCore**: every change is **revertable**, artifacts
are **generated from known sources** (no mystery binaries on the server), and install is handled by
the normal DB updater plus one small client patch.

Deep architecture, combo matrix, and phasing: [docs/mod-uac-engineering-implementation.md](docs/mod-uac-engineering-implementation.md).

## Goals

- **Human-readable server data.** Proficiencies, spawns, kits, totems, and quest gates ship as SQL
  under `data/sql/db-world/`, each file with a matching revert in `data/sql/db-uninstall/`.
- **No server-side binary DBC edits.** Skill overlays use AzerothCore's `skillraceclassinfo_dbc`
  world-table merge (same mechanism as other `*_dbc` overlays) — not patched `.dbc` files on disk.
- **Three checked-in client patches.** All named `patch-z.mpq` under `client-patch/` — pick one
  (unlock-only, standard, or enhanced). The server never reads these files; `playercreateinfo`
  rows are the server-side gate.
- **Reproducible generation.** Checked-in SQL and MPQ come from `tools/generate_canonical.py`
  (pinned [wowgaming/client-data](https://github.com/wowgaming/client-data) tag **v19**). Operators
  with custom DBC baselines can regenerate via `tools/generate_local.py`.

## What the mod adds

Stock AzerothCore ships **62** valid race/class pairs. mod-uac adds **38** more (100 playable tiles
on the client, including Death Knight — already all-race in stock `playercreateinfo` and unchanged by
the SQL emitters). Examples: Human Hunter, Orc Paladin, Tauren Mage, Night Elf Warlock, Blood Elf
Warrior, Gnome Shaman.

These combinations are **community expansions**, not Blizzard-shipped pairs. In-game they work like
normal characters once created; some class quests still require **travel** to reference zones (see
class quest summary below). Starter trainers are placed in each race's starting zone for the new
combos.

For each new combo the module provides:

| Concern | Mechanism |
|---------|-----------|
| Creation allowed (server) | `playercreateinfo` + action/item/spell rows |
| Armor & weapon skills | `skillraceclassinfo_dbc` overlay |
| Creation screen tiles (client) | `CharBaseInfo.dbc` in any `client-patch/*/patch-z.mpq` |
| Dressing-room preview gear (client) | `standard/` or `enhanced/` patch (see below) |
| Off-race shaman totems | `player_totem_model` |
| Class-critical abilities | Tiered quest patches + narrow spell grants (see below) |
| Starter-zone class trainers | `creature` spawns for new combos (see `mod_uac_starter_trainers.sql`) |

**Not in scope:** custom NPC/dialogue beyond the generated trainers and quest patches.
Off-race characters may still need to **travel** for some class quests; starter trainers are placed
for new combos in each race's starting zone (see [docs/trainer_worksheet.md](docs/trainer_worksheet.md)).

## Operator install

### 1. Add the module

Clone or symlink into your AzerothCore tree:

```text
azerothcore-wotlk/modules/mod-uac/
```

Rebuild/restart as usual. Ensure `mod-uac` is included in your modules build (default `MODULES=static` picks up all `modules/mod-*` directories).

On first **worldserver** start, AzerothCore's DB updater applies every `.sql` file under:

```text
modules/mod-uac/data/sql/db-world/
```

The updater scans `modules/<name>/data/sql/` and includes only subdirectories whose name contains **`world`** (see `UpdateFetcher.cpp`). Install SQL lives in `db-world/`; revert SQL lives in `db-uninstall/` (dirname intentionally **without** `world`, so it is never auto-applied).

Include the module in updates if you use an allow-list:

```ini
# worldserver.conf
Updates.AllowedModules = "all"
# or: Updates.AllowedModules = "mod-uac,..."
```

### 2. Client patch

Choose **one** checked-in MPQ and copy it to your WoW 3.3.5 client `Data/` folder as
`patch-z.mpq` (or rename to any free `patch-<letter>.mpq` slot):

| Directory | What it changes | Best for |
|-----------|-----------------|----------|
| **`client-patch/unlock-only/`** | `CharBaseInfo.dbc` only — unlocks all tiles | Minimal install; creation previews use whatever your client already has |
| **`client-patch/standard/`** | `CharBaseInfo` + `CharStartOutfit` (wowgaming v19 + mod-uac overlay rows) | Reference / stock 3.3.5 clients — new combos show **starter-gear** creation previews |
| **`client-patch/enhanced/`** | `CharBaseInfo` + `CharStartOutfit` (HD patch-k baseline + overlay rows with HD showcase displays) | Official HD 3.3.5a client — preserves retail-style creation previews for stock combos |

Example:

```text
client-patch/enhanced/patch-z.mpq  →  <WoW>/Data/patch-z.mpq
```

All three files are named `patch-z.mpq`; only the source directory differs.

The client loads `CharBaseInfo.dbc` so all race/class tiles appear on the creation screen.
The server does not read this file — `playercreateinfo` rows gate creation server-side.

**Outfit patches (`standard/` and `enhanced/`):** append 74 `CharStartOutfit` overlay rows (37 new
combos × 2 sexes) for dressing-room preview on **new** mod-uac combinations. Server starting gear
still comes from `charstartoutfit_dbc` SQL (wowgaming item clones). Client `DisplayItemID` columns
are preview-only.

- **Standard** rebuilds `CharStartOutfit` from wowgaming v19 — matches starter-gear creation screens
  on reference clients.
- **Enhanced** keeps the deduplicated HD baseline (`data/client/hd_outfit_templates.json` +
  `hd_outfit_stock_index.json`, extracted from official HD `patch-k`) for all 126 stock rows and
  applies HD preview displays to the overlay rows only. Maintainers can refresh from a new
  `patch-k.mpq` via `tools/extract_hd_outfit_baseline.py`.

**Unlock-only** does not ship `CharStartOutfit` at all, so it never replaces your client's existing
outfit file (including HD `patch-k`).

Operators with a custom DBC baseline can still run `tools/generate_local.py` to produce a
`standard`-style outfit patch from their own extracted `Data/dbc/`.

**Patch file name:** use `patch-z.mpq` so the patch loads **late** in the MPQ chain (after HD
`patch-k` and most stock patches). On the official HD client, **`z` was an open single-letter slot**
at the time of testing.

If `patch-z.mpq` is already taken in your `Data/` folder, **rename the mod-uac file** to any
**free** `patch-<letter>.mpq` slot (e.g. `patch-y.mpq`). The client only loads names matching
`patch-<single letter>.mpq` — custom names like `patch-uac.mpq` are **not** loaded on stock 3.3.5a.

**Windows note:** the filesystem is case-insensitive. Do **not** use `patch-A.mpq` for this mod if
you already have an HD or third-party `patch-a.mpq` — they collide and one will overwrite the other.

Remove the mod-uac patch file from `Data/` to revert the client to stock combo visibility.

### 3. worldserver.conf

Required for warlock tier-C imp grants and the optional hunter level-1 pet slice:

```ini
PlayerStart.CustomSpells = 1
```

Stock AzerothCore defaults this to `0`.

## Install SQL reference

| File | Purpose |
|------|---------|
| `mod_uac_skillraceclassinfo_dbc.sql` | Skill/proficiency overlay for new combos |
| `mod_uac_playercreateinfo.sql` | Spawn locations (38 new rows) |
| `mod_uac_playercreateinfo_action.sql` | Starting action bar |
| `mod_uac_charstartoutfit_dbc.sql` | Starting equipment (CharStartOutfit overlay) |
| `mod_uac_player_totem_model.sql` | Totem models for off-race shamans |
| `mod_uac_quest_template.sql` | Warlock tier A + §8.3 faction-wide class-quest unlocks |
| `mod_uac_quest_template_addon.sql` | Anti-gray companion (no-op on stock AC; kept for parity) |
| `mod_uac_playercreateinfo_spell_custom.sql` | Warlock Summon Imp (NE/Draenei tier C) |
| `mod_uac_starter_trainers.sql` | Class trainers in starter zones for new combos (26 spawns, GUIDs 6000000–6000025) |

Placement worksheet and override file: [docs/trainer_worksheet.md](docs/trainer_worksheet.md),
[data/trainer_overrides.yaml](data/trainer_overrides.yaml).

### Optional — hunter pets at level 1

Apply **both** files if you want all hunters to tame at creation (later-expansion QoL):

| Install | Uninstall |
|---------|-----------|
| `mod_uac_hunter_pet_spell_custom.sql` | `mod_uac_hunter_pet_spell_custom_uninstall.sql` |
| `mod_uac_hunter_pet_spell_dbc.sql` | `mod_uac_hunter_pet_spell_dbc_uninstall.sql` |

Spells: Tame Beast (1515), Call Pet (883), Dismiss Pet (2641), Feed Pet (6991), Revive Pet (982).

Requires `PlayerStart.CustomSpells = 1`. The spell grant alone is insufficient — `spell_dbc` overlays set `BaseLevel`/`SpellLevel` to 1.

## Uninstall

AzerothCore has no down-migrations. Revert manually by running the paired files in
`data/sql/db-uninstall/` against the **world** database (same order as install, or any order — files are independent).

To revert **only** level-1 hunter pets while keeping other mod-uac data, run the two `mod_uac_hunter_pet_*_uninstall.sql` files.

Remove the mod-uac `patch-*.mpq` file from the client `Data/` folder.

## Class quests (summary)

Critical abilities use targeted patches, not mod-arac's global quest mask:

| Tier | Rule | Action |
|------|------|--------|
| **A** | Reference quest in the **same starter zone** | Patch `AllowableRaces` on specific quest IDs |
| **B** | Same **continent**, different zone | Same targeted quest patch |
| **C** | **Cross-continent** hard gate | Spell grant at creation (warlock imp only) |

§8.3 opens warrior, shaman, druid, and paladin reference chains to the full faction (`1101` Alliance / `690` Horde). Off-race players travel to the chain when ready.

See the engineering doc §8 for quest IDs and policy detail.

## Regenerating artifacts (developers)

```bash
cd tools
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Run generators from the **mod-uac repo root** (paths below are relative to that root).

### `generate_canonical.py`

Writes checked-in SQL under `data/sql/`, all three client MPQs under `client-patch/`, and
`docs/trainer_worksheet.md`. Uses pinned [wowgaming/client-data](https://github.com/wowgaming/client-data)
tag **v19** (cached under `data/cache/`), the baked world snapshot under `data/snapshot/`, and
minimal outfit item metadata in `data/item_prototypes.json`.

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

Refresh snapshot from your live world DB, then regenerate everything:

```bash
python tools/generate_canonical.py --refresh-snapshot \
  --dsn "127.0.0.1;3306;acore;password;acore_world"
```

Or copy [tools/snapshot.conf.dist](tools/snapshot.conf.dist) to `tools/snapshot.conf`, set
`WorldDatabaseInfo`, and run with `--refresh-snapshot` (no `--dsn` needed). You can also set
`MOD_UAC_WORLD_DATABASE_INFO` or `MOD_UAC_SNAPSHOT_CONFIG` instead of editing the file.

### `generate_local.py`

Operator-specific output when your DBC baseline or overlay max IDs differ from stock. Writes to
`tools/output/` by default (not the checked-in `data/sql/` tree).

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

### `capture_snapshot.py`

Standalone snapshot capture (schema + trainer extracts + outfit item prototypes). The generator
front-ends call the same logic when you pass `--refresh-snapshot`; use this tool when you only want
to refresh the baked JSON artifacts.

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

PyMySQL is required only for snapshot capture (`pip install -r tools/requirements.txt`). Emitters
read the JSON snapshot and do not connect to MySQL.

### Trainer overrides

Edit [data/trainer_overrides.yaml](data/trainer_overrides.yaml) to tweak entry, anchor class, or
spawn coordinates for specific zone/class rows (labels match [docs/trainer_worksheet.md](docs/trainer_worksheet.md)).
Regenerate SQL after changes. Full emitter design: [docs/mod-uac-trainer-emitter-spec.md](docs/mod-uac-trainer-emitter-spec.md).

## Manual QA checklist

- [ ] Apply install SQL on a stock AC world DB; worldserver starts cleanly
- [ ] Remove client patch; off-race combos absent on creation screen
- [ ] Install one `client-patch/*/patch-z.mpq` (see table above); all race/class tiles selectable
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
