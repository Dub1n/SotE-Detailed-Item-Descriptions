# Param Extraction Blockers (Blinkbolt & AoW Behavior Chains)

This note documents everything we tried to surface missing behavior/damage data for Blinkbolt and other unmatched Ashes/skills, what we actually found, and what is still blocking full extraction.

It is meant for agents working with this repo so they **stop trying to “fix” this via params alone** and instead either:

- provide missing behavior IDs, or
- accept that some skills cannot currently be resolved and must be flagged as such.

---

## 1. What we already tried

We have exhausted all obvious data sources inside the repo:

- Parsed every TAE we have for Behavior events (type 304, the only TAE event that carries a `behaviorJudgeId`):
  - `PARAM/tae_behavior_map/tae/c0000/*.tae`
  - `dump/tae_collected/*.tae` (925 files, 106 with any type-304 events)
- Verified that `dump/c_.anibnd/*.hkx` contains no TAEs and thus no type-304 events.
- Re-ran `scripts/tae_dump_behaviors.py` on all TAEs above and consolidated behavior IDs into:
  - `work/tae_behavior_map/behaviors_dump.json`
- Mined `BehaviorParam_PC.csv` by name:
  - Looked for rows labeled like “Shared [AOW] …” and similar patterns.
  - Used those to build a heuristic behavior map for skills that had recognizable names.
  - Stored this in `work/tae_behavior_map/behavior_ids_param.json`.
  - Regenerated `work/skill_dump.json` with this map.
- Full‑text search across **all** decompressed content for Blinkbolt-related identifiers:
  - PARAM exports
  - Smithbox dumps
  - `dump/` hierarchy
  - `docs/`
  - message XML/JSON
  - `work/`
- Search keys included (non‑exhaustive):
  - AoW ID `413000`
  - swordArts IDs: `4130`, `5130`, `5140`
  - custom-weapon IDs (Blinkbolt variants): `1413020`–`1413062`
- Inspected `SwordArtsParam`:
  - Blinkbolt entries show `swordArtsTypeNew = 280` (offset from `a600`).
  - The corresponding offset TAE file (`a880.tae`) has **no** type‑304 events.
- Attempted to unpack additional TAEs from `*.anibnd(.dcx)` using Yabber under mono/wine:
  - Extracted TAEs matched what we already had.
  - No new TAEs with type‑304 Behavior events appeared.

---

## 2. Findings (hard constraints from the data we actually have)

### 2.1 TAE coverage

- The TAEs in the repo expose **only a small, generic set** of `behaviorJudgeId`s:
  - `{111, 165, 192, 193, 470, 500, 501, 510, 511, 515, 516, 530, 531, 550, 560, 561, 603, 3026, 3027, 6862}`
- **No** sword‑art‑specific IDs (for example, `430–439`) appear in any scanned TAE.
- For Blinkbolt’s swordArts ID (`4130`) the offset TAE (`a880.tae`) has zero type‑304 events, so we get no behavior IDs from there at all.

### 2.2 BehaviorParam_PC

- `BehaviorParam_PC.csv` has **no** rows named “Blinkbolt” or obvious variants.
- No rows reference `4130` or `14130xx` in any obvious ID or name field.
- The only “by name” hits for Ashes we can rely on are generic “Shared [AOW] …” style rows:
  - These cover **68/112** skills when we build `behavior_ids_param.json`.
  - Blinkbolt and ~44 other skills have **no** reliable name‑based BehaviorParam_PC mapping.

### 2.3 Magic table

- `Magic.csv` has **no** rows with `refId*` starting with `4130`.
- No records are named “Blinkbolt” or similar.
- There is therefore **no Magic → Bullet/Atk/SpEffect chain** corresponding to the player Blinkbolt AoW.

### 2.4 Bullet / Atk / SpEffect

- IDs starting with `413xxxxx` do exist, but:
  - They belong to NPC/dummy entries (e.g. Demi‑Human Queen).
  - These rows typically have `atkAttribute = 254` or otherwise match our “dummy/VFX” heuristics.
  - They are **not** wired to the player AoW as used in our skills.

### 2.5 EquipParamCustomWeapon

- There are EquipParamCustomWeapon rows (e.g., `1413020–1413062`) for prebuilt “Lightning <weapon> - Blinkbolt” instances:
  - These define base weapon + gem + reinforce for custom Blinkbolt weapon entries.
  - CharaInitParam references them as starting gear.
  - They **do not** link to BehaviorParam, Magic, Bullet, or Atk chains that give us hit data.

### 2.6 SwordArtsParam

- SwordArtsParam entries exist for Blinkbolt and its related IDs:
  - `4130` (Blinkbolt), `5130` (Twinaxe), `5140` (Long‑hafted Axe)
  - They use `swordArtsTypeNew = 280` with an offset that points to `a880.tae`.
- `a880.tae` (the TAE we would expect to carry their behavior events) contains **no** type‑304 events.
- This means that for these sword arts:
  - The TAE → BehaviorParam_PC path is effectively invisible from the TAEs we currently have.

---

## 3. Current state of `work/skill_dump.json`

