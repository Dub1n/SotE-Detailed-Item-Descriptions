import json
import xml.etree.ElementTree as ET
from pathlib import Path
import yaml

# Roots: base uses the modded detailed text we already have in-repo (mod/ as primary fallback),
# DLC pulls from the real SOTE dumps placed under real_dlc/. For DLC bundles
# we only want the *_dlc01 FMGs (dlc02 bundle includes placeholders and copies).
BASE_ROOT = Path('build/msg/engus')
if not BASE_ROOT.exists():
    BASE_ROOT = Path('mod/msg/engus')
DLC_ROOT = Path('real_dlc/msg/engus')

BUNDLES = [
    (BASE_ROOT, 'item-msgbnd-dcx', None),
    (DLC_ROOT, 'item_dlc01-msgbnd-dcx', '_dlc01'),
    (DLC_ROOT, 'item_dlc02-msgbnd-dcx', '_dlc01'),
]

VANILLA_JSON = Path('data/msg/engus/item.msgbnd.dcx.json')
BASEGAME_LIST = Path('basegame_items.yaml')
OUT_INDEX = Path('work/items_index.json')
OUT_TODO = Path('work/items_todo.json')

FMG_CATEGORY_MAP = {
    'Accessory': 'talisman',
    'Protector': 'armor',
    'Weapon': 'weapon',
    'Goods': 'consumable',
    'Magic': 'spell',
    'Arts': 'skill',
    'Gem': 'ash',
}

vanilla = json.load(VANILLA_JSON.open())

def load_base_list():
    data = yaml.safe_load(BASEGAME_LIST.read_text()) or {}
    items = set()
    for patch, content in (data.get('since_1_09_0') or {}).items():
        for k,v in (content or {}).items():
            if isinstance(v, list):
                for entry in v:
                    if isinstance(entry, str):
                        items.add(entry)
                    elif isinstance(entry, dict):
                        items.update(entry.keys())
            elif isinstance(v, dict):
                items.update(v.keys())
    return items

base_items_set = load_base_list()

index = []

def get_prefix(name_file: Path, dlc_suffix: str | None) -> str:
    fname = name_file.name
    if dlc_suffix and dlc_suffix in fname:
        fname = fname.replace(dlc_suffix, '')
    fname = fname.replace('.fmg.xml', '')
    if fname.endswith('Name'):
        fname = fname[:-4]
    return fname


def parse_bundle(root: Path, bundle_name: str, dlc_suffix: str | None):
    bundle_dir = root / bundle_name
    if not bundle_dir.exists():
        print(f"skip missing bundle dir: {bundle_dir}")
        return
    pattern = '*Name.fmg.xml' if not dlc_suffix else f"*Name{dlc_suffix}.fmg.xml"
    for name_file in bundle_dir.glob(pattern):
        prefix = get_prefix(name_file, dlc_suffix)
        category = FMG_CATEGORY_MAP.get(prefix, 'unknown')
        suffix = dlc_suffix or ''
        info_file = bundle_dir / f"{prefix}Info{suffix}.fmg.xml"
        caption_file = bundle_dir / f"{prefix}Caption{suffix}.fmg.xml"
        name_root = ET.parse(name_file).getroot()
        info_root = ET.parse(info_file).getroot() if info_file.exists() else None
        caption_root = ET.parse(caption_file).getroot() if caption_file.exists() else None
        for text_node in name_root.findall('.//text'):
            iid = text_node.attrib.get('id')
            name_val = text_node.text
            if name_val is None or name_val.strip() == '' or name_val.startswith('%'):
                continue
            def find_in(root):
                if not root:
                    return None
                for t in root.findall('.//text'):
                    if t.attrib.get('id') == iid:
                        return t.text
                return None
            info_val = find_in(info_root)
            caption_val = find_in(caption_root)
            vanilla_name_key = f"N:\\GR\\data\\INTERROOT_win64\\msg\\engUS\\{prefix}Name.fmg"
            vanilla_info_key = f"N:\\GR\\data\\INTERROOT_win64\\msg\\engUS\\{prefix}Info.fmg"
            vanilla_cap_key = f"N:\\GR\\data\\INTERROOT_win64\\msg\\engUS\\{prefix}Caption.fmg"
            vanilla_name = vanilla.get(vanilla_name_key, {}).get(iid)
            vanilla_info = vanilla.get(vanilla_info_key, {}).get(iid)
            vanilla_caption = vanilla.get(vanilla_cap_key, {}).get(iid)
            index.append({
                'id': int(iid),
                'name': name_val,
                'category': category,
                'prefix': prefix,
                'bundle': bundle_name,
                # For DLC (no modded text), treat the in-bundle text as "vanilla_*".
                # For base (modded build), treat in-bundle text as "mod_*" and vanilla_* from JSON.
                'mod_info': info_val if bundle_name == 'item-msgbnd-dcx' else None,
                'mod_caption': caption_val if bundle_name == 'item-msgbnd-dcx' else None,
                'vanilla_info': info_val if bundle_name != 'item-msgbnd-dcx' else vanilla_info,
                'vanilla_caption': caption_val if bundle_name != 'item-msgbnd-dcx' else vanilla_caption,
            })

for root, bundle, dlc_suffix in BUNDLES:
    parse_bundle(root, bundle, dlc_suffix)

OUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
json.dump(index, OUT_INDEX.open('w'), ensure_ascii=False, indent=2)

# build todo list: all DLC1 + base items set name match (case-insensitive eq)
todo = []
base_lower = {s.lower() for s in base_items_set}
for item in index:
    bundle = item['bundle']
    is_dlc = bundle.startswith('item_dlc')
    is_base_target = item['name'].lower() in base_lower
    if is_dlc or is_base_target:
        todo.append(item)

json.dump(todo, OUT_TODO.open('w'), ensure_ascii=False, indent=2)
print(f"Indexed {len(index)} items; TODO count {len(todo)}")
