import shutil
import time
from pathlib import Path

PENDING = Path('work/responses/pending')
ARCHIVE_ROOT = Path('work/responses/archive')
ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)

def archive_pending():
    if not PENDING.exists():
        print('No pending dir.')
        return None
    ts = time.strftime('%Y%m%d-%H%M%S')
    dest = ARCHIVE_ROOT / ts
    dest.mkdir(parents=True, exist_ok=True)
    moved = 0
    for item in PENDING.iterdir():
        shutil.move(str(item), str(dest / item.name))
        moved += 1
    print(f"Archived {moved} entries to {dest}")
    return dest

if __name__ == '__main__':
    archive_pending()
