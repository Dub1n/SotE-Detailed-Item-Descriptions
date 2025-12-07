import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEM_CSV = ROOT / "PARAM/EquipParamGem.csv"
BEHAVIOR_CSV = ROOT / "PARAM/BehaviorParam_PC.csv"
SWORDARTS_CSV = ROOT / "PARAM/SwordArtsParam.csv"
OUTPUT = ROOT / "docs/skill_names_from_gem_and_behavior.txt"


def load_gem_names() -> set[str]:
    names: set[str] = set()
    with GEM_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            if name.lower().startswith("ash of war"):
                name = name.split(":", 1)[1].strip() if ":" in name else name[len("ash of war") :].strip()
            if not name or name.lower().startswith("test gem"):
                continue
            names.add(name)
    return names


def load_behavior_names() -> set[str]:
    names: set[str] = set()
    with BEHAVIOR_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if "[AOW]" not in name:
                continue
            skill = name.split("]", 1)[1].strip() if "]" in name else name.replace("[AOW]", "").strip()
            if skill:
                names.add(skill)
    return names


def load_swordarts_names() -> set[str]:
    names: set[str] = set()
    with SWORDARTS_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name or name == "%null%":
                continue
            names.add(name)
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="Build unified AoW skill list from Gem and Behavior.")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Output path for combined skill list.")
    args = parser.parse_args()

    gem_names = load_gem_names()
    behavior_names = load_behavior_names()
    swordarts_names = load_swordarts_names()
    combined = sorted(gem_names | behavior_names | swordarts_names)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(combined), encoding="utf-8")

    print(f"Wrote {len(combined)} skills to {args.output}")
    only_gem = gem_names - behavior_names
    only_behavior = behavior_names - gem_names
    only_swordarts = swordarts_names - gem_names - behavior_names
    if only_gem:
        print(f"Gem-only ({len(only_gem)}): {', '.join(sorted(only_gem))}")
    if only_behavior:
        print(f"Behavior-only ({len(only_behavior)}): {', '.join(sorted(only_behavior))}")
    if only_swordarts:
        print(f"SwordArts-only ({len(only_swordarts)}): {', '.join(sorted(only_swordarts))}")


if __name__ == "__main__":
    main()
