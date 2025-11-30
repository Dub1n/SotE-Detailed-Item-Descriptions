import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple, List

MOD_ROOT = Path('/mnt/c/Users/gabri/Applications/Games/Modding/Elden Ring/Detailed Item Descriptions v1.3.4-1356-1-3-4-1720317354/msg/engus')
BUILD_ROOT = Path('build/msg/engus')
ITEMS_INDEX = Path('work/items_index.json')

CATEGORY_PREFIX = {
    'talisman': 'Accessory',
    'armor': 'Protector',
    'weapon': 'Weapon',
    'consumable': 'Goods',
    'spell': 'Magic',
    'skill': 'Arts',
    'ash': 'Gem',
}


def ensure_build_bundle(bundle: str):
    src = MOD_ROOT / bundle
    dst = BUILD_ROOT / bundle
    if dst.exists():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    return dst


def load_mapping() -> Dict[Tuple[str, int], Dict]:
    index = json.load(ITEMS_INDEX.open())
    mapping: Dict[Tuple[str, int], List[Dict]] = {}
    for entry in index:
        key = (entry['category'], int(entry['id']))
        mapping.setdefault(key, []).append(entry)
    return mapping


def update_fmg_text(paths: List[Path], target_id: int, new_text: str):
    """Try updating all FMG XMLs that contain the target id. If none contain it, append to the first existing path."""
    updated_any = False
    for fmg_path in paths:
        if not fmg_path.exists():
            continue
        tree = ET.parse(fmg_path)
        root = tree.getroot()
        for t in root.findall('.//text'):
            if t.attrib.get('id') == str(target_id):
                t.text = new_text
                tree.write(fmg_path, encoding='utf-8', xml_declaration=True)
                updated_any = True
    if updated_any:
        return True
    # If not found in any, append to first existing file
    for fmg_path in paths:
        if not fmg_path.exists():
            continue
        tree = ET.parse(fmg_path)
        root = tree.getroot()
        new_elem = ET.SubElement(root, 'text', {'id': str(target_id)})
        new_elem.text = new_text
        tree.write(fmg_path, encoding='utf-8', xml_declaration=True)
        return True
    return False


def apply_response_file(resp_path: Path, mapping: Dict[Tuple[str,int], Dict]):
    data = json.load(resp_path.open())
    for item in data:
        if item.get('use') is False:
            print(f"[skip] use=false for {item.get('name')} ({item.get('id')}) in {resp_path.name}")
            continue
        cat = item.get('category')
        iid = int(item['id'])
        key = (cat, iid)
        if key not in mapping:
            print(f"[warn] no mapping for {item['name']} ({cat} {iid})")
            continue
        # Prepare text adjustments per category (once per item).
        caption_text = item.get('caption')
        info_text = item.get('info')
        # For skills, roll caption + info into one block (written to Caption FMG).
        if cat == 'skill' and caption_text and info_text:
            caption_text = f"{caption_text}\n\n\n{info_text}"
            info_text = None
        # For ashes, use vanilla boilerplate up to first blank line, then append skill info.
        if cat == 'ash' and info_text:
            # Use the first matching entry's vanilla_caption to derive boilerplate.
            vanilla_cap = ''
            for entry in mapping[key]:
                vanilla_cap = entry.get('vanilla_caption') or ''
                if vanilla_cap:
                    break
            boiler = vanilla_cap.split('\n\n', 1)[0].strip()
            if boiler:
                caption_text = f"{boiler}\n\n\n{info_text}"
            else:
                caption_text = info_text
            info_text = None

        for entry in mapping[key]:
            bundle = entry['bundle']
            prefix = CATEGORY_PREFIX.get(cat)
            if not prefix:
                print(f"[warn] no prefix for category {cat} ({item['name']})")
                continue
            bundle_dir = ensure_build_bundle(bundle)
            # Allow cross-dlc lookups when ids actually live in the other dlc bundle.
            alt_dirs: List[Path] = []
            if bundle.startswith('item_dlc01'):
                alt_dirs.append(BUILD_ROOT / 'item_dlc02-msgbnd-dcx')
            elif bundle.startswith('item_dlc02'):
                alt_dirs.append(BUILD_ROOT / 'item_dlc01-msgbnd-dcx')
            # Prefer DLC-specific FMGs if present, then fall back to base.
            info_candidates = [
                bundle_dir / f"{prefix}Info_dlc01.fmg.xml",
                bundle_dir / f"{prefix}Info_dlc02.fmg.xml",
                bundle_dir / f"{prefix}Info.fmg.xml",
            ]
            cap_candidates = [
                bundle_dir / f"{prefix}Caption_dlc01.fmg.xml",
                bundle_dir / f"{prefix}Caption_dlc02.fmg.xml",
                bundle_dir / f"{prefix}Caption.fmg.xml",
            ]
            for alt in alt_dirs:
                info_candidates.extend([
                    alt / f"{prefix}Info_dlc01.fmg.xml",
                    alt / f"{prefix}Info_dlc02.fmg.xml",
                    alt / f"{prefix}Info.fmg.xml",
                ])
                cap_candidates.extend([
                    alt / f"{prefix}Caption_dlc01.fmg.xml",
                    alt / f"{prefix}Caption_dlc02.fmg.xml",
                    alt / f"{prefix}Caption.fmg.xml",
                ])
            # For skills/ashes, there is no Info FMG; write both caption and info into Caption.
            if cat in ('skill', 'ash'):
                info_candidates = cap_candidates + info_candidates
            # update caption and info
            if caption_text is not None:
                cap_existing = [p for p in cap_candidates if p.exists()]
                if cap_existing:
                    updated = update_fmg_text(cap_existing, iid, caption_text)
                    if not updated:
                        print(f"[warn] caption id not found {iid} in {bundle_dir}")
                else:
                    print(f"[warn] caption file missing for {iid} in {bundle_dir}")
            if info_text is not None:
                info_existing = [p for p in info_candidates if p.exists()]
                if info_existing:
                    updated = update_fmg_text(info_existing, iid, info_text)
                    if not updated:
                        print(f"[warn] info id not found {iid} in {bundle_dir}")
                else:
                    # Some categories (e.g., skills) may not have an Info FMG; note and continue.
                    print(f"[warn] info file missing for {iid} in {bundle_dir}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('responses', nargs='+', help='response json files from batches')
    args = ap.parse_args()

    mapping = load_mapping()
    for resp in args.responses:
        apply_response_file(Path(resp), mapping)
    print("Applied responses to build/; originals untouched.")


if __name__ == '__main__':
    main()
