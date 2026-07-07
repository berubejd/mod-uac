# mod-uac — Engineering Implementation Document

**Module:** `mod-uac` (Unlock All Classes) — provisional name
**Target:** AzerothCore, WotLK 3.3.5a
**Status:** Phase 1 complete (generator + data module). Starter trainer emitter (Phase 2b) complete.
Remaining Phase 2 work: gameplay QA and polish.
**Supersedes:** the design intent of `heyitsbench/mod-arac`, rebuilt for maintainability.

---

## 1. Purpose

Allow any playable race to create and play any playable class, with a design that is
**maintainable, revertable, and free of mystery binaries**, and that is **reusable by other
server operators** running stock or lightly-customized AzerothCore installations.

### Goals
- No unexplained binary DBC files. Every artifact is either generated from a known source or is
  human-readable SQL.
- No hand-applied, irreversible SQL. Everything is applied by AzerothCore's DB updater and has a
  companion revert.
- **Zero server-side binary DBC edits.** (See §3 — this is achievable and is the central finding.)
- Exactly one small, universal client artifact (a generated MPQ), producible in pure Python.
- Deterministic and reproducible: generation happens against a pinned canonical source, or against
  the operator's own installed DBCs.

### Non-goals
- Custom NPC dialogue beyond generated trainers and quest patches (unrelated to this module).

**Verified in scope (formerly deferred):**
- **`mod-playerbots` + new combos** — with mod-uac `playercreateinfo` rows applied, playerbots on
  typical Playerbot-branch AzerothCore already create and spawn the new race/class pairs; no separate
  mod-uac factory change required.
- **Starter-zone class trainers** — shipped via snapshot-driven `mod_uac_starter_trainers.sql`
  (26 spawns; see [mod-uac-trainer-emitter-spec.md](mod-uac-trainer-emitter-spec.md) and
  [trainer_worksheet.md](trainer_worksheet.md)).

---

## 2. Why the existing `mod-arac` is inadequate

Three operator-facing problems, all of which this design eliminates:

1. **Forces overwriting server DBC files** with binaries of unknown provenance
   (`CharBaseInfo.dbc`, `SkillRaceClassInfo.dbc`, `CharStartOutfit.dbc` under
   `patch-contents/DBFilesContent/`). Clobbers any other DBC customization and is non-diffable.
2. **A ~7,870-line `arac.sql`** applied by hand against the world DB, mixing `INSERT IGNORE` into
   `playercreateinfo*` with `UPDATE`s to shared tables (`quest_template`) and
   `DELETE`+`INSERT` on `player_totem_model`, with **no revert path**.
3. **A binary client patch** (`Patch-A.MPQ`, ~26 KB) of unknown contents, distributed manually
   because AzerothCore has no patch-download service.

For reference, what `arac.sql` actually touches (verified by inspection):
`playercreateinfo`, `playercreateinfo_action`, `playercreateinfo_spell_custom`,
`playercreateinfo_skills` (one `UPDATE`), `quest_template` (one `UPDATE`), and
`player_totem_model` (`DELETE`+`INSERT`).

---

## 3. Source-grounded findings

All findings below were verified against `azerothcore-wotlk` `master`. File:line references are to that
tree at the time of writing and should be re-confirmed if the core is bumped.

### 3.1 The server never reads `CharBaseInfo.dbc`
`CharBaseInfo` does not appear anywhere in `DBCStores.cpp` — there is no `sCharBaseInfoStore`. The
server does not load or consult it. It is a **purely client-side** file that governs which race/class
tiles are selectable on the character-creation screen. In `mod-arac`'s copy it is 100 records ×
2 bytes (two `uint8` fields: `raceId`, `classId`) — i.e. the full 10×10 matrix.

**Consequence:** the client needs a `CharBaseInfo.dbc` patch; the server does not.

### 3.2 The server-side "is this combo allowed?" gate is a `playercreateinfo` row
`Player::Create` (`Player.cpp:496`) does:
```cpp
PlayerInfo const* info = sObjectMgr->GetPlayerInfo(createInfo->Race, createInfo->Class);
if (!info) { /* log "invalid race/class pair", */ return false; }
```
`GetPlayerInfo` returns non-null **iff a `playercreateinfo` row exists** for that (race, class).
The creation opcode handler (`CharacterHandler.cpp:274+`) validates class/race existence in
`ChrClasses`/`ChrRaces`, expansion levels, and the racemask/classmask *disable* configs — but has
**no `CharBaseInfo` check**.

