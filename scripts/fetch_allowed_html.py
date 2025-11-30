import argparse
import json
import sys
from pathlib import Path
from typing import Set

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.append(str(SCRIPT_DIR.parent))
from scripts import fextralife_scrape as fs


def load_allowed(path: Path) -> Set[str]:
    data = json.loads(path.read_text(encoding='utf-8'))
    names = set()
    for entry in data:
        name = entry.get('name')
        if name:
            names.add(name)
    return names


def main():
    parser = argparse.ArgumentParser(description="Prune/fetch fextralife HTML for allowed items only.")
    parser.add_argument('--allowed-file', default='work/allowed_items_use_true.json', help='JSON array of allowed items')
    parser.add_argument('--cache-dir', default='work/fex_cache', help='Directory where HTML files are cached')
    args = parser.parse_args()

    allowed_names = load_allowed(Path(args.allowed_file))
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    keep_files = {name.replace(' ', '_') + '.html' for name in allowed_names}

    removed = 0
    for p in cache_dir.glob('*.html'):
        if p.name not in keep_files:
            p.unlink()
            removed += 1

    missing = [name for name in allowed_names if not (cache_dir / (name.replace(' ', '_') + '.html')).exists()]
    fetch_failures = []
    for idx, name in enumerate(missing, 1):
        res = fs.scrape_item(name)
        if res.get('error'):
            fetch_failures.append(name)
        if idx % 50 == 0:
            print(f"Fetched {idx}/{len(missing)}")

    print(f"Allowed items: {len(allowed_names)}")
    print(f"Removed stale cache files: {removed}")
    print(f"Fetched missing: {len(missing) - len(fetch_failures)}, failures: {len(fetch_failures)}")
    if fetch_failures:
        print("Failures:", ', '.join(fetch_failures[:20]) + (' ...' if len(fetch_failures) > 20 else ''))


if __name__ == '__main__':
    main()
