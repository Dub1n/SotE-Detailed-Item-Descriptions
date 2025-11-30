# SotE Better Item Descriptions

This workspace automates updating Elden Ring item descriptions (DLC1 + selected base-game items) into the "Detailed Item Descriptions" style. It handles scraping wiki effects, batching LLM rewrites, salvaging outputs, and applying them into FMG XMLs.

## Current Scope & Data

- **Allowed items**: DLC1 (`item_dlc01`) and base-game items explicitly listed in `basegame_items.yaml` (post-1.09 patch updates). Everything else is out of scope and marked `use:false`.
- **Language**: engUS only.
- **Style**: See `formatting_rules.md`, `brief.md`, `instructions.md` for colour codes, structure, and mechanical/lore split.

## Key Folders

- `work/items_index.json`: Parsed FMG index (name/id/category/bundle/texts) from mod FMG XMLs.
- `work/items_todo_filtered.json`: Current todo list (allowed items only).
- `work/responses/ready/`: Parsed JSON outputs (LLM results). Entries can have `"use": false` to skip applying.
- `work/responses/pending/`: Raw/partial outputs from the latest run; should be empty before new runs. Salvage and move valid JSON to `ready/`.
- `work/responses/archive/`: Archived pending artifacts per timestamp.
- `work/prompts/`: Batch prompts used for Codex runs.
- `work/responses/done_ids.json`: IDs present in `ready/` (regardless of `use`). Used to skip already-processed items.
- `work/fex_cache/`: Cached Fextralife HTML.
- `temp/scrape/`, `temp/scrape_filtered/`: Example HTML and extracted effect_lines for inspection.

## Scripts Overview

- **Indexing & Filters**
  - `scripts/build_index.py`: Build `items_index.json` and initial todo.
  - `scripts/restrict_items.py`: Apply allowed set (DLC1 + base list). Sets `use:true` for base list, removes `use` for DLC1, sets `use:false` otherwise. Rewrites `items_todo_filtered.json` and updates ready files.
  - `scripts/filter_todo.py`: Legacy non-null filter (not used now).
- **Wiki Scrape**
  - `scripts/fextralife_scrape.py`: Extract `effect_lines` from cached or live Fex pages. Supports `--dir/--file` to process HTML into `_filtered.json`.
- **Batch Generation & Runs**
  - `scripts/plan_batches.py`: Create `work/batch_plan.json` (chunk size 15) from `items_todo_filtered.json` skipping IDs already in `ready/` (by default uses `work/responses/ready/*_response.json`).
  - `scripts/run_batches.py`: Build prompts (includes formatting rules, vanilla/mod text, effect_lines, output path) and call `codex-mcp-wrapper chat`. Default model `gpt-5.1-codex-mini`, outputs to `work/responses/pending/`, prompts to `work/prompts/`. Supports `--category`, `--start`, `--batch-prefix`, `--processed-glob`.
  - `scripts/run_plan.py`: Execute `batch_plan.json` with configurable concurrency (default 5). Skips IDs found in ready via processed-glob.
- **Cleanup & Salvage**
  - `scripts/clean_pending.py`: Heuristically fix/truncate malformed pending JSON and move to `ready/` (deletes pending file).
  - `scripts/archive_pending.py`: Move everything in `pending/` to `archive/<timestamp>/`.
- **Apply to FMGs**
  - `scripts/apply_responses.py`: Copy bundles to `build/msg/engus/` and patch caption/info. Skips items with `"use": false`.

## How to Run Batches (Typical Loop)

1. **Prep**: Ensure `pending/` is empty (run `archive_pending.py`).
2. **Plan**: `./venv/bin/python scripts/plan_batches.py` (uses `items_todo_filtered.json`, skips ready IDs).
3. **Run**: (long-running) e.g.

   ```bash
   nohup .venv/bin/python scripts/run_plan.py \
     --concurrency 5 \
     --output-dir work/responses/pending \
     --model gpt-5.1-codex-mini \
     --config ../codex-mcp-wrapper/wrapper.toml \
     > work/run_all.log 2>&1 & echo $! > work/run_all.pid
   ```

   Monitor: `tail -f work/run_all.log`.
4. **Salvage**: Run `scripts/clean_pending.py` to fix partial JSON and move to `ready/`. Archive leftovers (`scripts/archive_pending.py`).
5. **Restrict/Use Flags**: `scripts/restrict_items.py` to enforce allowed set and `use` flags.
6. **Recompute done_ids/plan**: rerun `plan_batches.py`; repeat loop until `plan` empty.
7. **Apply**: `./venv/bin/python scripts/apply_responses.py work/responses/ready/*.json` to write into `build/` FMG XMLs (honors `use:false`).

## Use Flag Semantics

- `use:true`: apply this item.
- `use:false`: skip this item (out of scope or bad content). Treated as “done” for batching, ignored when applying.
- Absent: default apply (DLC1 items).

## ADR Notes (informal)

- **Batching**: Chunk size 15 with `gpt-5.1-codex-mini` for cost; parallel 5. Salvage/cleanup handles truncations/partials. For stubborn items, switch to full `gpt-5.1-codex`.
- **Scope**: Only DLC1 + basegame patch list (`basegame_items.yaml`). Everything else is `use:false` and ignored.
- **Scrape**: We use extracted effect lines (not full HTML) via `fextralife_scrape.py`. Cached HTML lives in `work/fex_cache/`.
- **Apply**: Use flags honored; only `use!=false` entries overwrite FMG XMLs. Builds go to `build/msg/engus/` leaving originals untouched.

## Current Status (as of this README)

- Ready: 88 files; 1,258 IDs present, but only those with `use != false` will apply (check `use` flags in ready files).
- Plan: 320 chunks remaining (chunk=15) after latest restriction and salvage.
- Pending: empty (after cleaning/archiving).

## Quick Commands

- Regenerate plan: `./venv/bin/python scripts/plan_batches.py`
- Run plan: see “Run” command above.
- Salvage pending: `./venv/bin/python scripts/clean_pending.py`
- Archive pending: `./venv/bin/python scripts/archive_pending.py`
- Enforce scope/use flags: `./venv/bin/python scripts/restrict_items.py`
- Apply to FMGs: `./venv/bin/python scripts/apply_responses.py work/responses/ready/*.json`

## References

- Style/spec: `formatting_rules.md`, `brief.md`, `instructions.md`.
- Base item list: `basegame_items.yaml`.
- Cached wiki HTML: `work/fex_cache/`; filtered examples: `temp/scrape_filtered/`.
