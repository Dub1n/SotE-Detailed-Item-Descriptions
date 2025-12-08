import argparse
import csv
import os
import re
import signal
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = ROOT / "work" / "aow_pipeline"
HELPERS_DIR = ROOT / "scripts"
if str(HELPERS_DIR) not in sys.path:
    sys.path.append(str(HELPERS_DIR))

from helpers.output import format_path_for_console  # noqa: E402

CSV_PATTERN = re.compile(r"AoW-data-(\d+)\.csv$", re.IGNORECASE)
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    # Not all platforms expose SIGPIPE.
    pass


def safe_print(text: str) -> None:
    try:
        print(text)
    except BrokenPipeError:
        os._exit(0)


def normalize_columns(raw: Iterable[Sequence[str] | str]) -> List[str]:
    """
    Normalize a list of column strings into a de-duplicated, ordered list.
    Supports comma-separated values passed to --ignore, and multi-word
    values provided as separate tokens (e.g., --ignore Dmg Type).
    """
    columns: List[str] = []
    for item in raw:
        if not item:
            continue
        text = item
        if isinstance(item, (list, tuple)):
            text = " ".join(item)
        for part in str(text).split(","):
            col = part.strip()
            if col and col not in columns:
                columns.append(col)
    return columns


def find_latest_csv(directory: Path) -> Path | None:
    """Return the AoW-data-*.csv with the highest numeric suffix."""
    latest: Tuple[int, Path] | None = None
    for path in directory.glob("AoW-data-*.csv"):
        match = CSV_PATTERN.search(path.name)
        if not match:
            continue
        idx = int(match.group(1))
        if not latest or idx > latest[0]:
            latest = (idx, path)
    return latest[1] if latest else None


def load_counts(
    path: Path, key_fields: List[str]
) -> Tuple[Dict[Tuple[str, ...], int], Dict[Tuple[str, ...], int]]:
    counts: Dict[Tuple[str, ...], int] = defaultdict(int)
    first_seen: Dict[Tuple[str, ...], int] = {}
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [col for col in key_fields if col not in fieldnames]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(
                f"Input CSV must contain required columns: {missing_text}"
            )
        for line_no, row in enumerate(reader, start=2):
            key: List[str] = []
            for col in key_fields:
                key.append((row.get(col) or "").strip() or "-")
            counts[tuple(key)] += 1
            if tuple(key) not in first_seen:
                first_seen[tuple(key)] = line_no
    return counts, first_seen


def duplicate_groups(
    counts: Dict[Tuple[str, ...], int],
    first_seen: Dict[Tuple[str, ...], int],
) -> List[Tuple[Tuple[str, ...], int, int]]:
    dupes: List[Tuple[Tuple[str, ...], int, int]] = []
    for key, count in counts.items():
        if count > 1:
            dupes.append((key, count, first_seen.get(key, 0)))
    dupes.sort(
        key=lambda item: (
            -item[1],
            item[2] or 0,
            tuple(part.lower() for part in item[0]),
        )
    )
    return dupes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Report combinations of Skill/Part (plus any --ignore columns) "
            "that appear more than once in the latest AoW-data CSV."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        help=(
            "Explicit AoW-data-*.csv to scan. "
            "Defaults to the highest stage in work/aow_pipeline."
        ),
    )
    parser.add_argument(
        "--ignore",
        action="append",
        nargs="+",
        default=[],
        help=(
            "Require duplicates to also match this column. "
            "Repeatable, supports multi-word columns, and accepts comma-separated "
            "lists (e.g., --ignore \"Dmg Type\" --ignore Weapon,Hand)."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all match columns in the output and print match column list.",
    )
    args = parser.parse_args()

    input_path = args.input
    if input_path:
        if not input_path.exists():
            parser.error(f"Input file does not exist: {input_path}")
    else:
        input_path = find_latest_csv(WORK_DIR)
        if not input_path:
            print(f"No AoW-data-*.csv files found in {WORK_DIR}")
            sys.exit(1)

    extra_fields = normalize_columns(args.ignore)
    key_fields = ["Skill", "Part"]
    for field in extra_fields:
        if field not in key_fields:
            key_fields.append(field)

    counts, first_seen = load_counts(input_path, key_fields)
    duplicates = duplicate_groups(counts, first_seen)
    path_text = format_path_for_console(input_path, ROOT)
    match_cols = " | ".join(key_fields)
    if args.verbose:
        safe_print(f"Scanning {path_text} (match columns: {match_cols})")
    else:
        safe_print(f"Scanning {path_text}")

    if not duplicates:
        safe_print("No duplicate groups found.")
        return

    line_width = len(str(max((line for *_ , line in duplicates), default=0))) or 1
    for key_parts, count, line_no in duplicates:
        if args.verbose:
            label = " | ".join(key_parts)
        else:
            label = " | ".join(key_parts[:2])
        line_text = str(line_no).rjust(line_width) if line_no else " " * line_width
        safe_print(f"{line_text} {label}: {count}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Allow piping to head/grep without a noisy traceback.
        try:
            sys.stdout.close()
        except Exception:
            pass
        os._exit(0)
