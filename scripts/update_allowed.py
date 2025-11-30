import json
import re
import sys
from pathlib import Path
import yaml

BASE_LIST = Path('basegame_items.yaml')
INDEX_PATH = Path('work/items_index.json')
ALLOWED_PATH = Path('work/allowed_items.json')
ALLOWED_TRUE_PATH = Path('work/allowed_items_use_true.json')
TODO_PATH = Path('work/items_todo_filtered.json')
IGNORE_PATH = Path('ignore.json')


def load_base_names():
    data = yaml.safe_load(BASE_LIST.read_text()) or {}
    names = set()
    for _, content in (data.get('since_1_09_0') or {}).items():
        for _, v in (content or {}).items():
            if isinstance(v, list):
                for entry in v:
                    if isinstance(entry, str):
                        names.add(entry.lower())
                    elif isinstance(entry, dict):
                        names.update(k.lower() for k in entry.keys())
            elif isinstance(v, dict):
                names.update(k.lower() for k in v.keys())
    return names


def load_ignore():
    if IGNORE_PATH.exists():
        try:
            data = json.loads(IGNORE_PATH.read_text(encoding='utf-8'))
            if isinstance(data, list):
                out = set()
                for x in data:
                    s = str(x)
                    out.add(s)
                    out.add(s.replace('_', ' '))
                    out.add(s.replace(' ', '_'))
                return out
        except Exception:
            pass
    return set()


def main():
    base_names = load_base_names()
    ignore_names = load_ignore()
    index = json.loads(INDEX_PATH.read_text(encoding='utf-8'))

    base_re = re.compile(r'^(.*)\s\+(\d+)$')
    bases_with_plus10 = set()
    for item in index:
        if item.get('category') == 'consumable':
            m = base_re.match(item.get('name', ''))
            if m and m.group(2) == '10':
                bases_with_plus10.add(m.group(1))

    def should_force_false(item):
        name = item.get('name', '')
        low = name.lower()
        cat = (item.get('category') or '').lower()
        if cat in ('weapon', 'ash', 'unknown'):
            return True
        if name == '[ERROR]':
            return True
        if 'remembrance of' in low:
            return True
        if 'cookbook' in low:
            return True
        if low.startswith('about '):
            return True
        if 'letter' in low:
            return True
        if 'bell bearing' in low:
            return True
        if low.startswith('note:'):
            return True
        if low.startswith('map:'):
            return True
        if cat == 'consumable':
            if 'prayerbook' in low:
                return True
            if 'scroll' in low:
                return True
            if 'painting' in low:
                return True
            if ' key' in low or low.endswith(' key') or low == 'key':
                return True
            m = base_re.match(name)
            base_name = m.group(1) if m else name
            if base_name in bases_with_plus10:
                return True
        if name in ignore_names:
            return True
        return False

    allowed = []
    for item in index:
        name_lower = item['name'].lower()
        bundle = item.get('bundle', '')
        is_base = (name_lower in base_names) and bundle == 'item-msgbnd-dcx'
        is_dlc = bundle == 'item_dlc01-msgbnd-dcx'
        allowed_flag = is_base or is_dlc
        if not allowed_flag or should_force_false(item):
            item['use'] = False
        else:
            if is_base:
                item['use'] = True
            elif 'use' in item:
                item.pop('use', None)
        allowed.append(item)

    allowed_true = [i for i in allowed if i.get('use') is not False]
    ALLOWED_PATH.write_text(json.dumps(allowed, ensure_ascii=False, indent=2), encoding='utf-8')
    ALLOWED_TRUE_PATH.write_text(json.dumps(allowed_true, ensure_ascii=False, indent=2), encoding='utf-8')
    TODO_PATH.write_text(json.dumps(allowed_true, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"allowed total {len(allowed)}, usable {len(allowed_true)}, ignore {len(ignore_names)}")


if __name__ == '__main__':
    main()
