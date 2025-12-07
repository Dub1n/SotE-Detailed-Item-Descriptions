#!/usr/bin/env python3
"""Compare snapshot skill stats to generated stats, ignoring block and weapon ordering."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a flattened skill snapshot to a generated stats file, ignoring block order and weapon order."
    )
    parser.add_argument(
        "--snapshot",
        default="dev/debug/skills_snapshot.json",
        help="Path to flattened snapshot (list of {name, stats, weapon}).",
    )
    parser.add_argument(
        "--target",
        default="work/skill_stats_from_sheet.json",
        help="Path to generated stats file to compare against.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write a JSON diff report (per-skill missing/extra blocks).",
    )
    return parser.parse_args()


def load_entries(path: Path) -> List[Dict[str, object]]:
    with path.open() as f:
        data = json.load(f)
    entries: List[Dict[str, object]] = []
    for entry in data:
        if isinstance(entry, dict) and "name" in entry:
            entries.append(entry)
    return entries


def normalize_weapons(entry: Dict[str, object]) -> Tuple[str, ...]:
    weapons = entry.get("weapon") or []
    if isinstance(weapons, str):
        weapons = [weapons]
    return tuple(sorted(w for w in weapons if w))


def canonical_block(entry: Dict[str, object]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    stats = entry.get("stats") or []
    stats_tuple = tuple(stats) if isinstance(stats, list) else (str(stats),)
    weapons_tuple = normalize_weapons(entry)
    return (stats_tuple, weapons_tuple)


def stats_multiset(entry: Dict[str, object]) -> Counter:
    stats = entry.get("stats") or []
    if not isinstance(stats, list):
        stats = [str(stats)]
    return Counter(stats)


def compare_skills(
    snapshot_entries: List[Dict[str, object]], target_entries: List[Dict[str, object]]
) -> Dict[str, Dict[str, object]]:
    snap_map: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for entry in snapshot_entries:
        snap_map[entry["name"]].append(entry)

    tgt_map: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for entry in target_entries:
        tgt_map[entry["name"]].append(entry)

    report: Dict[str, Dict[str, object]] = {}

    for name, snap_blocks in snap_map.items():
        tgt_blocks = list(tgt_map.get(name, []))

        # Step 1: exact matches (stats order + weapons)
        snap_remaining = []
        exact_matches = 0
        tgt_used = [False] * len(tgt_blocks)
        for snap in snap_blocks:
            found = False
            canon = canonical_block(snap)
            for idx, tgt in enumerate(tgt_blocks):
                if tgt_used[idx]:
                    continue
                if canonical_block(tgt) == canon:
                    tgt_used[idx] = True
                    exact_matches += 1
                    found = True
                    break
            if not found:
                snap_remaining.append(snap)

        # Step 2: weapon match + stats multiset match (order-only diffs)
        reorder_issues: List[Dict[str, object]] = []
        snap_after_reorder = []
        for snap in snap_remaining:
            stats_ms = stats_multiset(snap)
            weapons = normalize_weapons(snap)
            match_idx = None
            for idx, tgt in enumerate(tgt_blocks):
                if tgt_used[idx]:
                    continue
                if normalize_weapons(tgt) != weapons:
                    continue
                if stats_multiset(tgt) == stats_ms:
                    match_idx = idx
                    break
            if match_idx is not None:
                tgt_used[match_idx] = True
                reorder_issues.append({"snapshot": snap, "target": tgt_blocks[match_idx]})
            else:
                snap_after_reorder.append(snap)

        # Step 3: weapon match + content diffs (same weapons, stats differ)
        content_diffs: List[Dict[str, object]] = []
        snap_after_content = []
        for snap in snap_after_reorder:
            weapons = normalize_weapons(snap)
            match_idx = None
            for idx, tgt in enumerate(tgt_blocks):
                if tgt_used[idx]:
                    continue
                if normalize_weapons(tgt) == weapons:
                    match_idx = idx
                    break
            if match_idx is not None:
                tgt_used[match_idx] = True
                tgt = tgt_blocks[match_idx]
                snap_ms = stats_multiset(snap)
                tgt_ms = stats_multiset(tgt)
                missing_stats = list((snap_ms - tgt_ms).elements())
                extra_stats = list((tgt_ms - snap_ms).elements())
                content_diffs.append(
                    {
                        "snapshot": snap,
                        "target": tgt,
                        "missing_stats": missing_stats,
                        "extra_stats": extra_stats,
                    }
                )
            else:
                snap_after_content.append(snap)

        # Remaining unmatched snapshot blocks
        missing_blocks = snap_after_content
        # Remaining unmatched target blocks
        extra_blocks = [tgt for idx, tgt in enumerate(tgt_blocks) if not tgt_used[idx]]

        if reorder_issues or content_diffs or missing_blocks or extra_blocks:
            report[name] = {
                "reorder_only": [
                    {
                        "weapon": normalize_weapons(pair["snapshot"]),
                        "snapshot_stats": pair["snapshot"].get("stats"),
                        "target_stats": pair["target"].get("stats"),
                    }
                    for pair in reorder_issues
                ],
                "content_diffs": content_diffs,
                "missing_blocks": missing_blocks,
                "extra_blocks": extra_blocks,
            }

    return report


def main() -> None:
    args = parse_args()
    snapshot_entries = load_entries(Path(args.snapshot))
    target_entries = load_entries(Path(args.target))

    diff = compare_skills(snapshot_entries, target_entries)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(diff, f, indent=2, ensure_ascii=False)
        print(f"Wrote diff to {out_path}")

    if not diff:
        print("All snapshot skills match target (ignoring order).")
    else:
        print(f"Found differences for {len(diff)} skill(s):")
        for name, entries in diff.items():
            reorder_count = len(entries.get("reorder_only", []))
            content_count = len(entries.get("content_diffs", []))
            missing_count = len(entries.get("missing_blocks", []))
            extra_count = len(entries.get("extra_blocks", []))
            print(
                f"- {name}: reorder-only {reorder_count}, content diffs {content_count}, missing {missing_count}, extra {extra_count}"
            )


if __name__ == "__main__":
    main()
