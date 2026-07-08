# mod-uac — Operator Guide

Reference for operators running mod-uac on customized AzerothCore installations. For the basic
install, see the [README](../README.md). For architecture and design rationale, see the
[Engineering Implementation](mod-uac-engineering-implementation.md).

## Design goals

- **Human-readable server data.** Proficiencies, spawns, kits, totems, and quest gates ship as
  SQL under `data/sql/db-world/`, each file with a matching revert in `data/sql/db-uninstall/`.
- **No server-side binary DBC edits.** Skill overlays use AzerothCore's
  `skillraceclassinfo_dbc` world-table merge (the same mechanism as other `*_dbc` overlays) —
  not patched `.dbc` files on disk.
- **Reproducible generation.** Checked-in SQL and MPQs come from `tools/generate_canonical.py`
  against pinned [wowgaming/client-data](https://github.com/wowgaming/client-data) tag **v19**.
  Operators with custom DBC baselines can regenerate via `tools/generate_local.py`
  (see [Custom DBC baselines](#custom-dbc-baselines)).

**Not in scope:** custom NPC/dialogue beyond the generated trainers and quest patches.

## How each concern is handled

| Concern | Mechanism |
|---------|-----------|
| Creation allowed (server) | `playercreateinfo` + action/item/spell rows |
| Armor & weapon skills (server) | `skillraceclassinfo_dbc` overlay |
| Equip restriction tooltips (client) | Merged `SkillRaceClassInfo.dbc` in any `client-patch/*/patch-z.mpq` |
| Creation screen tiles (client) | `CharBaseInfo.dbc` in any `client-patch/*/patch-z.mpq` |
| Dressing-room preview gear (client) | `standard/` or `enhanced/` patch (see below) |
| Off-race shaman totems | `player_totem_model` |
| Class-critical abilities | Tiered quest patches + narrow spell grants (see [Class quests](#class-quests)) |
| Starter-zone class trainers | `creature` spawns for new combos (`mod_uac_starter_trainers.sql`) |

Death Knight is already all-race in stock `playercreateinfo` and is unchanged by the SQL
emitters.

## How the SQL is applied

On first **worldserver** start, AzerothCore's DB updater applies every `.sql` file under:

```text
modules/mod-uac/data/sql/db-world/
```

The updater scans `modules/<name>/data/sql/` and includes only subdirectories whose name
contains **`world`** (see `UpdateFetcher.cpp`). Install SQL lives in `db-world/`; revert SQL
lives in `db-uninstall/` — the directory name intentionally omits `world` so it is never
auto-applied.

### Install SQL reference

| File | Purpose |
|------|---------|
| `mod_uac_skillraceclassinfo_dbc.sql` | Skill/proficiency overlay for new combos |
| `mod_uac_playercreateinfo.sql` | Spawn locations (38 new rows) |
| `mod_uac_playercreateinfo_action.sql` | Starting action bar |
| `mod_uac_charstartoutfit_dbc.sql` | Starting equipment (CharStartOutfit overlay) |
| `mod_uac_player_totem_model.sql` | Totem models for off-race shamans |
| `mod_uac_quest_template.sql` | Warlock tier A + faction-wide class-quest unlocks (§8.3) |
| `mod_uac_quest_template_addon.sql` | Anti-gray companion (no-op on stock AC; kept for parity) |
| `mod_uac_playercreateinfo_spell_custom.sql` | Warlock Summon Imp (NE/Draenei tier C) |
| `mod_uac_starter_trainers.sql` | Class trainers in starter zones for new combos (26 spawns, GUIDs 6000000–6000025) |

Trainer placement worksheet and override file: [trainer_worksheet.md](trainer_worksheet.md),
[data/trainer_overrides.yaml](../data/trainer_overrides.yaml).

## Choosing a client patch

Three checked-in MPQs, all named `patch-z.mpq`; only the source directory differs:

| Directory | What it changes | Best for |
|-----------|-----------------|----------|
| `client-patch/unlock-only/` | `CharBaseInfo` + `SkillRaceClassInfo` (v19 + overlay rows) | Minimal install; creation outfit previews use whatever your client already has |
| `client-patch/standard/` | Above + `CharStartOutfit` (wowgaming v19 + mod-uac overlay rows) | Reference / stock 3.3.5a clients — new combos show starter-gear creation previews |
| `client-patch/enhanced/` | Above + `CharStartOutfit` (HD patch-k baseline + overlay rows with HD showcase displays) | Official HD 3.3.5a client — preserves retail-style creation previews for stock combos |

The server never reads these files — `playercreateinfo` rows gate creation server-side.

### What the patch contains

The client loads `CharBaseInfo.dbc` so all race/class tiles appear on the creation screen.
`SkillRaceClassInfo.dbc` mirrors the server `skillraceclassinfo_dbc` overlay so equip tooltips
show correct armor/weapon restrictions for new combos. Stock rows are preserved; 37 equip
overlay rows are appended, plus client-only UI normalization: per-race faction language rows
and per-race copies of every `playercreateinfo_skills` grant (stock plus mod-uac gear-skill
rows) so the skills list, weapon proficiencies, and chat language selection work with the
expanded `CharBaseInfo` matrix.

**Outfit patches (`standard/` and `enhanced/`)** append 74 `CharStartOutfit` overlay rows
(37 new combos × 2 sexes) for dressing-room preview on **new** mod-uac combinations. Server
starting gear still comes from `charstartoutfit_dbc` SQL (wowgaming item clones); client
`DisplayItemID` columns are preview-only.

- **Standard** rebuilds `CharStartOutfit` from wowgaming v19 — matches starter-gear creation
  screens on reference clients.
- **Enhanced** keeps the deduplicated HD baseline (`data/client/hd_outfit_templates.json` +
  `hd_outfit_stock_index.json`, extracted from official HD `patch-k`) for all 126 stock rows
  and applies HD preview displays to the overlay rows only. Maintainers can refresh from a new
  `patch-k.mpq` via `tools/extract_hd_outfit_baseline.py`.
- **Unlock-only** does not ship `CharStartOutfit` at all, so it never replaces your client's
  existing outfit file (including HD `patch-k`). It still ships the merged
  `SkillRaceClassInfo.dbc` needed for correct in-game equip tooltips on new combos.

### Patch file naming

Use `patch-z.mpq` so the patch loads **late** in the MPQ chain (after HD `patch-k` and most
stock patches). On the official HD client, `z` was an open single-letter slot at the time of
testing. If it's taken in your `Data/` folder, rename to any free `patch-<letter>.mpq` slot —
the client only loads names matching `patch-<single letter>.mpq`; custom names like
`patch-uac.mpq` are not loaded on stock 3.3.5a. On Windows the filesystem is case-insensitive,
so `patch-A.mpq` collides with an existing `patch-a.mpq`.

Removing the mod-uac patch file from `Data/` reverts the client to stock combo visibility.

## Class quests

Critical abilities use targeted patches, not mod-arac's global quest mask:

| Tier | Rule | Action |
|------|------|--------|
| **A** | Reference quest in the **same starter zone** | Patch `AllowableRaces` on specific quest IDs |
| **B** | Same **continent**, different zone | Same targeted quest patch |
| **C** | **Cross-continent** hard gate | Spell grant at creation (warlock imp only) |

§8.3 opens the warrior, shaman, druid, and paladin reference chains to the full faction
(`1101` Alliance / `690` Horde). Off-race players travel to the chain when ready.

See the [engineering doc §8](mod-uac-engineering-implementation.md) for quest IDs and policy
detail.

### `PlayerStart.CustomSpells`

```ini
PlayerStart.CustomSpells = 1
```

Required for the warlock tier-C imp grants and the optional level-1 hunter pet feature. Stock
AzerothCore defaults this to `0`.

## Optional — hunter pets at level 1

By default **both** files will be applied, allowing hunters to tame at creation (later-expansion QoL).  You can apply the uninstall SQL to revert that functionality:

| Install | Uninstall |
|---------|-----------|
| `mod_uac_hunter_pet_spell_custom.sql` | `mod_uac_hunter_pet_spell_custom_uninstall.sql` |
| `mod_uac_hunter_pet_spell_dbc.sql` | `mod_uac_hunter_pet_spell_dbc_uninstall.sql` |

Spells: Tame Beast (1515), Call Pet (883), Dismiss Pet (2641), Feed Pet (6991), Revive Pet
(982).

Requires `PlayerStart.CustomSpells = 1`. The spell grant alone is insufficient — the
`spell_dbc` overlays set `BaseLevel`/`SpellLevel` to 1.

## Custom DBC baselines

Operators with a custom DBC baseline (or existing `*_dbc` overlay rows with conflicting IDs)
can run `tools/generate_local.py` to produce operator-specific SQL and a `standard`-style
client MPQ (`CharBaseInfo` + merged `SkillRaceClassInfo` + `CharStartOutfit`) from their own
extracted `Data/dbc/` directory. See the [Development Guide](development.md#generate_localpy)
for flags and examples.

## Trainer overrides

Edit [data/trainer_overrides.yaml](../data/trainer_overrides.yaml) to tweak entry, anchor
class, or spawn coordinates for specific zone/class rows (labels match
[trainer_worksheet.md](trainer_worksheet.md)). Regenerate SQL after changes. Full emitter
design: [mod-uac-trainer-emitter-spec.md](mod-uac-trainer-emitter-spec.md).

## Uninstall details

AzerothCore has no down-migrations. Revert manually by running the paired files in
`data/sql/db-uninstall/` against the **world** database (same order as install, or any order —
the files are independent).

To revert **only** level-1 hunter pets while keeping other mod-uac data, run the two
`mod_uac_hunter_pet_*_uninstall.sql` files.

Remove the mod-uac `patch-*.mpq` file from the client `Data/` folder.
