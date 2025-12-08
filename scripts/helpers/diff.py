import csv
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple, List, Optional


def load_rows_by_key(
    path: Path, key_fields: Sequence[str]
) -> Dict[Tuple[str, ...], Dict[str, str]]:
    if not path.exists():
        return {}
    with path.open() as f:
        reader = csv.DictReader(f)
        rows = {
            tuple(row.get(field, "") for field in key_fields): row
            for row in reader
        }
    return rows


def _format_key(
    key: Tuple[str, ...], widths: Optional[List[int]] = None
) -> str:
    parts = [part or "" for part in key]
    if widths:
        padded: List[str] = []
        for idx, part in enumerate(parts):
            width = widths[idx] if idx < len(widths) else len(part)
            padded.append(part.ljust(width))
        return " | ".join(padded).rstrip()
    text = " | ".join([part for part in parts if part != ""]).strip()
    return text or "<empty>"


def report_row_deltas(
    before_rows: Dict[Tuple[str, ...], Mapping[str, str]],
    after_rows: Iterable[Mapping[str, str]],
    fieldnames: Iterable[str],
    key_fields: Sequence[str],
    *,
    label: str = "Row",
    max_list: int = 50,
    printer=print,
    align_columns: bool = False,
) -> None:
    """
    Compare two sets of rows keyed by key_fields, printing delta summary.
    Matches the existing Stage 1 output format (Row deltas: ...).
    """
    if not before_rows:
        return

    after_map: Dict[Tuple[str, ...], Mapping[str, str]] = {}
    for row in after_rows:
        key = tuple(row.get(field, "") for field in key_fields)
        after_map[key] = row

    added_keys = [key for key in after_map if key not in before_rows]
    removed_keys = [key for key in before_rows if key not in after_map]
    changed_keys: List[Tuple[str, ...]] = []

    for key, prev in before_rows.items():
        if key not in after_map:
            continue
        curr = after_map[key]
        if any(
            str(prev.get(col, "")) != str(curr.get(col, ""))
            for col in fieldnames
        ):
            changed_keys.append(key)

    widths: Optional[List[int]] = None
    if align_columns and (added_keys or removed_keys or changed_keys):
        max_len = max(len(k) for k in added_keys + removed_keys + changed_keys)
        widths = [0] * max_len
        for key in added_keys + removed_keys + changed_keys:
            for idx in range(max_len):
                part = key[idx] if idx < len(key) else ""
                widths[idx] = max(widths[idx], len(part))

    added = [_format_key(k, widths) for k in added_keys]
    removed = [_format_key(k, widths) for k in removed_keys]
    changed = [_format_key(k, widths) for k in changed_keys]

    total_diff = len(added) + len(removed) + len(changed)
    if total_diff:
        printer(
            f"{label} deltas: added="
            f"{len(added)}, removed={len(removed)}, changed={len(changed)}"
        )
        if total_diff <= max_list:
            if added:
                printer("  Added:")
                for n in sorted(added):
                    printer(f"    - {n}")
            if removed:
                printer("  Removed:")
                for n in sorted(removed):
                    printer(f"    - {n}")
            if changed:
                printer("  Changed:")
                for n in sorted(changed):
                    printer(f"    - {n}")
    else:
        printer("No row content changes detected.")
