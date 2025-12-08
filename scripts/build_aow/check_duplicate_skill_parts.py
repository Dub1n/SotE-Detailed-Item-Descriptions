import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = ROOT / "work" / "aow_pipeline"
HELPERS_DIR = ROOT / "scripts"
if str(HELPERS_DIR) not in sys.path:
    sys.path.append(str(HELPERS_DIR))

from helpers.output import format_path_for_console  # noqa: E402

CSV_PATTERN = re.compile(r"AoW-data-(\d+)\.csv$", re.IGNORECASE)


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


def load_counts(path: Path) -> Dict[Tuple[str, str], int]:
    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if "Skill" not in fieldnames or "Part" not in fieldnames:
            raise ValueError("Input CSV must contain Skill and Part columns.")
        for row in reader:
            skill = (row.get("Skill") or "").strip() or "-"
            part = (row.get("Part") or "").strip() or "-"
            counts[(skill, part)] += 1
    return counts


def duplicate_groups(counts: Dict[Tuple[str, str], int]) -> List[Tuple[str, str, int]]:
    dupes: List[Tuple[str, str, int]] = []
    for (skill, part), count in counts.items():
        if count > 1:
            dupes.append((skill, part, count))
    dupes.sort(key=lambda item: (-item[2], item[0].lower(), item[1].lower()))
    return dupes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Report Skill/Part combinations that appear more than once "
            "in the latest AoW-data CSV."
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

    counts = load_counts(input_path)
    duplicates = duplicate_groups(counts)
    path_text = format_path_for_console(input_path, ROOT)
    print(f"Scanning {path_text}")

    if not duplicates:
        print("No duplicate Skill/Part groups found.")
        return

    for skill, part, count in duplicates:
        print(f"{skill} | {part}: {count}")


if __name__ == "__main__":
    main()