- Using `behavior_ids_param.json` (name‑matched BehaviorParam_PC rows), we can populate **behavior sections for 68/112 skills**.
- For the remaining **44** skills (including all Blinkbolt variants):
  - The `behavior` block in `work/skill_dump.json` is empty.
  - Only Magic‑derived data exists, and for Blinkbolt even that is missing (no Magic refs).
  - Therefore there are **no Behavior → Bullet → Atk → SpEffect chains** in the dump for these skills.

---

## 4. What is actually blocking us

For Blinkbolt and ~44 other unmatched skills/AoWs, we lack **any trustworthy source of behavior IDs**.

Specifically, for those skills we have:

- no type‑304 Behavior events in any TAE we possess,
- no BehaviorParam_PC rows whose names or IDs can be confidently matched,
- no Magic rows that reference the relevant ID ranges or names,
- no player Bullet/Atk rows keyed by the skill IDs.

Without `behaviorJudgeId`s, we cannot construct:

- the set of BehaviorParam_PC rows that fire when the skill is used,
- the Bullet and AtkParam_Pc rows those behaviors point to,
- or the SpEffectParam chain for on‑hit statuses/buffs.

In other words: **we have no graph to walk**, so there is no safe way to derive actual damage/stance/status numbers for these skills from the existing data.

---

## 5. What we need next (to fully unblock)

There are only two realistic paths forward:

### 5.1 A behavior ID map for the unmatched skills

We need a file of the form:

- variationId for Ashes of War: `0` (shared player AoW slot)
- manual mapping for each unmatched skill:

  - `skill_id → [behaviorJudgeId, behaviorJudgeId, ...]`

Source of truth **must** be one of:

- TAEs from a game dump that actually contain the missing type‑304 events, or
- manual pairing of specific BehaviorParam_PC rows to the AoWs (e.g., from DSAnimStudio, DSMapStudio, or a human who knows the move chains).

Once we have this map, we can:

- merge it into the existing behavior map (`work/tae_behavior_map/behavior_ids_param.json` or a new file),
- re‑run `scripts/skill_dump.py` with that behavior map,
- and obtain complete Behavior → Bullet/Atk/SpEffect chains for the previously unmatched skills.

### 5.2 Additional TAEs with type‑304 events

If new TAEs exist that include behavior events for Blinkbolt and the other missing skills:

- Add them under a directory such as:
  - `dump/tae_collected_new/`
- Re-run:

      python scripts/tae_dump_behaviors.py \
        --tae-root dump/tae_collected_new \
        --out work/tae_behavior_map/behaviors_dump_new.json

- Merge the new behavior IDs into the main behavior map and re‑dump skills.

If no new TAEs are available, we are back to 5.1 (manual behavior IDs).

---

## 6. Commands of record

These commands are the **canonical** ones we have used so far:

### 6.1 Scan TAEs for behavior events

    python scripts/tae_dump_behaviors.py \
      --tae-root dump/tae_collected \
      --out work/tae_behavior_map/behaviors_dump.json

### 6.2 Build behavior map from BehaviorParam names

This step is already done; the result lives in:

- `work/tae_behavior_map/behavior_ids_param.json`

It was generated by heuristic name matching in `BehaviorParam_PC.csv` to cover skills with “Shared [AOW] ...” style rows.

### 6.3 Regenerate skill dump with current map

    python scripts/skill_dump.py \
      --skills work/responses/ready/skill.json \
      --behavior-map work/tae_behavior_map/behavior_ids_param.json \
      --out work/skill_dump.json

You can replace `behavior_ids_param.json` with a richer map (TAE‑derived or manual) to improve coverage.

---

## 7. Guidance for agents

### 7.1 What you **must not** do

For Blinkbolt and the other unmatched skills:

- Do **not** invent or “guesstimate” Behavior IDs.
- Do **not** try to derive damage/stance/status numbers purely from:
  - EquipParam*,
  - Magic,
  - Bullet,
  - or AtkParam_Pc,
  unless you have actual behavior IDs that link the skill to those rows.
- Do **not** assume NPC/413xxxxx entries apply to the player AoW.

If a skill has no behavior mapping, **treat its behavior data as unavailable**.

### 7.2 What you **should** do

When working on param extraction or explanations:

- Check `work/skill_dump.json` first:
  - If `behavior` is populated, use those Behavior → Bullet → Atk → SpEffect chains as the source of truth.
  - If `behavior` is empty for a given skill:
    - Acknowledge that behavior‑based numbers are currently unavailable.
    - Only use what we **do** have (e.g., scaling, resident SpEffects, any Magic data if present).
    - Mark the skill in your output as “requires manual behavior mapping” or similar.
- If you have access to additional tooling (DSAS, DSMapStudio, etc.) and can **personally** identify BehaviorParam_PC rows for Blinkbolt or other blocked skills:
  - Extract the `behaviorJudgeId`s and share them in a map:
    - `skill_id -> [behaviorJudgeId, ...]`
  - Once that exists, we can wire it into the pipeline and regenerate `work/skill_dump.json`.

### 7.3 Summary

- 68/112 skills are fully wired through behavior chains and safe to use.
- ~44 skills, including Blinkbolt, **cannot** be resolved with the data currently in this repo.
- Future progress depends on someone providing **correct behavior IDs** or **additional TAEs** with type‑304 events.

Until then, **do not “fill in” missing numbers for these skills**. Treat them as partially supported: scaling and static effects may be known, but behavior-driven damage and statuses remain unknown.
