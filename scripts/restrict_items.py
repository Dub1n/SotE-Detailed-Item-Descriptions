import json
from pathlib import Path

ITEMS = Path('work/items_index.json')
BASE_YAML = Path('basegame_items.yaml')
READY_DIR = Path('work/responses/ready')

index = json.load(ITEMS.open())
import yaml
base_data = yaml.safe_load(BASE_YAML.read_text()) or {}
base_names = set()
for _, content in (base_data.get('since_1_09_0') or {}).items():
    for k,v in (content or {}).items():
        if isinstance(v, list):
            for entry in v:
                if isinstance(entry, str):
                    base_names.add(entry.lower())
                elif isinstance(entry, dict):
                    base_names.update(x.lower() for x in entry.keys())
        elif isinstance(v, dict):
            base_names.update(x.lower() for x in v.keys())

def is_allowed(e):
    name_lower = e['name'].lower()
    if e.get('bundle') == 'item_dlc01-msgbnd-dcx':
        return True
    if name_lower in base_names:
        return True
    return False

updated = 0
for path in READY_DIR.glob('*.json'):
    try:
        data = json.load(path.open())
    except Exception:
        continue
    changed = False
    for obj in data:
        name = obj.get('name','').lower()
        iid = obj.get('id')
        try:
            iid_int = int(iid)
        except Exception:
            continue
        match = next((e for e in index if int(e['id'])==iid_int and e['name'].lower()==name), None)
        if match and is_allowed(match):
            if name in base_names:
                if obj.get('use') is not True:
                    obj['use'] = True
                    changed = True
            else:
                if 'use' in obj:
                    del obj['use']
                    changed = True
        else:
            if obj.get('use') is not False:
                obj['use'] = False
                changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        updated += 1
print(f"Updated {updated} ready JSON files with use flags")

# Todo list = allowed only
OUT = Path('work/items_todo_filtered.json')
todo = [e for e in index if is_allowed(e)]
OUT.write_text(json.dumps(todo, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Filtered todo written with {len(todo)} entries")
