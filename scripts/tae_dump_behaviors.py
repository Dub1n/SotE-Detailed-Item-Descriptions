#!/usr/bin/env python3
"""
Extract Behavior events (BehaviorListID) from unpacked TAE files.

Usage:
  python scripts/tae_dump_behaviors.py --tae-root /path/to/unpacked/chr --out PARAM/tae_behavior_map/behaviors.json

Notes:
- Point --tae-root at the folder that contains c0000-anibnd/GR/data/INTERROOT_win64/chr/c0000/tae and any c0000_aXX variants.
- Only Behavior events (type 304) are parsed; other event types are ignored.
- The TAE format reader is minimal and tailored to Elden Ring/TAE3; it may bail if the header checks fail.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def read_utf16le(data: memoryview, offset: int) -> str:
    chars = []
    while offset + 1 < len(data):
        val = struct.unpack_from("<H", data, offset)[0]
        if val == 0:
            break
        chars.append(val)
        offset += 2
    return bytes(struct.pack("<%dH" % len(chars), *chars)).decode("utf-16le")


def read_i32(data: memoryview, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def read_u32(data: memoryview, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def read_i64(data: memoryview, offset: int) -> int:
    return struct.unpack_from("<q", data, offset)[0]


def read_u64(data: memoryview, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def read_f32(data: memoryview, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


def parse_tae(path: Path) -> List[dict]:
    data = memoryview(path.read_bytes())
    if len(data) < 0xB0 or data[0:4].tobytes() != b"TAE ":
        return []

    # Basic header read (mirrors SoulsFormats TAE3 reader).
    # Magic already checked; skip 0x4..0xC sanity bytes.
    version = read_i32(data, 0x8)
    if version not in (0x1000C, 0x1000D):
        return []
    anim_count = read_i32(data, 0x54)
    anims_offset = read_i64(data, 0x58)
    skeleton_name_offset = read_i64(data, 0xB0)
    # skeleton_name = read_utf16le(data, skeleton_name_offset)  # unused, but confirmed reachable

    events: List[dict] = []

    for i in range(anim_count):
        anim_header = anims_offset + i * 0x10
        anim_id = read_i64(data, anim_header)
        anim_offset = read_i64(data, anim_header + 8)
        if anim_offset <= 0 or anim_offset >= len(data):
            continue

        event_headers_offset = read_i64(data, anim_offset + 0x00)
        # event_groups_offset = read_i64(data, anim_offset + 0x08)
        # times_offset = read_i64(data, anim_offset + 0x10)
        # anim_file_offset = read_i64(data, anim_offset + 0x18)
        event_count = read_i32(data, anim_offset + 0x20)
        # event_group_count = read_i32(data, anim_offset + 0x24)
        # times_count = read_i32(data, anim_offset + 0x28)
        # skip int32 padding at +0x2C
        if event_count <= 0:
            continue
        if event_headers_offset <= 0 or event_headers_offset + event_count * 0x18 > len(data):
            continue

        for ev_idx in range(event_count):
            hdr = event_headers_offset + ev_idx * 0x18
            if hdr < 0 or hdr + 0x18 > len(data):
                break
            start_time_offset = read_i64(data, hdr + 0x00)
            end_time_offset = read_i64(data, hdr + 0x08)
            event_data_offset = read_i64(data, hdr + 0x10)
            if event_data_offset <= 0 or event_data_offset + 0x18 > len(data):
                continue
            event_type = read_u64(data, event_data_offset)
            if event_type != 304:  # BehaviorThing in SoulsFormats; holds BehaviorListID
                continue
            start_time = read_f32(data, start_time_offset) if 0 <= start_time_offset + 4 <= len(data) else None
            end_time = read_f32(data, end_time_offset) if 0 <= end_time_offset + 4 <= len(data) else None
            behavior_id = read_i32(data, event_data_offset + 0x14)  # after type (8) + ptr (8) + u16/u16
            events.append(
                {
                    "tae": path.name,
                    "anim_id": anim_id,
                    "start": start_time,
                    "end": end_time,
                    "behaviorJudgeId": behavior_id,
                }
            )

    return events


def build_map(tae_files: Iterable[Path]) -> Dict[str, List[dict]]:
    all_events: List[dict] = []
    for tae in tae_files:
        try:
            events = parse_tae(tae)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Failed to parse {tae}: {exc}")
            continue
        all_events.extend(events)
    return {
        "behaviors": sorted(
            {e["behaviorJudgeId"] for e in all_events if e.get("behaviorJudgeId") is not None}
        ),
        "events": all_events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump Behavior events from TAE files into a JSON map.")
    parser.add_argument("--tae-root", required=True, type=Path, help="Root directory to search for .tae files (recursively).")
    parser.add_argument("--out", default=Path("PARAM/tae_behavior_map/behaviors.json"), type=Path, help="Output JSON path.")
    args = parser.parse_args()

    tae_files = sorted(args.tae_root.rglob("*.tae"))
    if not tae_files:
        raise SystemExit(f"No .tae files found under {args.tae_root}")

    result = {
        "tae_root": str(args.tae_root),
        **build_map(tae_files),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} with {len(result['behaviors'])} unique behavior IDs from {len(result['events'])} events.")


if __name__ == "__main__":
    main()
