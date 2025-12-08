# Repository Guidelines

## Project Structure & Key Paths

- **docs/aow_pipeline_overview.md**: End-to-end CSV pipeline plan and diagrams.
- **docs/skill_names_from_gem_and_behavior.txt**: Stage 0 output (canonical skill list).
- **docs/AoW-data-1_example.csv**: Authoritative sample rows for reference.
- **scripts/build_aow/**: Stage scripts (`build_aow_stage0.py`, `build_aow_stage1.py`, `build_aow_stage2.py`; Stage 3 placeholder).
- **work/aow_pipeline/**: Generated CSV stages (`AoW-data-1.csv`, `AoW-data-2.csv`, `AoW-data-3.csv` placeholder).
- **PARAM/**: Extracted param CSVs used by the pipeline (EquipParamGem, EquipParamWeapon, BehaviorParam_PC, SwordArtsParam).
- **docs/(1.16.1)-*.csv**, **docs/weapon_categories_poise.json**: Source CSVs/lookup JSON for Stage 1.
- **msg/mod/real_dlc/vanilla/**: FMG sources and comparisons (unchanged by the CSV pipeline).

## Build, Test, and Development Commands

- Create venv: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`.
- Stage 0: `.venv/bin/python scripts/build_aow/build_aow_stage0.py`.
- Stage 1: `.venv/bin/python scripts/build_aow/build_aow_stage1.py` (outputs `work/aow_pipeline/AoW-data-1.csv`).
- Stage 2: `.venv/bin/python scripts/build_aow/build_aow_stage2.py` (outputs `work/aow_pipeline/AoW-data-2.csv`; Stage 3 is pass-through today).
- Regenerate in order when upstream CSVs change; see `docs/aow_pipeline_overview.md` for details.

## Coding Style & Naming

- Python scripts; keep formatting conventional (PEP8-ish, 4-space indent). JSON is pretty-printed with `indent=2`, UTF-8, ASCII font tags preserved.
- Paths and filenames use lowercase with underscores; category files are suffixed or prefixed clearly (e.g., `consumable_Sorcery.json`).

## Testing & Validation

- No automated test suite. Validate by rerunning the CSV stages and diffing outputs; sanity-check counts and sample rows against `docs/AoW-data-1_example.csv`.
- Verify Stage 2 outputs parse and that derived fields (Wep Poise Range, Stance Dmg, Dmg Type/MV) look sane for spot-checked skills; compare shapes against `skill.json` expectations when iterating toward the final format.

## CSV skill pipeline (new)

- We now generate skill data via an explicit CSV pipeline instead of ad-hoc parsing. Stages live in `scripts/build_aow/`:
  - Stage 0: `build_aow_stage0.py` unions skill names from Gem/Behavior/SwordArts into `docs/skill_names_from_gem_and_behavior.txt`.
  - Stage 1: `build_aow_stage1.py` collates attack data + poise/category/weapon refs into `work/aow_pipeline/AoW-data-1.csv` (labels, weapon resolution, poise bases, base stats).
  - Stage 2: `build_aow_stage2.py` groups/sums, collapses poise ranges, derives stance damage and damage type/MV into `work/aow_pipeline/AoW-data-2.csv`. Stage 3 is currently a pass-through.
- The end goal is to drive `skill.json` population from these CSV stages. Format should align with `skill.json` structure, but values may differ while we correct parsing/understanding gaps. Use the docs (`docs/aow_pipeline_overview.md`) for per-column lineage and regeneration steps; do not hand-edit outputs.

## Commit & PR Guidelines

- Keep commits scoped and descriptive (e.g., "Add subcategory splits for consumables" rather than generic messages). Include a short summary of scripts run when relevant.
- PRs: describe scope, note affected folders (`work/`, `descriptions-*`, `PARAM/`), and call out any manual steps or data regeneration needed.

## Agent Tips

- Never overwrite user data in `ready/` or FMG sources; archive before batch runs.
- Respect `use:false` flags and scope rules (DLC1 + allowed base list). Avoid editing `.gfx` unless explicitly requested.
