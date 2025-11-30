import json
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from collections import defaultdict

ITEMS_INDEX = Path("work/items_index.json")
READY_DIR = Path("work/responses/ready")
MOD_ROOT = Path("mod")


def load_index():
    idx = json.loads(ITEMS_INDEX.read_text(encoding="utf-8"))
    mapping = defaultdict(list)
    for entry in idx:
        key = (entry["category"], int(entry["id"]))
        mapping[key].append(entry)
    return mapping


def load_ready_entries():
    out = []
    for path in READY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for obj in data:
            if isinstance(obj, dict):
                out.append(obj)
    return out


def update_fmg_text(paths, target_id, new_text):
    for fmg_path in paths:
        if not fmg_path.exists():
            continue
        tree = ET.parse(fmg_path)
        root = tree.getroot()
        for t in root.findall(".//text"):
            if t.attrib.get("id") == str(target_id):
                t.text = new_text
                tree.write(fmg_path, encoding="utf-8", xml_declaration=True)
    # If not found, append to the first existing file
    for fmg_path in paths:
        if not fmg_path.exists():
            continue
        tree = ET.parse(fmg_path)
        root = tree.getroot()
        new_elem = ET.SubElement(root, "text", {"id": str(target_id)})
        new_elem.text = new_text
        tree.write(fmg_path, encoding="utf-8", xml_declaration=True)
        break


def main():
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
    ready = load_ready_entries()
    for item in ready:
        if item.get("use") is False:
            continue
        cat = item.get("category")
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
