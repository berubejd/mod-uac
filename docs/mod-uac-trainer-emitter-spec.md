# mod-uac Engineering Spec — Snapshot Subsystem & Trainer Emitter

**Status:** Implemented (Phase **2b** starter trainers; Phase **2e** schema contract on all
world-table emitters). This document is the design record and operator reference.
**Author context:** builds on the mod-uac generator (`tools/aracgen`). Python.

Related: [mod-uac-engineering-implementation.md](mod-uac-engineering-implementation.md),
[trainer_worksheet.md](trainer_worksheet.md), [README.md](../README.md).

---

## 1. Motivation

Three separate divergences between AzerothCore *master* and a live world DB broke the
trainer work, each caught only after the fact:

1. Event-gated spawns (Arena Tournament, event 31) counted as "present" — coverage wrong.
2. Those trainers teach the full spell list, not the curated starter list — design wrong.
3. `creature` schema is `id1/id2/id3` on master but `id` on the target DB — the SQL wouldn't apply.

Root cause is identical in all three: **generating against a master snapshot instead of the
operator's actual database.** The fix is two subsystems that make "the operator's world" the
source of truth, without requiring a live DB connection at generation time:

- **A snapshot subsystem** — capture the world schema (and the small data extracts emitters
  need), versioned against the DB version, baked into the repo, refreshable with a shipped tool.
- **Data-driven emitters** built on the snapshot, producing shipped, plug-and-play SQL that
  operators can also regenerate when their world drifts from the baked snapshot.

Design tenet (unchanged from the outfit/skill work): generate from a **known, versioned source**;
ship the baked output *and* the tooling to reproduce it.

---

## 2. Part A — Snapshot subsystem

### 2.1 Domain model
- **`ColumnDef`** — `name`, `ordinal`, `type`, `nullable`, `default`.
- **`TableSchema`** — table name → ordered `list[ColumnDef]`.
- **`Snapshot`** — `{ version, version_raw, captured_at, source, schemas: {table: TableSchema}, data: {name: extract} }`.
- **Load path** — emitters call `load_snapshot()` (baked pointer `data/snapshot/world.latest.json`)
  or receive a `Snapshot` resolved by the generator front-ends. Emitters never connect to MySQL.

### 2.2 The snapshot tool (`tools/aracgen/snapshot.py`, `tools/capture_snapshot.py`)
- Connects to a world DB via DSN (`--dsn` or `tools/snapshot.conf`).
- **Schema capture:** for `SCHEMA_TABLES`, read `INFORMATION_SCHEMA.COLUMNS` ordered by
  `ORDINAL_POSITION` → `TableSchema`.
- **Data capture:** trainer extract (§3.1) into `data["trainers"]`.
- **Version tag:** read the `version` table. `db_version` is the authoritative match/dedup key.
  `core_version` + `core_revision` are metadata only. Ignore `cache_id`. Caveats:
  - Sanitize `db_version` for the filename; keep the raw string in `version_raw`.
  - If `db_version` is NULL, fall back to `unknown-<timestamp>` (with a warning).
- Write `data/snapshot/world.<sanitized_db_version>.json` and update `world.latest.json`.

Snapshot header:
```json
{
  "version": "<sanitized db_version>",
  "version_raw": "<db_version string>",
  "core_version": "...",
  "core_revision": "...",
  "captured_at": "<iso8601>",
  "source": "<dsn host/db, no creds>",
  "schemas": { "...": { "table": "...", "columns": [ ... ] } },
  "data": { "trainers": { ... } }
}
```

**Schema tables captured** (`snapshot_model.SCHEMA_TABLES` — everything world-table emitters write):

| Table | Emitter |
|-------|---------|
| `creature` | starter trainers |
| `playercreateinfo`, `playercreateinfo_action`, `playercreateinfo_skills` | player create |
| `playercreateinfo_spell_custom` | player create, class quest, hunter pet |
| `charstartoutfit_dbc` | player create |
| `skillraceclassinfo_dbc` | skill overlay |
| `player_totem_model` | totem |
| `quest_template`, `quest_template_addon` | class quest |
| `spell_dbc` | hunter pet spell overlay |

### 2.3 Baked snapshot + refresh
- Ship `data/snapshot/world.<baked_version>.json` — good for most operators for a while.
- An operator on a different world DB version runs `--refresh-snapshot` once to refresh schemas
  and trainer extracts from their live world DB.
- Pin older `world.<version>.json` files if you need to regenerate SQL against an older server
  layout while keeping a newer baked snapshot for current work.
- **Emitters always read a `Snapshot` for schema; they never hardcode column lists.**

### 2.4 Emitter contract (`tools/aracgen/schema_emit.py`)
Every schema-contract emitter derives column lists and value ordering from the snapshot:

```python
schema = snap.schema("creature")
row = prepare_row(schema, logical_values)   # defaults + signed-int normalization
render_insert("creature", schema, logical_values)
# or render_replace / render_update / render_insert_bulk
```

