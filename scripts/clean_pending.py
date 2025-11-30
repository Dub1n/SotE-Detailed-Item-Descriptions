import json
from pathlib import Path
import re

PENDING = Path('work/responses/pending')
READY = Path('work/responses/ready')
ARCHIVE = Path('work/responses/archive')
ARCHIVE.mkdir(parents=True, exist_ok=True)


def try_fix_json(text: str):
    # Attempt 1: parse as-is
    try:
        return json.loads(text)
    except Exception:
        pass
    # Attempt 2: if it ends without closing brackets, try to close the last object/array
    stripped = text.strip()
    # Ensure starts with [
    if not stripped.startswith('['):
        return None
    # Heuristic: ensure it ends with ]
    if not stripped.endswith(']'):
        stripped += ']'  # append closing bracket
    # Balance braces by counting
    open_braces = stripped.count('{')
    close_braces = stripped.count('}')
    if close_braces < open_braces:
        stripped += '}' * (open_braces - close_braces)
    # Try load again
    try:
        return json.loads(stripped)
    except Exception:
        # Attempt 3: truncate to last complete object
        last = stripped.rfind('},')
        if last != -1:
            candidate = stripped[:last+1]
            if not candidate.endswith(']'):
                candidate += ']'  # close array
            try:
                return json.loads(candidate)
            except Exception:
                pass
    return None


def main():
    moved = 0
    skipped_overwrite = 0
    for f in list(PENDING.glob('*.json')):
        text = f.read_text(encoding='utf-8', errors='ignore')
        data = try_fix_json(text)
        if data is None:
            continue
        # ensure list of dicts
        if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
            continue
        target = READY / f.name
        if target.exists():
            print(f"skip overwrite: {target} already exists; leaving pending file intact")
            skipped_overwrite += 1
            continue
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        f.unlink()  # remove pending file
        moved += 1
    print(f"Cleaned and moved {moved} pending JSON files to ready")
    if skipped_overwrite:
        print(f"Skipped {skipped_overwrite} files because a ready file already exists (no overwrite performed)")

if __name__ == '__main__':
    main()
