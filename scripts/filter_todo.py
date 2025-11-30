import json
from pathlib import Path

ITEMS_TODO = Path('work/items_todo.json')
OUT = Path('work/items_todo_filtered.json')

# categories to keep; armor is always kept per instruction
KEEP_CATS = {'armor', 'talisman', 'weapon', 'spell', 'skill', 'ash', 'consumable'}

def has_meaningful_info(entry):
    info = entry.get('vanilla_info') or entry.get('mod_info') or ''
    if not info:
        return False
    s = str(info).strip()
    if not s or s.lower().startswith('%null%'):
        return False
    if len(s) < 4:
        return False
    return True

todo = json.load(ITEMS_TODO.open())
filtered = []
for e in todo:
    cat = e.get('category')
    if cat not in KEEP_CATS:
        continue
    if cat == 'armor':
        filtered.append(e)
        continue
    if has_meaningful_info(e):
        filtered.append(e)

OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(filtered, OUT.open('w'), ensure_ascii=False, indent=2)
print(f"Original TODO: {len(todo)}, filtered: {len(filtered)}")