**Column aliasing** for the one known structural variant: emitters work in *logical* fields;
`COLUMN_ALIASES` resolves them against the actual schema.
```python
# logical "entry" -> "id" if present else "id1" (id2/id3 default 0)
{"creature": {"entry": ["id", "id1"]}}
```

### 2.5 Outfit item prototypes (`data/item_prototypes.json`)
Separate from the snapshot JSON (keeps snapshot focused on schema + trainer data), but refreshed
on the same `--refresh-snapshot` pass when CharStartOutfit.dbc is available:

- **Item IDs** — derived from client `CharStartOutfit.dbc` for mod-uac outfit overlays
  (`outfit_items.collect_mod_uac_outfit_item_ids`).
- **Class/subclass** — queried from the operator's world DB:
  `SELECT entry, class, subclass FROM item_template WHERE entry IN (...)`.
- **Shipped file** — minimal map `{ "1395": [2, 10], ... }` (62 items in the baked canonical
  set). Used only for `playercreateinfo_skills` gear-skill derivation; no sibling AC checkout
  required at generation time.

---

## 3. Part B — Trainer emitter (`tools/aracgen/emit_trainers.py`)

### 3.1 Data extract (lives in `snapshot.data["trainers"]`)
Captured by the snapshot tool, filtered to starter-zone boxes around stock `playercreateinfo`
spawns. Event-gated creature GUIDs are excluded at capture time (`game_event_creature`).

| Key | Content |
|-----|---------|
| `playercreateinfo` | stock spawn rows (zone boxes) |
| `starter_zones` | derived box metadata |
| `creature_spawns` | non-event trainer spawns in starter zones |
| `spawn_defaults` | per-entry equipment/health/mana/npcflag from anchor spawns |
| `creature_default_trainer` | `{creatureId: trainerId}` |
| `trainer_spell_counts` | spell **count** per `trainerId` (curated vs full lists) |
| `trainers` | `{trainerId: {type, requirement}}` |
| `creature_template` | `{entry: {name, subname, faction}}` for trainer entries |

### 3.2 Pipeline
1. **Coverage** — per starter zone, the set of class trainers present. New-combo classes not
   present = **gaps**.
2. **Entry selection** — for each `(zone_faction, gap_class)`: a **curated** starter trainer
   entry (`trainer_spell_counts` ≤ threshold) from a **same-faction** starter zone.
3. **Anchor selection** — kinship model (§3.3).
4. **Placement** — orientation-aware (§3.4); optional YAML overrides (§3.6).
5. **Emit** — schema-driven `creature` rows + idempotent GUID-band `DELETE` + uninstall.

### 3.3 Anchor selection — class kinship (shipped)
Anchor each new trainer to the **highest-priority kin class that has a native trainer present** in
the zone. Kin that are themselves gaps are skipped; fallback is nearest native by distance.

Shipped in `trainer_catalog.CLASS_KINSHIP`:
```
Warrior : [Paladin, Rogue, Hunter]
Paladin : [Warrior, Priest, Rogue]
Hunter  : [Rogue, Warrior, Paladin]
Rogue   : [Hunter, Warrior, Paladin]
Priest  : [Shaman, Druid, Mage, Paladin]
Shaman  : [Druid, Priest, Paladin]
Druid   : [Shaman, Priest, Hunter]
Mage    : [Warlock, Priest]
Warlock : [Mage, Priest]
```

**Worked example — Northshire** (natives: War, Pal, Rog, Pri, Mag, Wlk; gaps: Hun, Sha, Dru):
- Hunter → Rogue present → anchor **Rogue**
- Shaman → Druid is a gap, Priest present → anchor **Priest**
- Druid → Shaman is a gap, Priest present → anchor **Priest**

### 3.4 Placement — orientation-aware (shipped)
Offset **perpendicular to the anchor's facing**, inherit orientation, extend the lineup beside the
anchor. Constants in `trainer_catalog`:

- `PLACEMENT_GAP = 2.0` yards — first trainer on a side
- `PLACEMENT_STEP = 2.0` yards — additional trainers sharing an anchor on the same side
- **Side choice:** pick the side farther from all other native trainers; tie → right

Anchor at `(x, y, z)` facing `o` (radians):
```
right = ( sin o, -cos o)
d     = GAP + k * STEP
new_x = x + right.x * d   # or left, per side choice
new_y = y + right.y * d
new_z = z
new_o = o
```

### 3.5 Emission details (shipped)
- **GUID band:** `6000000–6000025` (26 trainers); base configurable via `--trainer-guid-base`
  (must stay within `6000000–6009999` reserved band).
- **Curated threshold:** `CURATED_SPELL_THRESHOLD = 30` spells per trainer list.
- **Idempotent install:** `DELETE FROM creature WHERE guid BETWEEN base AND base+n-1;` then
  `INSERT`.
- **Uninstall:** same GUID-band `DELETE`.
- **Schema-driven columns** via §2.4 (`id` vs `id1/id2/id3` handled by snapshot + aliases).