**Consequence:** populating `playercreateinfo` for a combo is what makes it creatable server-side.

### 3.3 `SkillRaceClassInfo` gates proficiency/skill learning (server-side)
Skill and proficiency granting is gated on `GetSkillRaceClassInfo(skill, race, class)`:
- `LearnDefaultSkills()` (`Player.cpp:11926`, gate at `:11942`)
- spell-learn skip: "skip wrong class and race skill saved in SkillRaceClassInfo.dbc"
  (`Player.cpp:12457`)
- additional gates at `Player.cpp:3106`, `:13826`

Without an entry covering a new (race, class), the server silently refuses that combo's armor/weapon
proficiencies and trainable skills.

**Consequence:** new combos need `SkillRaceClassInfo` coverage — **but see §3.4, this need not be a
binary edit.**

### 3.4 `*_dbc` world tables are a live DB-overlay for every DBC store (the central finding)
Every DBC store is loaded from its file **and then merged with a companion world-DB table**:
```cpp
// DBCStores.cpp ~:238 (inside LoadDBC)
if (storage.Load(dbcFilename.c_str())) { /* file + locale strings */ }
if (dbTable)
    storage.LoadFromDB(dbTable, storage.GetFormat());
```
`SkillRaceClassInfo` is explicitly wired to `skillraceclassinfo_dbc`
(`DBCStores.cpp:352`). The merge logic (`DBCDatabaseLoader.cpp`) is:
- `SELECT * FROM <table> ORDER BY \`ID\` DESC` (`:40`)
- grow the in-memory index table to `max(existing, maxDbId + 1)` (`:56`)
- write each DB row into the index **by its `ID`**; the collision branch comment reads
  *"If exist in DBC file override from DB"* (`:78`, `:128`)

