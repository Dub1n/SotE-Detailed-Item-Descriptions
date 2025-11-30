import json
from pathlib import Path
from collections import defaultdict

READY_DIR = Path("work/responses/ready")
OUT_DIR = READY_DIR


def load_ready():
    out = []
    for path in READY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            out.extend([obj for obj in data if isinstance(obj, dict)])
    return out


def main():
    items = load_ready()
    by_cat = defaultdict(list)
    for obj in items:
        cat = obj.get("category", "unknown")
        by_cat[cat].append(obj)
    for cat, objs in by_cat.items():
        objs_sorted = sorted(objs, key=lambda o: int(o.get("id", 0)))
        out_path = OUT_DIR / f"{cat}_merged_sorted.json"
        out_path.write_text(json.dumps(objs_sorted, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out_path} ({len(objs_sorted)} items)")


if __name__ == "__main__":
    main()
