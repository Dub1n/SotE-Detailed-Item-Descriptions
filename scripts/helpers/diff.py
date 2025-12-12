import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple, List, Optional, DefaultDict


def load_rows_by_key(
    path: Path, key_fields: Sequence[str]
) -> Dict[Tuple[str, ...], List[Dict[str, str]]]:
    if not path.exists():
        return {}
    rows_by_key: DefaultDict[Tuple[str, ...], List[Dict[str, str]]] = defaultdict(list)
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = tuple(row.get(field, "") for field in key_fields)
            rows_by_key[key].append(row)
    return dict(rows_by_key)


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
    before_rows: Dict[Tuple[str, ...], List[Mapping[str, str]]],
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

    def row_tuple(row: Mapping[str, str]) -> Tuple[str, ...]:
        return tuple(str(row.get(col, "")) for col in fieldnames)

    after_map: DefaultDict[Tuple[str, ...], List[Mapping[str, str]]] = defaultdict(list)
    for row in after_rows:
        key = tuple(row.get(field, "") for field in key_fields)
        after_map[key].append(row)

    added_entries: List[Tuple[Tuple[str, ...], int]] = []
    removed_entries: List[Tuple[Tuple[str, ...], int]] = []
    changed_keys: List[Tuple[str, ...]] = []

    all_keys = set(before_rows) | set(after_map)
    for key in all_keys:
        before_list = before_rows.get(key, [])
        after_list = after_map.get(key, [])
        if not before_list and after_list:
            added_entries.append((key, len(after_list)))
            continue
        if before_list and not after_list:
            removed_entries.append((key, len(before_list)))
            continue

        before_counter = Counter(row_tuple(r) for r in before_list)
        after_counter = Counter(row_tuple(r) for r in after_list)
        if before_counter == after_counter:
            continue
        delta_added = sum((after_counter - before_counter).values())
        delta_removed = sum((before_counter - after_counter).values())
        if delta_added:
            added_entries.append((key, delta_added))
        if delta_removed:
            removed_entries.append((key, delta_removed))
        changed_keys.append(key)

    widths: Optional[List[int]] = None
    key_lists = (
        [k for k, _ in added_entries]
        + [k for k, _ in removed_entries]
        + changed_keys
    )
    if align_columns and key_lists:
        max_len = max(len(k) for k in key_lists)
        widths = [0] * max_len
        for key in key_lists:
            for idx in range(max_len):
                part = key[idx] if idx < len(key) else ""
                widths[idx] = max(widths[idx], len(part))

    def _format_entry(entry: Tuple[Tuple[str, ...], int]) -> str:
        key, count = entry
        label = _format_key(key, widths)
        return f"{label} (x{count})" if count > 1 else label

    added = [_format_entry(e) for e in added_entries]
    removed = [_format_entry(e) for e in removed_entries]
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
