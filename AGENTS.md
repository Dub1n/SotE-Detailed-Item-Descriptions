# Repository Guidelines

## Project Structure & Key Paths

- **work/**: LLM workflow artifacts. `responses/ready/` holds cleaned JSON outputs per category; `responses/pending/` is for raw batches; `prompts/` stores generated prompts; `items_index.json` and `items_todo_filtered.json` drive batching.
- **scripts/**: CLI tooling for planning, running, salvaging batches, restricting scope, and applying to FMGs.
- **msg/mod/real_dlc/vanilla/**: Source FMG XMLs and comparisons; `PARAM/` contains extracted param CSVs (EquipParam*).
- **descriptions-*/**: Derived JSON bundles: `mod`, `delta`, `comparison`, `vanilla`. Split consumable files live alongside combined `consumable.json`.

## Build, Test, and Development Commands

- Create venv: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` (pip-only project; no build step).
- Plan batches: `.venv/bin/python scripts/plan_batches.py`.
- Run batches: `.venv/bin/python scripts/run_plan.py --concurrency 5 --output-dir work/responses/pending --model gpt-5.1-codex-mini`.
- Salvage pending: `.venv/bin/python scripts/clean_pending.py`; archive: `scripts/archive_pending.py`.
- Apply to FMGs: `.venv/bin/python scripts/apply_responses.py work/responses/ready/*.json` (honors `use:false`).

## Coding Style & Naming

- Python scripts; keep formatting conventional (PEP8-ish, 4-space indent). JSON is pretty-printed with `indent=2`, UTF-8, ASCII font tags preserved.
- Paths and filenames use lowercase with underscores; category files are suffixed or prefixed clearly (e.g., `consumable_Sorcery.json`).

## Testing & Validation

- No automated test suite. Validate by: ensuring `pending/` is empty before new runs, verifying ready JSON parses, and spot-checking applied FMGs in `build/msg/engus/`.
- For data transforms, re-run the script and diff outputs; sanity-check counts (e.g., subcategory splits) and sample entries.

## Commit & PR Guidelines

- Keep commits scoped and descriptive (e.g., "Add subcategory splits for consumables" rather than generic messages). Include a short summary of scripts run when relevant.
- PRs: describe scope, note affected folders (`work/`, `descriptions-*`, `PARAM/`), and call out any manual steps or data regeneration needed.

## Agent Tips

- Never overwrite user data in `ready/` or FMG sources; archive before batch runs.
- Respect `use:false` flags and scope rules (DLC1 + allowed base list). Avoid editing `.gfx` unless explicitly requested.
