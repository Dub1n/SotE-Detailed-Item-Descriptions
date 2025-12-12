import argparse
import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
MD_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-5.md"
INPUT_JSON_DEFAULT = ROOT / "work/responses/skill.json"
OUTPUT_JSON_DEFAULT = ROOT / "work/responses/ready/skill.json"


def load_md_blocks(path: Path) -> Dict[str, str]:
    """
    Parse the AoW-data-5 markdown into a mapping of skill name -> formatted text
    without the leading "### {skill}" header.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: Dict[str, List[str]] = {}
    current_skill: str | None = None
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer, current_skill
        if current_skill is None:
            return
        # Trim leading/trailing blank lines.
        while buffer and not buffer[0].strip():
            buffer.pop(0)
        while buffer and not buffer[-1].strip():
            buffer.pop()
        blocks[current_skill] = "\n".join(buffer)
        buffer = []

    for line in lines:
        if line.startswith("### "):
            flush()
            current_skill = line[4:].strip()
            buffer = []
            continue
        buffer.append(line)
    flush()
    return blocks


def merge_info(existing: str, extra: str) -> str:
    existing = (existing or "").rstrip()
    extra = extra.rstrip()
    if not existing:
        return extra
    return f"{existing}\n\n{extra}"


def apply_md_to_ready(
    md_blocks: Dict[str, str], ready_entries: List[Dict[str, str]]
) -> int:
    updated = 0
    for entry in ready_entries:
        name = entry.get("name")
        if not name or name not in md_blocks:
            continue
        entry["info"] = merge_info(entry.get("info", ""), md_blocks[name])
        updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 6: append AoW-data-5 markdown into ready skill info."
    )
    parser.add_argument(
        "--md",
        type=Path,
        default=MD_DEFAULT,
        help="Path to AoW-data-5.md",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_JSON_DEFAULT,
        help="Path to source skill.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_JSON_DEFAULT,
        help="Path to write ready/skill.json",
    )
    args = parser.parse_args()

    md_blocks = load_md_blocks(args.md)
    ready_entries = json.loads(args.input.read_text(encoding="utf-8"))

    updated_count = apply_md_to_ready(md_blocks, ready_entries)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(ready_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Appended markdown stats to {updated_count} skill(s); "
        f"wrote output to {args.output}"
    )


if __name__ == "__main__":
    main()
