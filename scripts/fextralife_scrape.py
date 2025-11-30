import argparse
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag

CACHE_DIR = Path('work/fex_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = 'https://eldenring.wiki.fextralife.com/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

MECH_PAT = re.compile(
    r"(increase|boost|raise|reduce|damage|negation|stamina|fp|mana|hp|poise|strength|dexterity|intelligence|faith|arcane|duration|seconds|sec|%|percent|bonus|scaling|cost|build|accumul|guard|reduces|prevents|fall damage|bleed|frost|poison|rot|madness|stance|vigor|endurance|absorption|negate|resistance)",
    re.I,
)

SECTION_KEYS = [
    'use',
    'uses',
    'use in',
    'effect',
    'effects',
    'information',
    'info',
    'guide',
    'notes',
    'tips',
    'passive',
    'skill',
    'weapon skill',
    'ash of war',
]

EXCLUDE_SECTION_KEYS = ['where to find', 'location', 'map', 'drops', 'farming', 'crafting', 'buff']

DROP_PATTERNS = [
    re.compile(r'sell value', re.I),
    re.compile(r'you can hold up to', re.I),
    re.compile(r'you can store up to', re.I),
    re.compile(r'you cannot (store|sell)', re.I),
    re.compile(r'cannot be sold', re.I),
    re.compile(r'notes\s*(?:&|and)?\s*(?:player\s*)?tips\s+go\s+here', re.I),
    re.compile(r'other notes\s*(?:&|and)?\s*(?:player\s*)?tips\s+go\s+here', re.I),
    re.compile(r'^fp cost', re.I),
    re.compile(r'^hp cost', re.I),
    re.compile(r'^scaling\b', re.I),
    re.compile(r'effect information', re.I),
    re.compile(r'updated to patch', re.I),
    re.compile(r'can be altered to', re.I),
    re.compile(r'^slots used', re.I),
    re.compile(r'dmg negation', re.I),
    re.compile(r'^upgrades with', re.I),
    re.compile(r'material used for crafting items', re.I),
    re.compile(r'^found (by|in|on|at)', re.I),
    re.compile(r'can be used to craft the following items', re.I),
]


def fetch_html(name: str) -> Optional[str]:
    cache_file = CACHE_DIR / f"{name.replace(' ', '_')}.html"
    if cache_file.exists():
        return cache_file.read_text(encoding='utf-8', errors='ignore')
    url = BASE_URL + requests.utils.quote(name.replace(' ', '+'))
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return None
    cache_file.write_text(resp.text, encoding='utf-8')
    time.sleep(0.5)
    return resp.text


def gather_section_text(start_header: Tag) -> List[str]:
    texts = []
    sib = start_header.find_next_sibling()
    while sib and sib.name not in ['h1', 'h2', 'h3', 'h4']:
        if sib.name in ['ul', 'ol']:
            for li in sib.find_all('li', recursive=False):
                txt = li.get_text(' ', strip=True)
                if txt:
                    texts.append(txt)
        elif sib.name == 'p':
            txt = sib.get_text(' ', strip=True)
            if txt:
                texts.append(txt)
        sib = sib.find_next_sibling()
    return texts


def extract_effect_lines(html: str) -> List[str]:
    def normalize(txt: str) -> str:
        return re.sub(r'\s+', ' ', txt).strip()

    def should_keep(txt: str) -> bool:
        low = txt.lower()
        if not txt:
            return False
        if any(p.search(low) for p in DROP_PATTERNS):
            return False
        if 'patch' in low:
            return False
        if 'resistance' in low and any(k in low for k in ['immunity', 'robustness', 'focus', 'vitality', 'poise']):
            return False
        if re.fullmatch(r'[\d\W]+', txt):
            return False
        return MECH_PAT.search(txt) is not None or len(txt.split()) >= 3

    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()

    main = soup.find(id='wiki-content-block') or soup.find(id='wiki-content') or soup
    collected: List[str] = []

    infobox = main.find('div', id='infobox') or main.find('div', class_='infobox')
    if infobox:
        for line in infobox.select('.lineleft'):
            td = line.find_parent('td')
            context = (td.get_text(' ', strip=True).lower() if td else '').lower()
            if any(skip in context for skip in ['dmg negation', 'damage negation', 'resistance', 'immunity', 'robustness', 'focus', 'vitality', 'poise', 'wgt.', 'weight']):
                continue
            txt = normalize(line.get_text(' ', strip=True))
            if txt:
                collected.append(txt)

    for div in main.select('div.table-responsive'):
        if div.find_parent(id='infobox') or div.find_parent(class_='infobox'):
            continue
        div.decompose()

    headers = main.find_all(re.compile('^h[1-4]$'))
    for h in headers:
        title = h.get_text(strip=True).lower()
        if any(ex in title for ex in EXCLUDE_SECTION_KEYS):
            continue
        if any(key in title for key in SECTION_KEYS):
            collected.extend(gather_section_text(h))

    if not collected:
        for li in main.find_all('li'):
            txt = normalize(li.get_text(' ', strip=True))
            if txt and MECH_PAT.search(txt):
                collected.append(txt)

    if not collected:
        for elem in main.find_all(['p', 'li']):
            txt = normalize(elem.get_text(' ', strip=True))
            if txt and len(txt) > 30:
                collected.append(txt)
            if len(collected) >= 8:
                break

    filtered = []
    skip_craft_list = False
    for t in collected:
        txt = normalize(t)
        if not txt:
            continue
        if re.search(r'can be used to craft the following items', txt, re.I):
            skip_craft_list = True
            continue
        if skip_craft_list:
            if ':' in txt or len(txt.split()) > 6:
                skip_craft_list = False
                continue
            else:
                continue
        if txt.count('♦') > 3:
            continue
        if len(txt) > 400:
            continue
        if should_keep(txt):
            filtered.append(txt)

    seen = set()
    out = []
    for t in filtered:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
        if len(out) >= 25:
            break
    return out


def scrape_item(name: str) -> Dict:
    html = fetch_html(name)
    if not html:
        return {'name': name, 'effect_lines': [], 'error': 'fetch_failed'}
    lines = extract_effect_lines(html)
    return {'name': name, 'effect_lines': lines}


def process_file(path: Path, dest: Path):
    html = path.read_text(encoding='utf-8', errors='ignore')
    lines = extract_effect_lines(html)
    dest.write_text(json.dumps({'file': path.name, 'effect_lines': lines}, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', action='append', help='item names to fetch/scrape')
    parser.add_argument('--file', action='append', help='html files to process from disk')
    parser.add_argument('--dir', help='directory of html files to process')
    parser.add_argument('--out-dir', default='.', help='where to write *_filtered.json')
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.name:
        results = [scrape_item(n) for n in args.name]
        print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.file:
        for f in args.file:
            p = Path(f)
            dest = out_dir / f"{p.stem}_filtered.json"
            process_file(p, dest)
            print(f"wrote {dest}")
    if args.dir:
        for p in Path(args.dir).glob('*.html'):
            dest = out_dir / f"{p.stem}_filtered.json"
            process_file(p, dest)
        print(f"processed dir {args.dir}")

if __name__ == '__main__':
    main()
