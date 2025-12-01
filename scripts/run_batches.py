import argparse
import glob
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set

IGNORE_PATH = Path("ignore.json")
FILTERED_DIR = Path("work/fex_cache_filtered")


def load_effect_lines_filtered(name: str) -> List[str]:
    """Load pre-filtered effect lines from work/fex_cache_filtered if present."""
    path = FILTERED_DIR / f"{name.replace(' ', '_')}_filtered.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("effect_lines", []) or []
    except Exception:
        return []


ITEMS_INDEX = Path("work/items_index.json")
ITEMS_TODO = (
    Path("work/items_todo_filtered.json")
    if Path("work/items_todo_filtered.json").exists()
    else Path("work/items_todo.json")
)
FORMATTING_RULES = Path("formatting_rules.md")
BATCH_DIR = Path("work/prompts")
BATCH_DIR.mkdir(parents=True, exist_ok=True)
RESP_DIR = Path("work/responses")
RESP_DIR.mkdir(parents=True, exist_ok=True)


def load_processed_ids(glob_pattern: str) -> Set[int]:
    processed: Set[int] = set()
    for path in glob.glob(glob_pattern):
        try:
            data = json.load(open(path, encoding="utf-8"))
            for obj in data:
                if isinstance(obj, dict) and "id" in obj:
                    processed.add(int(obj["id"]))
        except Exception:
            continue
    return processed


def load_items(
    names_filter: List[str],
    limit: int,
    start: int,
    processed_ids: Set[int],
    category: Optional[str],
) -> List[Dict]:
    todo = json.load(ITEMS_TODO.open())
    # Category restriction first.
    if category:
        todo = [t for t in todo if t.get("category") == category]
    # Names restriction (if explicitly provided).
    if names_filter:
        names_lower = {n.lower() for n in names_filter}
        todo = [t for t in todo if t["name"].lower() in names_lower]
    # Respect ignore list (same as plan_batches).
    ignore_names = set()
    if IGNORE_PATH.exists():
        try:
            raw = json.load(IGNORE_PATH.open())
            for n in raw:
                s = str(n).strip()
                ignore_names.add(s)
                ignore_names.add(s.replace("_", " "))
                ignore_names.add(s.replace(" ", "_"))
        except Exception:
            pass
    todo = [
        t
        for t in todo
        if t["name"] not in ignore_names
        and t["name"].replace(" ", "_") not in ignore_names
    ]

    # Require a non-empty filtered effect_lines file (mirrors plan_batches).
    def has_filtered(item):
        fname = item["name"].replace(" ", "_") + "_filtered.json"
        path = FILTERED_DIR / fname
        if not path.exists():
            return False
        try:
            data = json.load(path.open(encoding="utf-8"))
            lines = data.get("effect_lines") or []
            return isinstance(lines, list) and any(
                isinstance(ln, str) and ln.strip() for ln in lines
            )
        except Exception:
            return False

    todo = [t for t in todo if has_filtered(t)]
    # Skip already processed ids.
    todo = [t for t in todo if int(t["id"]) not in processed_ids]
    if start:
        todo = todo[start:]
    if limit:
        todo = todo[:limit]
    return todo


def build_prompt(batch: List[Dict], rules_text: str, output_path: Path) -> str:
    lines = []
    lines.append(
        "You are updating Elden Ring item descriptions to match the 'Detailed Item Descriptions' mod style. Follow the formatting rules below exactly. Return JSON only, no prose."
    )
    lines.append(
        "Caption = lore-only; Info = lore (if not already in caption) + mechanics per rules. Keep them distinct."
    )
    lines.append(
        "Do not use placeholders; write final in-game text exactly as it should appear."
    )
    lines.append(
        "If effect info is missing/uncertain or shows placeholders (e.g., '??'), resolve it: first read the provided HTML effect lines; if still unclear, look up the correct values online before writing."
    )
    lines.append(
        "Do not include spoilers, quest/location guidance, acquisition steps, or patch notes—focus only on what the item does."
    )
    lines.append(f"Save the JSON array to this path: {output_path}")
    lines.append("Formatting rules:\n" + rules_text)
    lines.append(
        "For each item, produce JSON with: id, name, category, caption (lore-only), info (final description with formatting). Keep lore intact, put mechanics per rules."
    )
    for idx, item in enumerate(batch, 1):
        wiki_effects = load_effect_lines_filtered(item["name"])
        lines.append(f"Item {idx}:")
        lines.append(
            f"id: {item['id']}, name: {item['name']}, category: {item['category']}, bundle: {item['bundle']}"
        )
        lines.append("vanilla_caption:\n" + (item.get("vanilla_caption") or ""))
        lines.append("vanilla_info:\n" + (item.get("vanilla_info") or ""))
        lines.append("current_mod_caption:\n" + (item.get("mod_caption") or ""))
        lines.append("current_mod_info:\n" + (item.get("mod_info") or ""))
        lines.append(
            "wiki_effect_lines:\n" + json.dumps(wiki_effects, ensure_ascii=False)
        )
    lines.append(
        'Output JSON array, each object: {"id": int, "name": str, "category": str, "caption": str, "info": str}.'
    )
    lines.append("Do not include markdown fences.")
    return "\n\n".join(lines)