So the semantics are **merge-by-ID**: a new `ID` (above the file's max) is appended; a colliding `ID`
overrides the file record. The `SkillRaceClassInfoBySkill` lookup map is rebuilt from the merged store
*after* the DB load (`DBCStores.cpp:423`), and `GetSkillRaceClassInfo` walks that map
(`DBCStores.cpp:895`). DB-added rows are therefore honored identically to file rows.

The `*_dbc` tables ship **empty** because base game data lives in the `.dbc` files; the tables exist
purely so operators/modules can add or override records via SQL.

**Consequence — this is the key architectural unlock:** the `SkillRaceClassInfo` records for new
combos go into the **`skillraceclassinfo_dbc` table as revertable SQL**, not into the binary file.
This removes the last mandatory server-side binary DBC edit.

### 3.5 `RaceMask`/`ClassMask` are bitmasks; `0` matches everything
`GetSkillRaceClassInfo` (`DBCStores.cpp:895`):
```cpp
if (entry->RaceMask  && !(entry->RaceMask  & (1 << (race  - 1)))) continue;
if (entry->ClassMask && !(entry->ClassMask & (1 << (class_ - 1)))) continue;
```
A mask of `0` short-circuits the guard, i.e. the row applies to **all** races/classes.

**Consequence:** many proficiency rows already cover new races. The overlay must compute a **minimal
delta** — emit rows only for (skill, class) whose existing rows do not already cover the new race —
rather than cloning wholesale.

### 3.6 Starting gear must use `CharStartOutfit.dbc`, not `playercreateinfo_item`
`Player::Create` equips starter gear from `GetCharStartOutfitEntry()` (`Player.cpp:630`) — a lookup
into `CharStartOutfit.dbc` / `charstartoutfit_dbc` keyed by `(race, class, sex)`. The separate
`playercreateinfo_item` path (`Player.cpp:666–667`, `StoreNewItemInBestSlots`) is a secondary
mechanism; **rndbots and other headless creation paths rely on the outfit DBC**, not item rows.

**Consequence:** new combos need **cloned `CharStartOutfit` records** in `charstartoutfit_dbc`, not
`playercreateinfo_item` inserts. A record is a fixed 77-field shape: header (`ID`, `Race`, `Class`,
`Sex`, `OutfitID`) plus three parallel 24-wide arrays (`ItemId`, `DisplayItemId`, `InventoryType`).
We do not compose item lists — we copy the reference combo's male and female records whole, re-key
only the header (`Race`, `Class`, new `ID` above the stock max), and leave the arrays unchanged
because they are item-derived and stay valid for the same items. Combos that already have a native
stock outfit row (e.g. Dwarf Mage `(3,8)`) are skipped to avoid `sCharStartOutfitMap` collisions.

### 3.7 Summary table

| Data | Server needs | Client needs | Home in `mod-uac` |
|---|---|---|---|
| `CharBaseInfo.dbc` | No (not loaded) | **Yes** (creation screen) | Generated client MPQ only |
| `SkillRaceClassInfo` | **Yes** (proficiency gate) | Preview only | `skillraceclassinfo_dbc` overlay **SQL** |
| `CharStartOutfit.dbc` | **Yes** (equip at creation) | Preview | `charstartoutfit_dbc` overlay SQL |
| `playercreateinfo(+_action/_spell_custom/_skills)` | **Yes** | No | Module install SQL (+ uninstall) |
| `player_totem_model` | Yes (off-race shamans) | No | Module install SQL (+ uninstall) |

---

## 4. Architecture

### 4.1 Split of responsibilities
- **Server side: zero binary DBC edits.** Everything is SQL applied by the DB updater:
  `playercreateinfo`, `playercreateinfo_action`, `playercreateinfo_spell_custom`,
  `playercreateinfo_skills`, `charstartoutfit_dbc`, `skillraceclassinfo_dbc`, `player_totem_model`.
- **Client side: one universal generated MPQ** containing `CharBaseInfo.dbc` (the full matrix).
  Optionally also regenerated `SkillRaceClassInfo.dbc` / `CharStartOutfit.dbc` for preview correctness
  (cosmetic, decided during 1e). The MPQ is **identical for every operator** because the combo matrix
  does not depend on anyone's local DBCs — so it ships once from the canonical run.

### 4.2 The generator: one core, two front-ends
The only thing the two entry points differ by is the DBC source:
- **`generate_local.py`** — reads the operator's own `data/dbc/`. Emits operator-specific SQL. This is
  a *correctness* requirement, not just convenience: overlay row IDs must sit above the operator's
  actual `SkillRaceClassInfo.dbc` max ID, and the `RaceMask` delta depends on which rows their
  installed file already has. Operators running other DBC-editing mods have a different baseline than
  canonical.
- **`generate_canonical.py`** — reads the pinned canonical source
  (`wowgaming/client-data`, tag **`v19`**) and the baked world snapshot under `data/snapshot/`.
  Produces the **checked-in** module SQL, starter trainer worksheet, and the shared MPQ.

### 4.3 Domain model
- **`DbcTable`** — a decoded WDBC file: header (record count, field count, record size, string-block
  size), typed records, string block. Codec supports read and **byte-exact** write. Foundation of the
  whole tool; validated first (1a) by exact round-trip of the stock files.
- **`DbcSource`** (interface) — yields baseline DBCs. `LocalDbcSource(dbc_path)` and
  `CanonicalDbcSource(pin="v19")`. The *only* axis the front-ends differ on.
- **`ComboMatrix`** — the target `(raceId, classId)` set, plus per-class metadata.
- **`CanonicalKitResolver`** — composes each new combo from two orthogonal sources:
  - **kit from the class** — starting `_action`, `_spell_custom`, `_skills`, and `charstartoutfit_dbc`
    outfit clones, derived from a chosen reference combo of that class;
  - **location from the race** — spawn map/zone/x/y/z/o taken from any existing combo of that race.

  *Example:* to make a **Tauren Mage**, clone **Human Mage**'s kit (class 8) and place it at the
  **Tauren** starting location (race 6). This composition rule is why the SQL is *derivable* rather
  than authored.
- **Emitters** (each produces install + uninstall SQL, except the client emitter):
  - `SkillOverlayEmitter` → minimal `skillraceclassinfo_dbc` delta (§3.5), new IDs above source max.
  - `PlayerCreateEmitter` → `playercreateinfo`, `playercreateinfo_action`,
    `playercreateinfo_skills`, and `charstartoutfit_dbc` overlays.
  - `TotemEmitter` → `player_totem_model` for off-race shamans.
  - `TrainerEmitter` → starter-zone `creature` spawns for new combos (snapshot-driven; §8 Phase 2b).
  - `ClientPatchEmitter` → builds `CharBaseInfo.dbc` and packs the MPQ (pure-Python writer).

### 4.4 Data flow
```
DbcSource ──► DbcTable(s) ──► ComboMatrix ──► CanonicalKitResolver
                                   │                     │
                                   ▼                     ▼
                        SkillOverlayEmitter      PlayerCreateEmitter
                        TotemEmitter             TrainerEmitter (snapshot)
                                   │                     │
                                   ▼                     ▼
                        install/uninstall SQL     creature spawns + worksheet
                        ClientPatchEmitter
                                   │
                                   ▼
                        CharBaseInfo.dbc → MPQ
```

---

## 5. Data model and schema touchpoints

### 5.1 World DB tables
- **`playercreateinfo`** — `(race, class, map, zone, position_x, position_y, position_z, orientation)`.
  One row per new combo. `map/zone/position*` from the race; the row's existence is the server gate
  (§3.2).
- **`playercreateinfo_action`** — starting action-bar buttons. Cloned from the class reference combo.
- **`playercreateinfo_spell_custom`** — starting spells. Cloned from the class reference combo.
- **`playercreateinfo_skills`** — starting skills. Cloned from the class reference combo.
- **`charstartoutfit_dbc`** — starting equipment (§3.6). Full 77-field records cloned from the class
  reference combo's male/female outfits; overlay IDs above stock max; skipped when stock already
  covers the combo.
- **`player_totem_model`** — totem display for shamans of races without native totems (Alliance →
  Dwarf totems, Horde → Orc totems, mirroring the approach `mod-arac` used).
- **`creature`** — starter-zone class trainer spawns for new combos (Phase 2b). Reserved GUID band
  `6000000–6009999`; idempotent install/uninstall via `mod_uac_starter_trainers.sql`.
- **`skillraceclassinfo_dbc`** — DBC overlay (§3.4). Columns mirror the `SkillRaceClassInfo` DBC
  layout: `ID`, `SkillID`, `RaceMask`, `ClassMask`, `Flags`, `MinLevel`, `SkillTier`,
  `SkillCostIndex` (8 fields; struct field names `SkillID`/`RaceMask`/`ClassMask` confirmed from
  core source). **TO VERIFY:** exact column names/types against the base world schema and the
  `SkillRaceClassInfofmt` format string; the generator should map columns from the format rather than
  hardcode them.

### 5.2 Client DBC
- **`CharBaseInfo.dbc`** — 2 fields (`raceId` `uint8`, `classId` `uint8`), 2-byte records. The
  generator emits the full playable matrix: races `{1,2,3,4,5,6,7,8,10,11}` × classes
  `{1,2,3,4,5,6,7,8,9,11}` = **100 records** (race id 9 = Goblin and class id 10 are not playable and
  are skipped). Including already-valid combos here is harmless.

### 5.3 Overlay ID assignment rule
Compute `base_max = max(ID)` over the source `SkillRaceClassInfo.dbc`. Assign overlay row IDs
`base_max + 1, base_max + 2, …`. This guarantees append semantics (no accidental override, §3.4).
Because canonical and local baselines may differ, this max is read from whichever `DbcSource` is in
use — the reason both front-ends exist (§4.2).

### 5.4 Illustrative SQL shapes (schematic — real columns/values come from the source at gen time)
```sql
-- playercreateinfo (Tauren Mage: race 6, class 8; location from Tauren, kit from Mage reference)
INSERT INTO playercreateinfo (race, class, map, zone, position_x, position_y, position_z, orientation)
VALUES (6, 8, 1, 215, -2917.58, -257.98, 52.9968, 4.05);

-- skillraceclassinfo_dbc overlay (grant a class skill to a race not already covered)
INSERT INTO skillraceclassinfo_dbc (ID, SkillID, RaceMask, ClassMask, Flags, MinLevel, SkillTier, SkillCostIndex)
VALUES (<base_max+1>, <skillId>, <mask incl. new race>, <class bit>, 0, 0, <tier>, <costIndex>);
```

---

## 6. Combo matrix

This matrix is **derived from AzerothCore's base `data/sql/base/db_world/playercreateinfo.sql`**
(62 existing rows across races `{1,2,3,4,5,6,7,8,10,11}` × classes `{1,2,3,4,5,6,7,8,9,11}`). It is
authoritative for stock AzerothCore; an operator with a customized `playercreateinfo` will differ, and
the generator always recomputes the delta from the active source at generation time. `mod-uac` adds the
**38 new combos** marked below.

Legend: `✓` already valid (in base) · `+` new combo `mod-uac` adds · `D` Death Knight (already all-race — see note).

| Race \ Class | War | Pal | Hun | Rog | Pri | DK | Sha | Mag | Wlk | Dru |
|---|---|---|---|---|---|---|---|---|---|---|
| Human (1)      | ✓ | ✓ | + | ✓ | ✓ | D | + | ✓ | ✓ | + |
| Orc (2)        | ✓ | + | ✓ | ✓ | + | D | ✓ | + | ✓ | + |
| Dwarf (3)      | ✓ | ✓ | ✓ | ✓ | ✓ | D | + | + | + | + |
| Night Elf (4)  | ✓ | + | ✓ | ✓ | ✓ | D | + | + | + | ✓ |
| Undead (5)     | ✓ | + | + | ✓ | ✓ | D | + | ✓ | ✓ | + |
| Tauren (6)     | ✓ | + | ✓ | + | + | D | ✓ | + | + | ✓ |
| Gnome (7)      | ✓ | + | + | ✓ | + | D | + | ✓ | ✓ | + |
| Troll (8)      | ✓ | + | ✓ | ✓ | ✓ | D | ✓ | ✓ | + | + |
| Blood Elf (10) | + | ✓ | ✓ | ✓ | ✓ | D | + | ✓ | ✓ | + |
| Draenei (11)   | ✓ | ✓ | ✓ | + | ✓ | D | ✓ | ✓ | + | + |

New combos per race (38 total): Human 3 (Hun, Sha, Dru) · Orc 4 (Pal, Pri, Mag, Dru) · Dwarf 4 (Sha,
Mag, Wlk, Dru) · Night Elf 4 (Pal, Sha, Mag, Wlk) · Undead 4 (Pal, Hun, Sha, Dru) · Tauren 5 (Pal, Rog,
Pri, Mag, Wlk) · Gnome 5 (Pal, Hun, Pri, Sha, Dru) · Troll 3 (Pal, Wlk, Dru) · Blood Elf 3 (War, Sha,
Dru) · Draenei 3 (Rog, Wlk, Dru).

**Death Knight (class 6):** present for every race in base `playercreateinfo` already, so it is **not** a
new combo for anyone. `CharBaseInfo` still includes all DK tiles (harmless), but the SQL emitters
**exclude DK** — no new `playercreateinfo` is needed, and DK carries special handling (starts at level
55 in Ebon Hold, a creation level-requirement path). Excluding it avoids disturbing that flow.

### Flagged problem combos (QA, not architectural blockers)
1. **Off-race shamans** (e.g. Human/Gnome/Undead/Blood Elf shaman) — totem display handled by
   `player_totem_model` (§5.1). In scope, Phase 1 (1d).
2. **Foreign class trainers in starter zones** (e.g. Tauren Mage in Red Cloud Mesa) — **resolved
   (Phase 2b).** Snapshot-driven placement beside native trainers; nudge coordinates via
   `data/trainer_overrides.yaml` if in-game QA finds overlap or bad facing.
3. **Starting quests with race/class checks** — warlock imp handled in **1g** via tiered quest patches
   and spell grants (§8.1). Hunter pets use a separate class-wide level-1 slice (§8.2). mod-arac's
   global mask is not replicated.
4. **Druid forms on non-druid races** — form models are shared in 3.3.5a; expected cosmetic-fine, but
   spot-check during QA.

---

## 7. Revert / uninstall strategy

AzerothCore's DB updater is one-directional (no native down-migrations), so every install file has a
**companion uninstall file** applied manually. Because all added data is keyed by `(race, class)` and
overlay IDs occupy a known contiguous range above `base_max`, revert is clean:
- `DELETE FROM playercreateinfo* WHERE (race, class) IN (<added combos>);`
- `DELETE FROM player_totem_model WHERE …;` (restore prior rows if any were replaced)
- `DELETE FROM skillraceclassinfo_dbc WHERE ID > <base_max>;` (or by the emitted ID range)
- Revert `quest_template.AllowableRaces` per patched quest ID (1g warlock)
- `DELETE FROM playercreateinfo_spell_custom` for tier-C warlock spell grants (1g)
- `DELETE FROM creature WHERE guid BETWEEN 6000000 AND 6009999` (starter trainers, 2b)
- Hunter pet slice (optional): run `mod_uac_hunter_pet_spell_*_uninstall.sql` pair — removes class-wide hunter spell grants and `spell_dbc` overlays without touching other mod-uac data

Uninstall files live under `data/sql/db-uninstall/` and are documented in the README. The client
side reverts by removing the MPQ from `Data/`.

---

## 8. Phasing and task breakdown

### Phase 1 — generator + data module (makes all combos creatable and functional)
- **1a — WDBC codec + round-trip test.** `DbcTable` read/write; prove byte-exact round-trip on the
  stock `CharBaseInfo.dbc`, `SkillRaceClassInfo.dbc`, `CharStartOutfit.dbc`. Nothing is built on the
  codec until this passes.
- **1b — `SkillOverlayEmitter`.** Minimal `skillraceclassinfo_dbc` delta via mask analysis (§3.5);
  IDs above source max (§5.3); install + uninstall SQL.
- **1c — `PlayerCreateEmitter`.** `CanonicalKitResolver` (kit-from-class + location-from-race);
  emit the four `playercreateinfo*` tables; install + uninstall SQL; exclude DK.
- **1d — `TotemEmitter` + quest investigation.** `player_totem_model` for off-race shamans;
  document why mod-arac's global `quest_template` UPDATE is not replicated.
- **1e — `ClientPatchEmitter` (complete).** Pure-Python MPQ v1 writer; `CharBaseInfo.dbc` full matrix
  only (no preview DBCs — server-authoritative skills/outfit via SQL). Output: `client-patch/patch-A.mpq`.
- **1f — Module packaging + docs (complete).** `CMakeLists.txt` (data-only); SQL path verified against
  `UpdateFetcher.cpp` (`data/sql/db-world/` auto-applied; `db-uninstall/` manual); operator README.
- **1g — Class quest emitters (complete).** Shipped:
  - **`ClassQuestEmitter`** — warlock imp: tier A quest patches + tier C `playercreateinfo_spell_custom`
    grants; per-quest revert masks.
  - **`HunterPetEmitter`** — optional class-wide level-1 pet kit (`mod_uac_hunter_pet_*` SQL pair);
    `spell_dbc` export for castable-at-1 overlays.
  - **§8.3 faction-wide unlock** — warrior, shaman, druid, paladin travel-gated quest chains.

#### 8.1 Class quest tiers (1g)

Warlocks need **Summon Imp** (688) from a level-1 quest chain; without it the class is unplayable
until ~level 10. Stock chains are race-gated on `quest_template.AllowableRaces`.

| Tier | Rule | Action | Example |
|------|------|--------|---------|
| **A** | Reference quest in the **same starter zone** | Patch `AllowableRaces` on specific quest IDs | Dwarf Warlock → gnome imp chain in Dun Morogh (zone 1) |
| **B** | Same **continent**, different zone | Same targeted patch (player travels) | Human Hunter → dwarf taming chain in Kharanos (future slice) |
| **C** | **Cross-continent** | Grant spell at creation via `playercreateinfo_spell_custom` **only for hard gates** (warlock imp); otherwise faction-wide quest patch + travel | Night Elf Warlock → imp spell; Night Elf Warrior → horde/alliance stance chain via travel (§8.3) |

**Canonical warlock output (38-combo matrix):**

| Combo | Tier | Mechanism |
|-------|------|-----------|
| Dwarf (3,9) | A | Patch quests 3115, 1599 (`64` → `68`) |
| Night Elf (4,9) | C | Grant spell 688 at creation |
| Tauren (6,9) | — | Stock orc quest 1485 already allows horde mask `690` |
| Troll (8,9) | — | Same horde mask |
| Draenei (11,9) | C | Grant spell 688 at creation |

Uninstall restores **exact stock masks per quest ID** and deletes spell-custom rows by
`(racemask, classmask, Spell)`.

#### 8.2 Hunter pets at level 1 (optional, class-wide)

Hunter taming is gated differently from warlock imp:

| Aspect | Warlock imp | Hunter pets |
|--------|-------------|-------------|
| Scope | Per new combo (38-matrix) | **All hunters** (`racemask=0`, `classmask=4`) |
| Stock gate | Level-1 quest chain, race-gated | Level-10 quest chain + spell `BaseLevel` 10 |
| Mechanism | Tier A/B quest patch or tier C spell grant | Spell grant + `spell_dbc` level patch |
| Revert | Main uninstall set | **Separate** `mod_uac_hunter_pet_*` uninstall pair |

Stock level-10 taming quests cannot be patched for level-1 play (`MinLevel` 10). Granting spells at creation is insufficient because client `Spell.dbc` sets `BaseLevel`/`SpellLevel` to 10 for the pet kit. mod-uac therefore emits:

1. **`playercreateinfo_spell_custom`** — spells 1515, 883, 2641, 6991, 982 at hunter creation (requires `PlayerStart.CustomSpells = 1`).
2. **`spell_dbc` REPLACE rows** — full-row overlays from canonical `Spell.dbc` with fields 38/39 patched to 1.

Operators who want stock hunter pacing run only the hunter uninstall files; hunters revert to level-10 quest gating while off-race combos and other mod-uac data remain. Off-race hunters (Human, Undead, Gnome) benefit from the class-wide policy without a separate tier-B quest patch to Kharanos.

#### 8.3 Travel-gated class quests (shipped in Phase 1g)

Warlock imp and hunter pets are the extremes (spell grant at creation). Most other class gates use
**tier A/B/C quest patches only** — players travel when they can, even if that means finishing a
level-4 or level-10 chain at character level 12–15. **Do not** use tier-C spell grants for these unless
the class is literally unplayable without the ability (warlock imp rule).

**Faction-wide unlock:** For travel-gated classes, patch the reference chain so the **entire faction**
can take the quests. Collapse patches per quest ID to stock mask OR full faction mask:

| Faction | `AllowableRaces` target |
|---------|-------------------------|
| Alliance | `1101` (Human, Dwarf, NE, Gnome, Draenei) |
| Horde | `690` (Orc, Undead, Tauren, Troll, BE) |

Revert restores the **exact stock mask per quest ID** (same rule as warlock).

**Anti-gray companion patches:** Travel delays mean players often arrive above the quest’s nominal
level. For each patched class-quest chain, emit `quest_template_addon` updates where stock
`MaxLevel` would hide the quest — typically set `MaxLevel = 0` (no cap). Stock AC 3.3.5a already
uses `MaxLevel = 0` on these chains, so the emitter skips addon SQL unless catalogued caps exist;
uninstall restores stock addon rows when emitted.

| Class | Stock gate | Reference chains (stock masks) | Notes |
|-------|------------|----------------------------------|-------|
| **Warrior** | Defensive Stance ~10 | Horde: Path of Defense etc. (`690` already). Alliance: Dwarf IF `1678–1679` (`68` → `1101`); NE line already `1101` | Only **1 new combo** (BE warrior). Tier B/C → quest patch, not spell grant. |
| **Shaman** | Earth totem **4**, Fire **10**, Water **20** | Orc `1516–1518` (`130` → `690`), Tauren `1519–1521` (`32` → `690`); Draenei `9449–9451` already `1101`; Fire/Water already faction-wide in stock | Faction-wide unlock + anti-gray is the default. |
| **Druid** | Bear form **10** | NE `5921→6001` (`8` → `1101`), Tauren `5922→6002` (`32` → `690`); Moonglade + Body and Heart | Eight new druid combos travel to the appropriate reference chain. |
| **Paladin** | Redemption **12** | Human SW `1642→1788` (`1` → `1101`), Dwarf IF `1646→1785` (`4` → `1101`), Draenei `9598→9600` (`1024` → `1101`), BE `9676→9685` (`512` → `690`) | Horde paladins reach Eversong; gnome paladin uses IF chain (tier **A**). |

**Tier C spell-grant exceptions (keep rare):**

- Warlock Summon Imp (cross-continent new combos) — emitted.
- Hunter pet kit — optional class-wide slice (§8.2), not tier logic.
- Shaman Call of Earth — **maybe**, only if quest patching + anti-gray fails QA (open; Phase 2).

**Emitter:** `FACTION_UNLOCK_CHAINS` in `class_quest_catalog.py`; `compute_faction_quest_patches()`
in `emit_class_quest.py` merges with warlock per-combo patches; optional `quest_template_addon`
install/uninstall pair for anti-gray rows.

### Phase 2 — gameplay QA + polish

- **Playerbots (resolved).** With mod-uac `playercreateinfo` data applied, `mod-playerbots` on
  Playerbot-branch AzerothCore already enumerates and spawns the new race/class combos; no additional
  mod-uac emitter work was required beyond the Phase 1 playercreateinfo rows.
- **2b — Starter trainers (complete).** World DB snapshot (`tools/capture_snapshot.py`,
  `data/snapshot/`) + `TrainerEmitter` → `mod_uac_starter_trainers.sql` (26 spawns, GUIDs
  `6000000–6000025`), placement worksheet, YAML overrides. Wired into `generate_canonical.py` /
  `generate_local.py`. Spec: [mod-uac-trainer-emitter-spec.md](mod-uac-trainer-emitter-spec.md).
- **Remaining gameplay QA.** Shaman Call of Earth spell-grant fallback if quest patching fails QA;
  druid form spot-checks; trainer coordinate nudges via `trainer_overrides.yaml`.

---

## 9. Open questions / to-verify

1. **Updater SQL scan path** — **resolved (1f).** Module install SQL: `modules/<mod>/data/sql/db-world/`
   (directory name must contain `world`). Uninstall: `data/sql/db-uninstall/` (must **not** contain
   `world`). Source: `UpdateFetcher.cpp` (`ReceiveIncludedDirectories`, module branch).
2. **`skillraceclassinfo_dbc` columns** — mapped from `SkillRaceClassInfofmt` in the emitter; re-verify
   if AC schema changes.
3. **Client preview DBCs** — **resolved (1e).** `CharBaseInfo.dbc` alone is sufficient for creation-screen
   combo tiles; skills/outfit preview is server-authoritative via SQL overlays.
4. **`quest_template` edit** — resolved in 1g (§8.1–8.3).
5. **Shaman Call of Earth at level 4** — faction quest patch + anti-gray shipped (§8.3); spell-grant
   fallback reserved for gameplay QA if travel proves insufficient.
6. **`mod-playerbots` combo enumeration** — **resolved.** New combos work once `playercreateinfo`
   rows are applied; verified on Playerbot-branch AzerothCore.

---

## 10. Dependencies and environment

- **Language:** Python 3 (pure Python; no native dependencies).
- **`requirements.txt`:** `requests` (fetch the pinned canonical release); `PyMySQL` (world DB
  snapshot capture only — emitters read JSON and stay DB-free). The WDBC codec is stdlib
  `struct`; the MPQ writer is in-repo. (There is **no** cross-platform pip package that *writes*
  MPQs — `mpq`/HearthSim is read/patch-only and states "Writing MPQs is not supported"; `pystormlib`
  is Windows-x86 read-only; `mpyq` is read-only — hence the pure-Python writer.)
- **Core target:** AzerothCore WotLK 3.3.5a.
- **Canonical DBC source:** `wowgaming/client-data`, pinned at tag **`v19`**.
- **Distribution:** module repo with checked-in SQL, the generator, and one universal client MPQ.

### Proposed on-disk layout
```
mod-uac/
  data/sql/db-world/            # install SQL (auto-applied by AC updater)
  data/sql/db-uninstall/        # companion revert SQL (manual)
  data/snapshot/                # baked world snapshot for trainer emitter
  data/trainer_overrides.yaml   # optional trainer placement overrides
  tools/aracgen/                # generator package
      dbc.py  sources.py  matrix.py  kits.py
      emit_skill.py  emit_player.py  emit_totem.py  emit_class_quest.py
      emit_hunter_pet.py  emit_trainers.py  emit_client.py  mpq.py
      snapshot.py  trainer_catalog.py  schema_emit.py
  tools/capture_snapshot.py     # world DB snapshot capture
  tools/generate_local.py       # LocalDbcSource     -> operator SQL only
  tools/generate_canonical.py   # CanonicalDbcSource(v19) -> checked-in SQL + shared MPQ
  tools/requirements.txt
  client-patch/patch-A.mpq      # universal client artifact
  CMakeLists.txt                # data-only module stub
  README.md
```

---

## 11. Reference: source citations

- `Player.cpp:496–501` — `GetPlayerInfo` null check = server-side combo gate.
- `Player.cpp:622, 11926–11942` — `LearnDefaultSkills` gated on `GetSkillRaceClassInfo`.
- `Player.cpp:630` — `GetCharStartOutfitEntry` / `CharStartOutfit` DBC is the primary equip path
  (rndbots and headless creation depend on this). `playercreateinfo_item` (`666–667`) is secondary.
- `Player.cpp:12457, 3106, 13826` — spell/skill learning gated on `GetSkillRaceClassInfo`.
- `CharacterHandler.cpp:274+` — `HandleCharCreateOpcode`; no `CharBaseInfo` check.
- `DBCStores.cpp:238` — file load then `LoadFromDB`.
- `DBCStores.cpp:352` — `SkillRaceClassInfo` wired to `skillraceclassinfo_dbc`.
- `DBCStores.cpp:423, 895–905` — `SkillRaceClassInfoBySkill` built from merged store; mask semantics.
- `DBCStore.cpp` (`DBCStorageBase::LoadFromDB`) → `DBCDatabaseLoader.cpp:40, 56, 78, 128` — merge-by-ID
  overlay, "override from DB".
- `DBCStores.cpp` — absence of any `CharBaseInfo` reference (server does not load it).
- `data/sql/base/db_world/playercreateinfo.sql` — authoritative source for §6 (62 existing combos;
  38 new). Companion base files present: `playercreateinfo_action.sql`, `_item.sql`, `_skills.sql`,
  `_spell_custom.sql`, `_cast_spell.sql` (kit-clone sources for 1c).
