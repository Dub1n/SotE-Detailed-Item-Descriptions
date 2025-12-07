# AoW CSV Pipeline

This approach makes the skill data flow deterministic, debuggable, and repeatable by producing explicit on-disk CSV stages instead of doing ad-hoc, in-memory munging.

## Intent
- Collate all AoW rows we need into a single, minimal CSV with only the columns we care about.
- Resolve weapon/poise data deterministically: prefer per-weapon bases when they exist, otherwise fall back to category poise via mount flags.
- Keep every stage reproducible via scripts so we can regenerate when upstream CSVs change.
- Future stages stay pass-through until we design their transforms; this keeps the pipeline shape stable while we iterate.

## Stage 1: Build `AoW-data-1.csv`
- Inputs:
  - `docs/(1.16.1)-Ashes-of-War-Attack-Data.csv` (source rows; uses `Unique Skill Weapon` when present).
  - `docs/(1.16.1)-Poise-Damage-MVs.csv` (weapon-specific `Base` poise for unique weapons).
  - `PARAM/EquipParamGem.csv` (mount flags → weapon categories for non-unique skills).
  - `docs/weapon_categories_poise.json` (category → display name + poise).
  - `docs/skill_names_from_gem.txt` (canonical skill list, longest-first matching).
- Output: `work/aow_pipeline/AoW-data-1.csv` (collated rows; no value transforms beyond lightweight labeling).
- Column shape (initial): `Skill`, `Weapon`, `Weapon Poise`, `Weapon Source`, `FP`, `Charged`, `Part`, `Follow-up`, `Hand`, `Step`, `Bullet`, `Name`, `AtkId`, `Phys MV`, `Magic MV`, `Fire MV`, `Ltng MV`, `Holy MV`, `Status MV`, `Weapon Buff MV`, `Poise Dmg MV`, `PhysAtkAttribute`, `AtkPhys`, `AtkMag`, `AtkFire`, `AtkLtng`, `AtkHoly`, `AtkSuperArmor`, `isAddBaseAtk`, `overwriteAttackElementCorrectId`, `Overwrite Scaling`, `subCategory1`, `subCategory2`, `subCategory3`, `subCategory4`, `spEffectId0`, `spEffectId1`, `spEffectId2`, `spEffectId3`, `spEffectId4`.
- Resolution rules:
  - `Weapon`: if `Unique Skill Weapon` is populated, use it directly; else if the row name carries a `[Weapon Type]` prefix, use only that category unless the prefix is in the ignored list (`Slow`, `Var1`, `Var2`), in which case use the category mapping; otherwise, map the skill name to `EquipParamGem` mount flags **that have a valid `mountWepTextId` (not -1)** and emit the human-readable category names (space-separated).
  - `Weapon Poise`: if a unique weapon is present, read its `Base` from `Poise-Damage-MVs` (with category fallback when needed); if a bracketed weapon prefix is present, look up that category’s base poise; otherwise, emit category poise values from `weapon_categories_poise.json` aligned with the `Weapon` list.
  - `FP`: `0` when the name contains `(Lacking FP)`, else `1`.
  - `Charged`: `1` when the name contains `Charged`, else `0`.
  - `Part`: inferred from name tokens without charged/hand/follow-up labels; removes `Bullet` and strips outer parentheses when the whole part is wrapped. Defaults to `Main`, with `Loop` preserved when present.
  - `Follow-up`: `Light` when the name contains `R1`, `Heavy` when it contains `R2`, else `-`.
  - `Hand`: detects `1h`/`2h` in the name, otherwise `-`.
  - `Step`: number after `#` in the name; defaults to `1` when absent.
  - `Bullet`: `1` when the name contains `Bullet`, else `0`.

```mermaid
flowchart TD
  A[Attack data\n(1.16.1)-Ashes-of-War-Attack-Data.csv\nincludes Unique Skill Weapon] --> D[Build AoW-data-1]
  B[Poise MVs\n(1.16.1)-Poise-Damage-MVs.csv\nBase per weapon/class] --> D
  C[EquipParamGem.csv\nmount flags] --> D
  E[weapon_categories_poise.json\ncategory -> name + poise] --> D
  D --> F[work/aow_pipeline/AoW-data-1.csv\ncollated + labeled rows]
```

## Stage 2 (placeholder): Normalize/augment (identity for now)
- Input: `work/aow_pipeline/AoW-data-1.csv`
- Output: `work/aow_pipeline/AoW-data-2.csv` (currently identical to Stage 1; will host future normalizations/handedness merges).

```mermaid
flowchart TD
  A[work/aow_pipeline/AoW-data-1.csv] --> B[Stage 2 (pending)\nidentity pass-through] --> C[work/aow_pipeline/AoW-data-2.csv]
```

## Stage 3 (placeholder): Final shaping for downstream
- Input: `work/aow_pipeline/AoW-data-2.csv`
- Output: `work/aow_pipeline/AoW-data-3.csv` (currently identical to Stage 2; future spot for formatting ready/JSON ingest).

```mermaid
flowchart TD
  A[work/aow_pipeline/AoW-data-2.csv] --> B[Stage 3 (pending)\nidentity pass-through] --> C[work/aow_pipeline/AoW-data-3.csv]
```

## Filesystem layout
- `docs/aow_pipeline_overview.md` (this plan).
- `docs/AoW-data-1_example.csv` (authoritative sample rows for reference).
- `docs/skill_names_from_gem_and_behavior.txt` (canonical skill names derived from EquipParamGem + Behavior).
- `work/aow_pipeline/AoW-data-1.csv` (generated Stage 1 output).
- `work/aow_pipeline/` (workspace for outputs and scratch; add temp files as needed).
- `scripts/build_aow_stage1.py` (rebuild script).

## How to regenerate Stage 1
```sh
python scripts/build_aow_stage1.py
# optional: choose another output
python scripts/build_aow_stage1.py --output work/aow_pipeline/custom.csv
```

Regenerate whenever upstream CSVs change. The script reports any skills missing mount categories or poise lookups so we can patch inputs instead of silently guessing.