def extract_json_from_output(text: str) -> (Optional[str], Optional[object]):
    """Return the first JSON array snippet and parsed object if possible."""
    try:
        match = re.search(r"\[[\s\S]*?\]", text)
        if not match:
            return None, None
        snippet = match.group(0)
        return snippet, json.loads(snippet)
    except Exception:
        return snippet if "snippet" in locals() else None, None


def run_batch(
    batch: List[Dict],
    rules_text: str,
    batch_idx: int,
    execute: bool,
    model: str,
    config: Path,
    save_raw: bool,
    save_full: bool,
    prefix: str,
    output_dir: Path,
):
    base = f"{prefix}batch_{batch_idx:04d}" if prefix else f"batch_{batch_idx:04d}"
    prompt_file = BATCH_DIR / f"{base}_prompt.txt"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_file = output_dir / f"{base}_response_raw.txt"
    full_file = output_dir / f"{base}_response_full.txt"
    parsed_file = output_dir / f"{base}_response.json"
    prompt = build_prompt(batch, rules_text, parsed_file)
    prompt_file.write_text(prompt, encoding="utf-8")
    if not execute:
        print(f"[dry-run] wrote {prompt_file}")
        return
    cmd = [
        "codex-mcp-wrapper",
        "chat",
        prompt,
        "--config",
        str(config),
        "--transport",
        "streamable-http",
        "--port",
        "0",
        "--light",
        "--",
        "--model",
        model,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    combined = res.stdout + "\n" + res.stderr
    if save_full:
        full_file.write_text(combined, encoding="utf-8")
    snippet, parsed_obj = extract_json_from_output(combined)
    if save_raw:
        raw_file.write_text(snippet or "", encoding="utf-8")
    if parsed_obj is not None:
        parsed = parsed_obj
        parsed_file.write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"[run] batch {batch_idx} exit {res.returncode}, parsed JSON -> {parsed_file}"
        )
    else:
        if snippet:
            parsed_file.write_text(snippet, encoding="utf-8")
        else:
            parsed_file.write_text("null", encoding="utf-8")
        msg = f"[run] batch {batch_idx} exit {res.returncode}, no JSON parsed"
        if save_raw:
            msg += f" (see {raw_file})"
        if save_full:
            msg += f" (full {full_file})"
        print(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument(
        "--limit", type=int, default=2, help="total items to process (for testing)"
    )
    ap.add_argument("--names", nargs="*", help="specific item names to process")
    ap.add_argument(
        "--execute", action="store_true", help="actually call codex-mcp-wrapper chat"
    )
    ap.add_argument("--model", default="gpt-5.1-codex-max")
    ap.add_argument("--config", default="../codex-mcp-wrapper/wrapper.toml")
    ap.add_argument(
        "--save-raw", action="store_true", help="save extracted JSON snippet"
    )
    ap.add_argument("--save-full", action="store_true", help="save full CLI output")
    ap.add_argument(
        "--start",
        type=int,
        default=0,
        help="offset into todo list after filtering processed",
    )
    ap.add_argument(
        "--processed-glob",
        default="work/responses/ready/*_response*.json",
        help="glob of already processed response files to skip ids",
    )
    ap.add_argument(
        "--batch-prefix",
        default="",
        help="prefix for batch output files to avoid collisions",
    )
    ap.add_argument(
        "--category",
        help="restrict to category (armor, talisman, weapon, spell, skill, ash, consumable)",
    )
    ap.add_argument(
        "--output-dir",
        default="work/responses/pending",
        help="directory for responses (parsed/raw/full)",
    )
    args = ap.parse_args()

    rules_text = FORMATTING_RULES.read_text(encoding="utf-8")
    processed_ids = (
        load_processed_ids(args.processed_glob) if args.processed_glob else set()
    )
    items = load_items(
        args.names or [], args.limit, args.start, processed_ids, args.category
    )

    batch_idx = 0
    for i in range(0, len(items), args.batch_size):
        batch = items[i : i + args.batch_size]
        if not batch:
            continue
        batch_idx += 1
        run_batch(
            batch,
            rules_text,
            batch_idx,
            args.execute,
            args.model,
            Path(args.config),
            args.save_raw,
            args.save_full,
            args.batch_prefix,
            Path(args.output_dir),
        )

    print(f"Prepared {batch_idx} batches")


if __name__ == "__main__":
    main()
