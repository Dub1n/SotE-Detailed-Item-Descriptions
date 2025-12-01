import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Iterable, List, Dict, Optional
from html.parser import HTMLParser

ITEMS_INDEX = Path("work/items_index.json")
READY_DIR = Path("work/responses/ready")
MOD_ROOT = Path("mod")
SKILL_PATH = READY_DIR / "skill.json"
ASHES_PATH = READY_DIR / "ashes_generated.json"


def load_index():
    idx = json.loads(ITEMS_INDEX.read_text(encoding="utf-8"))
    mapping = defaultdict(list)
    for entry in idx:
        key = (entry["category"], int(entry["id"]))
        mapping[key].append(entry)
    return mapping


def load_ready_entries(paths: Iterable[Path]) -> List[Dict]:
    out: List[Dict] = []
    for path in paths:
        default_cat: Optional[str] = "consumable" if path.name.startswith("consumable_") else None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[warn] failed to parse {path.name}: {e}")
            continue
        if not isinstance(data, list):
            continue
        for obj in data:
            if isinstance(obj, dict):
                if obj.get("use") is False:
                    continue
                cat = obj.get("category") or default_cat
                if not cat:
                    print(f"[warn] missing category for {obj.get('name')} ({obj.get('id')}) in {path.name}")
                    continue
                obj = dict(obj)
                obj["category"] = cat
                obj["__source"] = path.name  # tracked for validation messages
                out.append(obj)
    return out


def update_fmg_text(paths, target_id, new_text):
    """Overwrite existing FMG entries by id; never add new elements."""
    target_str = str(target_id)
    found_any = False
    for fmg_path in paths:
        if not fmg_path.exists():
            continue
        tree = ET.parse(fmg_path)
        root = tree.getroot()
        updated = False
        for t in root.findall(".//text"):
            if t.attrib.get("id") == target_str:
                found_any = True
                if t.text != new_text:
                    t.text = new_text
                    updated = True
        if updated:
            tree.write(fmg_path, encoding="utf-8", xml_declaration=True)
    if not found_any:
        print(f"[warn] id {target_id} not found in any FMG; skipping append")


class _TagValidator(HTMLParser):
    """Minimal HTML/tag validator for FMG strings."""
    allowed_tags = {"font"}

    def __init__(self):
        super().__init__()
        self.stack: List[str] = []
        self.errors: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.allowed_tags:
            self.errors.append(f"disallowed tag <{tag}>")
            return
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag not in self.allowed_tags:
            self.errors.append(f"disallowed closing </{tag}>")
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"mismatched closing </{tag}>; stack={self.stack}")
        else:
            self.stack.pop()

    def close(self):
        super().close()
        if self.stack:
            self.errors.append(f"unclosed tags {self.stack}")


def validate_html_text(text: str) -> List[str]:
    parser = _TagValidator()
    parser.feed(text)
    parser.close()
    return parser.errors


def validate_ready_entries(entries: List[Dict]):
    """Ensure all caption/info strings only use allowed tags with proper balance."""
    issues: List[str] = []
    for obj in entries:
        source = obj.get("__source", "?")
        item_id = obj.get("id")
        name = obj.get("name")
        for field in ("caption", "info"):
            val = obj.get(field)
            if not isinstance(val, str):
                continue
            errors = validate_html_text(val)
            for err in errors:
                issues.append(f"{source}: id {item_id} {name} {field} -> {err}")
    if issues:
        print("[error] HTML validation failed:")
        for msg in issues:
            print(f" - {msg}")
        raise SystemExit(1)


def refresh_ashes_from_skills(skill_path: Path, ashes_path: Path):
    """Overwrite ash info boxes with the corresponding skill info (id alignment via // 100)."""
    try:
        skill_data = json.loads(skill_path.read_text(encoding="utf-8"))
        ash_data = json.loads(ashes_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[warn] could not refresh ashes ({e})")
        return

    info_by_skill: Dict[int, Optional[str]] = {}
    for entry in skill_data:
        try:
            sid = int(entry.get("id"))
        except (TypeError, ValueError):
            continue
        info_text = entry.get("info") or entry.get("caption")
        info_by_skill[sid] = info_text

    changed = False
    for entry in ash_data:
        try:
            skill_id = int(entry.get("id")) // 100
        except (TypeError, ValueError):
            continue
        info_text = info_by_skill.get(skill_id)
        if not info_text:
            print(f"[warn] no skill info for ash {entry.get('name')} (skill id {skill_id})")
            continue
        if entry.get("info") != info_text:
            entry["info"] = info_text
            changed = True

    if changed:
        ashes_path.write_text(json.dumps(ash_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[info] refreshed ash info from {skill_path.name} into {ashes_path}")
    else:
        print(f"[info] ash info already matches {skill_path.name}")


def main():
    ap = argparse.ArgumentParser(description="Patch FMG XMLs from ready responses into a new package-* directory.")
    ap.add_argument("responses", nargs="*", help="Ready JSON files to apply (default: work/responses/ready/*.json)")
    ap.add_argument("--generate-ash", action="store_true",
                    help="Refresh ashes_generated.json info using skill.json before applying.")
    args = ap.parse_args()

    if args.generate_ash:
        refresh_ashes_from_skills(SKILL_PATH, ASHES_PATH)

    response_paths: List[Path]
    if args.responses:
        response_paths = [Path(p) for p in args.responses]
    else:
        response_paths = sorted(READY_DIR.glob("*.json"))

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    package_root = Path(f"package-{timestamp}")
    if package_root.exists():
        raise SystemExit(f"Package path already exists: {package_root}")
    shutil.copytree(
        MOD_ROOT,
        package_root,
        ignore=shutil.ignore_patterns("*.fmg", "*.dcx"),
    )
    patch_target = package_root / "msg" / "engus"

    idx = load_index()
    ready = load_ready_entries(response_paths)
    validate_ready_entries(ready)
    for item in ready:
        cat = item.get("category")
        if not cat:
            print(f"[warn] skipping {item.get('name')} ({item.get('id')}) with no category")
            continue
        iid = int(item["id"])
        key = (cat, iid)
        if key not in idx:
            continue
        caption_text = item.get("caption")
        info_text = item.get("info")
        for entry in idx[key]:
            bundle = entry["bundle"]
            prefix = entry.get("prefix")
            bundle_dir = patch_target / bundle
            info_paths = [
                bundle_dir / f"{prefix}Info_dlc01.fmg.xml",
                bundle_dir / f"{prefix}Info_dlc02.fmg.xml",
                bundle_dir / f"{prefix}Info.fmg.xml",
            ]
            cap_paths = [
                bundle_dir / f"{prefix}Caption_dlc01.fmg.xml",
                bundle_dir / f"{prefix}Caption_dlc02.fmg.xml",
                bundle_dir / f"{prefix}Caption.fmg.xml",
            ]
            if caption_text is not None:
                update_fmg_text(cap_paths, iid, caption_text)
            if info_text is not None:
                update_fmg_text(info_paths, iid, info_text)
    print(f"Wrote patched FMGs to {package_root}")


if __name__ == "__main__":
    main()
