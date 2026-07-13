# AGENTS.md

Guidance for AI coding assistants (Cursor, Claude Code, Aider, etc.) working
on the Unlock All Classes mod. If you're a human, read the [README](README.md)
first -- this file assumes you've already seen the basics.

> For Claude Code specifically, [CLAUDE.md](CLAUDE.md) points at this file.
> Everything here applies to every agent.

---

## Purpose

Allow any playable race to create and play any playable class, with a design that is
**maintainable, revertable, and free of mystery binaries**, and that is **reusable by other
server operators** running stock or lightly-customized AzerothCore installations.

### Goals
- No unexplained binary DBC files. Every artifact is either generated from a known source or is
  human-readable SQL.
- No hand-applied, irreversible SQL. Everything is applied by AzerothCore's DB updater and has a
  companion revert.
- **Zero server-side binary DBC edits.** (See [engineering doc §3](docs/mod-uac-engineering-implementation.md#3-source-grounded-findings).)
- Exactly three small, universal client artifacts (generated MPQs under `client-patch/`), producible in pure Python.
- Deterministic and reproducible: generation happens against a pinned canonical source, or against
  the operator's own installed DBCs.

### Non-goals
- Custom NPC dialogue beyond the generated trainers and quest patches (unrelated to this module).

**Resolved / in scope (formerly deferred):** `mod-playerbots` already spawns new combos once
mod-uac's `playercreateinfo` rows are applied. Starter-zone class trainers ship in
`mod_uac_starter_trainers.sql` (see [docs/trainer_worksheet.md](docs/trainer_worksheet.md)).

---

## Where things live

```
mod-uac/
  data/sql/db-world/            # install SQL (auto-applied by AC updater)
  data/sql/db-uninstall/        # companion revert SQL (manual; dirname must not contain "world")
  tools/aracgen/                # generator package
      dbc.py  sources.py  matrix.py  kits.py
      emit_skill.py  emit_player.py  emit_totem.py  emit_class_quest.py
      emit_totem_quest.py  emit_hunter_pet.py  emit_trainers.py  emit_client.py  mpq.py
      snapshot.py  trainer_catalog.py  capital_trainer_catalog.py  schema_emit.py
      class_quest_catalog.py  totem_quest_catalog.py
  tools/capture_snapshot.py     # world DB snapshot capture (PyMySQL)
  tools/generate_local.py       # LocalDbcSource     -> operator SQL + standard MPQ
  tools/generate_canonical.py   # CanonicalDbcSource(v19) -> checked-in SQL + client MPQs
  data/snapshot/                # baked world snapshot (schemas + trainer extracts)
  data/item_prototypes.json     # minimal outfit item class/subclass lookup (from snapshot refresh)
  data/trainer_overrides.yaml   # optional trainer placement overrides (starter + capital)
  tools/requirements.txt
  client-patch/unlock-only/patch-z.mpq   # CharBaseInfo + SkillRaceClassInfo (equip + UI normalization)
  client-patch/standard/patch-z.mpq      # above + v19 CharStartOutfit + overlays
  client-patch/enhanced/patch-z.mpq      # above + HD baseline CharStartOutfit + overlays
  data/client/hd_outfit_templates.json   # deduplicated HD stock outfit templates (54)
  data/client/hd_outfit_stock_index.json # 126 stock rows -> template_id
  CMakeLists.txt                # data-only module stub
  README.md
```

---

## Coding conventions

- **Python 3.11**. Use modern syntax: `X | Y` unions, `list[int]`, `datetime.UTC`
  instead of `datetime.timezone.utc`. Ruff will tell you.
- **Comments explain why, not what.** A comment like `# increment counter` on
  `counter += 1` is noise. A comment explaining a non-obvious trade-off is
  gold.
- **Write the test before you believe the fix.** Passing tests will catch
  more regressions than any amount of local eyeballing. Run from `tools/`:
  `python -m pytest` and `python -m ruff check .`.
- **Emitters produce install + uninstall pairs.** SQL under
  `data/sql/db-world/` and `data/sql/db-uninstall/`; never hand-edit
  checked-in SQL — regenerate via `generate_canonical.py` (or
  `generate_local.py` for operator baselines).
- **Schema-driven SQL.** World-table emitters (`emit_skill`, `emit_player`,
  `emit_totem`, `emit_class_quest`, `emit_hunter_pet`, `emit_trainers`) render
  INSERT/REPLACE/UPDATE rows from the baked snapshot's `TableSchema` via
  `schema_emit.py` — column lists and defaults come from the operator's world DB
  capture (or AC base DDL bootstrap), not hardcoded in emitters.
- **Source world facts from the snapshot, don't hardcode them.** Anything the
  emitter needs to *know about the game world* — which NPCs exist and where they
  spawn, what a trainer teaches, a quest's stock `AllowableRaces`/level, item
  categories, coverage of a zone — must come from the captured snapshot
  (`tools/capture_snapshot.py` → `data/snapshot/`), the same way starter and
  capital trainers are placed by *reading* captured trainers rather than a table
  of entries/coordinates. If you find yourself writing a literal NPC entry,
  spawn coordinate, or "this city already has class X" list into an emitter or
  catalog, stop: capture it instead (extend `capture_trainer_data` /
  `SCHEMA_TABLES` and refresh the snapshot). The **only** things that may be
  hardcoded are facts with *no data source* — e.g. capital geography
  (`capital_trainer_catalog.py`: map/center/radius/faction/home-races, the analog
  of the starter zones' `playercreateinfo` anchors) and the reference quest
  chains in `class_quest_catalog.py` / `totem_quest_catalog.py`. Keep those
  minimal, comment *why* they can't be captured, and cross-check them against the
  live DB (see the §9.7 `--verify-catalog` drift-guard idea).

---

## Commits

**Never run git on the maintainer's behalf.** Do not run `git add`, `git commit`,
`git push`, or any other command that creates or publishes commits — even when
the user says they "need a commit" or asks you to "commit this phase." Your job at
boundaries is to **provide a single-line commit message** for the maintainer to
copy and run themselves.

Commits are made **manually by the maintainer**. At every commit boundary (a
finished change, a phase boundary, or a session wrap), provide that message in
[Conventional Commit](https://www.conventionalcommits.org) style.

Examples from this repo:

> `feat(1g): class quest ungates for warlock, hunter pets, and travel-gated classes`
>
> `feat(1e): add client MPQ patch with full CharBaseInfo matrix`
>
> `feat(aracgen): add totem model emitter for off-race shamans`

Conventions:

- Use the standard types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`,
  `build`, `ci`. Most deliverables here are `feat`.
- **Scope:** use the **phase id** (`1a` … `1g`, `1f`, `1e`) when the commit
  lands a planned phase slice; use **`aracgen`** for cross-cutting generator
  infrastructure that is not tied to one phase (early codec/emitter work used
  this). Optional narrower scopes (`mpq`, `class-quest`) are fine if clearer.
- Keep it to **one line**, imperative mood, no trailing period. Do not add a
  body unless the maintainer asks for one.
- Regenerated SQL under `data/sql/` and all three `client-patch/*/patch-z.mpq` files belong in
  the same commit as the emitter change that produced them (same phase).

---

## Phase map

Work is tracked in [README.md](README.md) and
[docs/mod-uac-engineering-implementation.md](docs/mod-uac-engineering-implementation.md) §8.

| Phase | Deliverable (representative paths) |
|-------|-----------------------------------|
| **1a** | `tools/aracgen/dbc.py`, `tools/tests/test_dbc_roundtrip.py` |
| **1b** | `tools/aracgen/emit_skill.py`, `data/sql/db-world/mod_uac_skillraceclassinfo_dbc.sql` |
| **1c** | `tools/aracgen/emit_player.py`, `mod_uac_playercreateinfo*.sql` |
| **1d** | `tools/aracgen/emit_totem.py`, `mod_uac_player_totem_model.sql` |
| **1e** | `tools/aracgen/mpq.py`, `emit_client.py`, `client-patch/*/patch-z.mpq`, `data/client/hd_outfit_*.json` |
| **1f** | `CMakeLists.txt`, `README.md`, docs |
| **1g** | `emit_class_quest.py`, `class_quest_catalog.py`, `mod_uac_quest_template.sql`, optional `mod_uac_hunter_pet_*.sql` |
| **2b** | `emit_trainers.py`, `snapshot.py`, `mod_uac_starter_trainers.sql`, `docs/trainer_worksheet.md` |
| **2e** | Schema contract on all world-table emitters (`schema_emit.py`, snapshot schemas) |

Phase 1, starter trainers (**2b**), and schema-contract retrofit (**2e**) are **complete**.
Remaining Phase 2 work is gameplay QA and polish (see engineering doc §8).

Generator entry points: `tools/generate_canonical.py` (checked-in artifacts),
`tools/generate_local.py` (operator-specific SQL). Shared wiring lives in
`tools/aracgen/cli.py`.

---

## Multi-phase work: pause at phase boundaries

When a plan is explicitly structured into phases (**1a**, **1b**, … **2b**, or
later slices), **stop after each phase completes** before beginning the next one.

At the boundary:

1. Report what the phase delivered and what comes next.
2. Ask: *"Ready to commit this phase before I continue?"*

Then wait for the answer.

Why this rule exists: phases here have different risk profiles (e.g. 1g touches
shared `quest_template` rows; 1e adds the only binary client artifact). The
maintainer may want a rollback point, Bugbot review, or in-game QA before the
next layer lands. Executing all phases in one uninterrupted pass removes that
option.

Example boundary report for **this** codebase:

> **Phase 1g complete.** 75 tests pass, ruff clean. Delivered:
> `class_quest_catalog.py` (`FACTION_UNLOCK_CHAINS` for §8.3),
> `emit_class_quest.py` (warlock tiers + faction-wide quest unlock),
> regenerated `data/sql/db-world/mod_uac_quest_template.sql` and uninstall pair,
> optional hunter pet SQL slice.
> Next up: **1e** (client MPQ) unless you want to commit 1g first.

Then wait. If the user says "continue", proceed. If they say "commit first" (or
similar), provide the one-line conventional message only — **do not** run git.

This rule applies equally when work *grows* a phase boundary mid-session (e.g.
§8.3 faction unlocks split out of 1g into their own commit). Name the split,
ask whether to land the first piece before starting the second.

---

## Design pivots at implementation time

When implementation reveals a simpler shape than the plan called for,
do not silently follow the plan as written. The engineering doc is a
proposal based on incomplete information; reading stock AC data often
surfaces patterns that meet the same exit criteria with less change.
**Plans are proposals, not contracts.**

The right shape:

1. **Pause and explain the pivot.** Name the original plan, the
   simpler alternative, the trade-off, and ask before implementing.
2. **If the user approves, implement the new shape.** Update
   `docs/mod-uac-engineering-implementation.md` / README checkboxes to
   match what shipped.
3. **Record the pivot somewhere durable** (engineering doc §8–9, or a
   short comment in the emitter catalog).

Example pivot from this project:

> **Plan:** tier-C `playercreateinfo_spell_custom` grants for every
> cross-continent class gate (like warlock imp).
> **Pivot:** §8.3 faction-wide `quest_template.AllowableRaces` patches
> for warrior/shaman/druid/paladin — players travel to the stock chain;
> spell grants reserved for true hard gates only.
> **Trade-off:** off-race paladins must reach Eversong; starter trainers ship separately in
> `mod_uac_starter_trainers.sql` (Phase **2b**).

Anti-patterns:

* **Silently substituting designs** (e.g. emitting mod-arac's blanket
  `AllowableRaces = 1791` instead of per-quest revert SQL).
* **Slavishly following the doc** when stock `quest_template_addon.MaxLevel`
  is already `0` and anti-gray SQL would be empty noise — skip emission but
  document why.
* **Pivoting without naming the trade-off** (e.g. level-1 hunter pets apply to
  *all* hunters, not just new combos — intentional QoL, isolated uninstall).