### 3.6 Placement overrides (`data/trainer_overrides.yaml`)
Optional per-row nudges matched by starter zone label + class (see worksheet). Regenerate after
editing; shipped SQL reflects overrides.

**In-game QA (maintainer, stock AC world):** all 26 trainer positions were walked. Three rows
needed coordinate overrides (computed placement was close but not ideal):

| Zone | Class | Reason |
|------|-------|--------|
| CampNarache | Warlock | lineup/clipping vs native cluster |
| Deathknell | Paladin | facing/stand position vs Warrior anchor |
| Deathknell | Hunter | facing/stand position vs Rogue anchor |

**Hunter** was fully exercised in-game (all available starter skills trained successfully).
Other classes use the same curated starter-list entries and placement algorithm; they are
expected to behave equivalently but were not individually re-tested beyond placement walk-through.

---

## 4. Integration into `tools/aracgen`

| Module | Role |
|--------|------|
| `snapshot.py` | capture + load; only code that touches MySQL |
| `snapshot_model.py` | `Snapshot`, `TableSchema`, `SCHEMA_TABLES` |
| `schema_emit.py` | shared INSERT/REPLACE/UPDATE rendering |
| `emit_trainers.py` | trainer emitter |
| `trainer_catalog.py` | kinship, thresholds, placement constants, zone labels |
| `outfit_items.py` | outfit item ID collection for prototype refresh |
| `item_prototypes.py` | minimal class/subclass lookup for starter skills |
| `cli.py` | `resolve_generation_snapshot()`, `write_trainer_sql()`, shared wiring |

**Front-ends:** `generate_canonical.py`, `generate_local.py`

- Default: baked `data/snapshot/world.latest.json` + `data/item_prototypes.json`.
- `--refresh-snapshot --dsn ...` — capture fresh schema, trainer extract, and item prototypes
  from the operator's world DB (requires PyMySQL + cached client-data for outfit item IDs).

**Schema-contract emitters (all world-table SQL):** `emit_skill`, `emit_player` /
`charstartoutfit_export`, `emit_totem`, `emit_class_quest`, `emit_hunter_pet` / `spell_dbc_export`,
`emit_trainers`.

**Not on schema contract:** `emit_client` (MPQ patches: `CharBaseInfo.dbc`; optional
`CharStartOutfit.dbc` in standard/enhanced variants — see `client-patch/*/patch-z.mpq`).

---

## 5. Shipped decisions

| Decision | Resolution |
|----------|------------|
| Kinship table (§3.3) | Shipped as `CLASS_KINSHIP` in `trainer_catalog.py` |
| Curated-list threshold | `≤ 30` spells (`CURATED_SPELL_THRESHOLD`); validated on stock AC sampling |
| Placement constants | `GAP = STEP = 2.0` yards; side-choice heuristic shipped |
| Snapshot format | JSON; `version` = sanitized `db_version` |
| Snapshot scope | Schema for all emitter tables + trainer data extract in `data.trainers` |
| GUID policy | Fixed reserved band `6000000–6009999`; 26 trainers use `6000000–6000025` |
| Hand-generated SQL | Superseded by emitter output in `data/sql/db-world/mod_uac_starter_trainers.sql` |

### Remaining / future
- Broader in-game class-by-class training QA (beyond Hunter full test + placement walk).
- Revisit kinship/threshold/constants if custom world DBs produce bad entry picks.
- Additional YAML overrides if operators report overlap on non-stock layouts.

---

## 6. Implementation checklist

- [x] Snapshot tool: schema capture → versioned JSON; baked pointer
- [x] `Snapshot`/`TableSchema` loader + `schema_emit` contract
- [x] Trainer data extract in snapshot capture (starter zones, event-gated exclusion)
- [x] Trainer emitter: coverage → curated same-faction entry selection
- [x] Kinship anchor + orientation-aware placement
- [x] Emit install/uninstall via schema; worksheet + YAML overrides
- [x] Retrofit all world-table emitters onto schema contract; wire front-ends
- [x] Minimal `item_prototypes.json` sidecar (no sibling-repo dependency)
- [x] In-game placement QA + three shipped overrides

---

## 7. Shipped artifacts

| Path | Purpose |
|------|---------|
| `data/sql/db-world/mod_uac_starter_trainers.sql` | 26 starter trainers (install) |
| `data/sql/db-uninstall/mod_uac_starter_trainers_uninstall.sql` | GUID-band revert |
| `data/snapshot/world.latest.json` | pointer → baked snapshot |
| `data/trainer_overrides.yaml` | three placement nudges (CampNarache Warlock, Deathknell Paladin/Hunter) |
| `docs/trainer_worksheet.md` | human placement worksheet (regenerated with SQL) |

Regenerate everything:
```bash
python tools/generate_canonical.py
# or with a live world DB refresh:
python tools/generate_canonical.py --refresh-snapshot --dsn "host;port;user;pass;db"
```
