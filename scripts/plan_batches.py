import json
from pathlib import Path
from typing import List, Dict
import glob

ITEMS_TODO = Path('work/items_todo_filtered.json') if Path('work/items_todo_filtered.json').exists() else Path('work/items_todo.json')
# Count any ready file variant (original or renamed with suffixes) as processed.
PROCESSED_GLOB = 'work/responses/ready/*_response*.json'
OUT_PLAN = Path('work/batch_plan.json')
CHUNK_SIZE = 15
CATEGORY_ORDER = ['armor','talisman','weapon','spell','skill','ash','consumable']
FILTERED_DIR = Path('work/fex_cache_filtered')


def load_processed_ids():
    ids = set()
    for path in glob.glob(PROCESSED_GLOB):
        try:
            data = json.load(open(path, encoding='utf-8'))
            for obj in data:
                if isinstance(obj, dict) and 'id' in obj:
                    ids.add(int(obj['id']))
        except Exception:
            continue
    return ids


def main():
    items = json.load(ITEMS_TODO.open())
    # Only include items that have a filtered effect_lines JSON available and non-empty.
    def has_filtered(item):
        fname = item['name'].replace(' ', '_') + '_filtered.json'
        path = FILTERED_DIR / fname
        if not path.exists():
            return False
        try:
            data = json.load(path.open(encoding='utf-8'))
            lines = data.get('effect_lines') or []
            return isinstance(lines, list) and len([ln for ln in lines if isinstance(ln, str) and ln.strip()]) > 0
        except Exception:
            return False

    # Exclude any items that are in ignore.json (normalized underscores/spaces)
    ignore_names = set()
    ignore_path = Path('ignore.json')
    if ignore_path.exists():
        try:
            raw = json.load(ignore_path.open())
            for n in raw:
                s = str(n).strip()
                ignore_names.add(s)
                ignore_names.add(s.replace('_', ' '))
                ignore_names.add(s.replace(' ', '_'))
        except Exception:
            pass

    items = [i for i in items if has_filtered(i) and i['name'] not in ignore_names and i['name'].replace(' ', '_') not in ignore_names]
    processed = load_processed_ids()
    plan: List[Dict] = []
    for cat in CATEGORY_ORDER:
        cat_items = [t for t in items if t.get('category') == cat and int(t['id']) not in processed]
        if not cat_items:
            continue
        idx = 0
        chunk_idx = 0
        while idx < len(cat_items):
            chunk = cat_items[idx:idx+CHUNK_SIZE]
            chunk_idx += 1
            prefix = f"{cat[:3].upper()}{chunk_idx:03d}_"
            plan.append({
                'category': cat,
                'start': idx,
                'limit': len(chunk),
                'batch_size': CHUNK_SIZE,
                'prefix': prefix,
                'save_raw': True,
            })
            idx += CHUNK_SIZE
    OUT_PLAN.parent.mkdir(parents=True, exist_ok=True)
    json.dump(plan, OUT_PLAN.open('w'), ensure_ascii=False, indent=2)
    print(f"Plan entries: {len(plan)}")

if __name__ == '__main__':
    main()
