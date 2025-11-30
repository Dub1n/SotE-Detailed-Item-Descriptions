#!/usr/bin/env python3
"""
Scan response JSON files for mechanical strings that should be colour tagged and
optionally apply the tags. Default is dry-run; pass --apply to write changes.

Intended for the work/responses/ready/*.json files. By default it only touches
the `info` field; use --fields to target other fields (e.g. caption, effect).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

# Colour codes follow formatting_rules.md
HEADER = "#C0B194"
GOLD = "#E0B985"
PHYSICAL = "#F395C4"
MAGIC = "#57DBCE"
FIRE = "#F48C25"
LIGHTNING = "#FFE033"
HOLY = "#F5EB89"
FROST = "#9DD7FB"
POISON = "#40BF40"
ROT = "#EF7676"
BLEED = "#C84343"
MADNESS_COLOR = "#EEAA2B"
SLEEP_COLOR = "#A698F4"
DEATH_COLOR = "#A17945"

FONT_SPAN_RE = re.compile(r"<font[^>]*?>.*?</font>", re.IGNORECASE | re.DOTALL)
COLOR_ATTR_RE = re.compile(r'color="(#?[0-9a-fA-F]{6})"', re.IGNORECASE)
FONT_CLOSE = "</font>"


@dataclass(frozen=True)
class TagRule:
    pattern: re.Pattern[str]
    color: str


@dataclass(frozen=True)
class MergeRule:
    pattern: re.Pattern[str]
    color: str


@dataclass(frozen=True)
class WarnRule:
    pattern: re.Pattern[str]
    color: Optional[str]
    search_all: bool = False


class TokenCollector:
    """Track tokens we changed without double-counting."""

    def __init__(self) -> None:
        self._seen: set[Tuple[str, Optional[str]]] = set()
        self.tokens: List[Tuple[str, Optional[str]]] = []

    def add(self, token: str, color: Optional[str]) -> None:
        token_clean = token.strip()
        key = (token_clean.lower(), color.lower() if color else None)
        if key in self._seen:
            return
        self._seen.add(key)
        self.tokens.append((token_clean, color))

    def extend(self, tokens: Iterable[Tuple[str, Optional[str]]]) -> None:
        for tok, col in tokens:
            self.add(tok, col)


def is_capitalized(text: str) -> bool:
    for ch in text:
        if ch.isalpha():
            return ch.isupper()
    return False


def strip_font_tags(segment: str) -> str:
    return re.sub(r"</?font[^>]*>", "", segment)


def ensure_font_color(open_tag: str, color: str) -> str:
    if COLOR_ATTR_RE.search(open_tag):
        return COLOR_ATTR_RE.sub(f'color="{color}"', open_tag, count=1)
    tag = open_tag.rstrip(">")
    return f'{tag} color="{color}">'


GENERAL_PATTERN_DEFS: Sequence[Tuple[str, str, int]] = (
    # attack power stays uncoloured in the original mod; do not tag it
    (r"\bmaximum hp\b", GOLD, re.IGNORECASE),
    (r"\bhp restoration\b", GOLD, re.IGNORECASE),
    (r"\bmaximum fp\b", GOLD, re.IGNORECASE),
    (r"\bfp restoration\b", GOLD, re.IGNORECASE),
    (r"\bfp\b", GOLD, re.IGNORECASE),
    (r"\bstamina recovery speed\b", GOLD, re.IGNORECASE),
    (r"\bstamina regeneration\b", GOLD, re.IGNORECASE),
    (r"\bStamina\b", GOLD, 0),
    (r"\bstamina\b", GOLD, re.IGNORECASE),
    (r"\bstance damage(?:\s+received)?\b", HEADER, re.IGNORECASE),
    (r"\bpoise damage(?:\s+received)?\b", GOLD, re.IGNORECASE),
    (r"\bpoise\b", GOLD, re.IGNORECASE),
    (r"\brobustness\b", GOLD, re.IGNORECASE),
    (r"\bfocus\b", GOLD, re.IGNORECASE),
    (r"\bvigor\b", GOLD, re.IGNORECASE),
    (r"\bmind\b", GOLD, re.IGNORECASE),
    (r"\bendurance\b", GOLD, re.IGNORECASE),
    (r"\bstrength\b", GOLD, re.IGNORECASE),
    (r"\bdexterity\b", GOLD, re.IGNORECASE),
    (r"\bintelligence\b", GOLD, re.IGNORECASE),
    (r"\bfaith\b", GOLD, re.IGNORECASE),
    (r"\barcane\b", GOLD, re.IGNORECASE),
    (r"\bmagic damage negation\b", MAGIC, re.IGNORECASE),
    (r"\bphysical damage negation\b", PHYSICAL, re.IGNORECASE),
    (r"\bfire damage negation\b", FIRE, re.IGNORECASE),
    (r"\blightning damage negation\b", LIGHTNING, re.IGNORECASE),
    (r"\bholy damage negation\b", HOLY, re.IGNORECASE),
    (r"\b(?:base\s+)?physical damage\b", PHYSICAL, re.IGNORECASE),
    (r"\b(?:base\s+)?magic damage\b", MAGIC, re.IGNORECASE),
    (r"\b(?:base\s+)?fire damage\b", FIRE, re.IGNORECASE),
    (r"\b(?:base\s+)?lightning damage\b", LIGHTNING, re.IGNORECASE),
    (r"\b(?:base\s+)?holy damage\b", HOLY, re.IGNORECASE),
)

STATUS_PATTERN_DEFS: Sequence[Tuple[str, str, int]] = (
    (r"\bDeadly Poison\b", POISON, 0),
    (r"\bPoison\b", POISON, 0),
    (r"\bScarlet Rot\b", ROT, 0),
    (r"\bEternal Sleep\b", SLEEP_COLOR, 0),
    (r"\bSleep\b", SLEEP_COLOR, 0),
    (r"\bDeath Blight\b", DEATH_COLOR, 0),
    (r"frostbite", FROST, re.IGNORECASE),
    (r"\bHemorrhage\b", BLEED, 0),
    (r"\bMadness\b", MADNESS_COLOR, 0),
)

WARN_PATTERN_DEFS: Sequence[Tuple[str, int, Optional[str], bool]] = (
    (r"\bresistance\b", re.IGNORECASE, None, False),
    # standalone stance (not followed by damage) should be reviewed but not colored
    (r"\bstance\b(?!\s+damage)", re.IGNORECASE, HEADER, True),
    # lowercase status words that might be mis-capitalized in text
    (r"\bpoison\b", 0, POISON, False),
    (r"\bdeadly poison\b", 0, POISON, False),
    (r"\bscarlet rot\b", 0, ROT, False),
    (r"\bhemorrhage\b", 0, BLEED, False),
    (r"\bsleep\b", 0, SLEEP_COLOR, False),
    (r"\beternal sleep\b", 0, SLEEP_COLOR, False),
    (r"\bmadness\b", 0, MADNESS_COLOR, False),
    (r"\bdeath blight\b", 0, DEATH_COLOR, False),
)


def compile_tag_rules(
    defs: Sequence[Tuple[str, str, int]]
) -> Sequence[TagRule]:
    return tuple(TagRule(re.compile(pattern, flags=flags), color) for pattern, color, flags in defs)


GENERAL_RULES: Sequence[TagRule] = compile_tag_rules(GENERAL_PATTERN_DEFS)
STATUS_RULES: Sequence[TagRule] = compile_tag_rules(STATUS_PATTERN_DEFS)
WARN_RULES: Sequence[WarnRule] = tuple(
    WarnRule(re.compile(pattern, flags=flags), color, search_all)
    for pattern, flags, color, search_all in WARN_PATTERN_DEFS
)

MERGE_RULES: Sequence[MergeRule] = (
    MergeRule(
        re.compile(
            r'<font[^>]*?color="(?P<c>#[0-9a-fA-F]{6})"[^>]*>(?P<lead>stance)</font>\s+(?P<trail>damage(?:\s+received)?)',
            re.IGNORECASE,
        ),
        HEADER,
    ),
    MergeRule(
        re.compile(
            r'<font[^>]*?color="(?P<c>#[0-9a-fA-F]{6})"[^>]*>(?P<lead>poise)</font>\s+(?P<trail>damage(?:\s+received)?)',
            re.IGNORECASE,
        ),
        GOLD,
    ),
    MergeRule(
        re.compile(
            r'<font[^>]*?color="(?P<c>#[0-9a-fA-F]{6})"[^>]*>(?P<lead>stance)</font>\s+<font[^>]*?color="(?P<c2>#[0-9a-fA-F]{6})"[^>]*>(?P<trail>damage(?:\s+received)?)</font>',
            re.IGNORECASE,
        ),
        HEADER,
    ),
    MergeRule(
        re.compile(
            r'<font[^>]*?color="(?P<c>#[0-9a-fA-F]{6})"[^>]*>(?P<lead>poise)</font>\s+<font[^>]*?color="(?P<c2>#[0-9a-fA-F]{6})"[^>]*>(?P<trail>damage(?:\s+received)?)</font>',
            re.IGNORECASE,
        ),
        GOLD,
    ),
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Suggest or apply colour tags for stat/element labels in item responses."
    )
    parser.add_argument("json_path", type=Path, help="Path to response JSON file.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes back to file (default: dry-run).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print before/after for each changed entry.",
    )
    parser.add_argument(
        "--fields",
        default="info",
        help="Comma-separated list of fields to scan (default: info).",
    )
    parser.add_argument(
        "--patterns",
        choices=["all", "status"],
        default="all",
        help="Which pattern set to use: all (default) or status-only.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Only normalize existing font colors; do not wrap bare tokens.",
    )
    parser.add_argument(
        "--capitalized-only",
        action="store_true",
        help="Only match tokens that start with a capital letter (skip all-lowercase).",
    )
    parser.add_argument(
        "--color-log",
        action="store_true",
        help="Colorize console output for matched tokens (ANSI).",
    )
    return parser.parse_args(argv)


def iter_plain_segments(text: str) -> List[Tuple[str, str]]:
    """Split text into plain text and font-tagged segments."""
    segments: List[Tuple[str, str]] = []
    last = 0
    for match in FONT_SPAN_RE.finditer(text):
        if match.start() > last:
            segments.append(("text", text[last : match.start()]))
        segments.append(("font", match.group(0)))
        last = match.end()
    if last < len(text):
        segments.append(("text", text[last:]))
    return segments


def get_tag_rules(mode: str) -> Sequence[TagRule]:
    if mode == "status":
        return STATUS_RULES
    return tuple(GENERAL_RULES) + tuple(STATUS_RULES)


def get_merge_rules(mode: str) -> Sequence[MergeRule]:
    if mode == "status":
        return ()
    return MERGE_RULES


def merge_split_tags(
    text: str,
    merge_rules: Sequence[MergeRule],
    collector: TokenCollector,
    capitalized_only: bool,
) -> str:
    updated = text
    for rule in merge_rules:
        def _merge(match: re.Match[str]) -> str:
            phrase = strip_font_tags(match.group(0)).strip()
            if not phrase:
                return match.group(0)
            if capitalized_only and not is_capitalized(phrase):
                return match.group(0)
            collector.add(phrase, rule.color)
            return f'<font color="{rule.color}">{phrase}</font>'

        updated = rule.pattern.sub(_merge, updated)
    return updated


def match_rule_for_content(content: str, rules: Sequence[TagRule]) -> Optional[TagRule]:
    for rule in rules:
        if rule.pattern.fullmatch(content):
            return rule
    return None


def normalize_font_colors(
    text: str,
    tag_rules: Sequence[TagRule],
    collector: TokenCollector,
    capitalized_only: bool,
) -> str:
    def _normalize(match: re.Match[str]) -> str:
        segment = match.group(0)
        open_end = segment.find(">") + 1
        if open_end <= 0 or not segment.endswith(FONT_CLOSE):
            return segment
        content = segment[open_end:-len(FONT_CLOSE)]
        content_clean = content.strip()
        if not content_clean:
            return segment
        rule = match_rule_for_content(content_clean, tag_rules)
        if not rule:
            return segment
        if capitalized_only and not is_capitalized(content_clean):
            return segment
        expected = rule.color.lower()
        current_tag = segment[:open_end]
        m = COLOR_ATTR_RE.search(current_tag)
        current = m.group(1).lower() if m else None
        if current == expected:
            return segment
        new_tag = ensure_font_color(current_tag, rule.color)
        collector.add(content_clean, rule.color)
        return f"{new_tag}{content}{FONT_CLOSE}"

    return FONT_SPAN_RE.sub(_normalize, text)


def apply_rule_to_plain_segment(
    segment: str,
    rule: TagRule,
    collector: TokenCollector,
    capitalized_only: bool,
) -> str:
    parts: List[str] = []
    i = 0
    for match in rule.pattern.finditer(segment):
        start, end = match.span()
        token = match.group(0)
        parts.append(segment[i:start])
        if capitalized_only and not is_capitalized(token):
            parts.append(token)
        else:
            collector.add(token, rule.color)
            parts.append(f'<font color="{rule.color}">{token}</font>')
        i = end
    parts.append(segment[i:])
    return "".join(parts)


def tag_outside_fonts(
    text: str,
    tag_rules: Sequence[TagRule],
    collector: TokenCollector,
    capitalized_only: bool,
) -> str:
    updated = text
    for rule in tag_rules:
        pieces: List[str] = []
        last = 0
        for match in FONT_SPAN_RE.finditer(updated):
            if match.start() > last:
                pieces.append(
                    apply_rule_to_plain_segment(
                        updated[last : match.start()], rule, collector, capitalized_only
                    )
                )
            pieces.append(match.group(0))
            last = match.end()
        if last < len(updated):
            pieces.append(
                apply_rule_to_plain_segment(
                    updated[last:], rule, collector, capitalized_only
                )
            )
        updated = "".join(pieces)
    return updated


def colourize_text(
    text: str,
    tag_rules: Sequence[TagRule],
    merge_rules: Sequence[MergeRule],
    fix_only: bool = False,
    capitalized_only: bool = False,
) -> Tuple[str, List[Tuple[str, Optional[str]]]]:
    collector = TokenCollector()
    merged = merge_split_tags(text, merge_rules, collector, capitalized_only) if merge_rules else text
    normalized = normalize_font_colors(merged, tag_rules, collector, capitalized_only)
    if fix_only:
        return normalized, collector.tokens
    tagged = tag_outside_fonts(normalized, tag_rules, collector, capitalized_only)
    return tagged, collector.tokens


def find_warnings(text: str) -> List[Tuple[str, Optional[str]]]:
    collector = TokenCollector()
    for rule in WARN_RULES:
        segments: List[str]
        if rule.search_all:
            segments = [strip_font_tags(text)]
        else:
            segments = [seg for kind, seg in iter_plain_segments(text) if kind == "text"]
        for segment in segments:
            for match in rule.pattern.finditer(segment):
                collector.add(match.group(0), rule.color)
    return collector.tokens


def render_tokens(tokens: Sequence[Tuple[str, Optional[str]]], color_log: bool) -> str:
    rendered: List[str] = []
    for tok, col in tokens:
        if color_log and col:
            r = int(col[1:3], 16)
            g = int(col[3:5], 16)
            b = int(col[5:7], 16)
            rendered.append(f"\x1b[38;2;{r};{g};{b}m{tok}\x1b[0m")
        else:
            rendered.append(tok)
    return ", ".join(rendered)


def process_file(
    path: Path,
    apply: bool,
    verbose: bool,
    fields: Iterable[str],
    tag_rules: Sequence[TagRule],
    merge_rules: Sequence[MergeRule],
    fix_only: bool,
    capitalized_only: bool,
    color_log: bool,
) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed_entries: List[Tuple[str, List[str], List[Tuple[str, Optional[str]]]]] = []
    warnings: List[Tuple[str, List[Tuple[str, Optional[str]]]]] = []
    fields = list({f.strip() for f in fields if f.strip()})

    for entry in data:
        entry_tokens = TokenCollector()
        entry_warnings = TokenCollector()
        changed_fields: List[str] = []
        for field in fields:
            val = entry.get(field)
            if not isinstance(val, str):
                continue
            new_val, tokens = colourize_text(
                val,
                tag_rules,
                merge_rules,
                fix_only=fix_only,
                capitalized_only=capitalized_only,
            )
            if new_val != val:
                entry[field] = new_val
                entry_tokens.extend(tokens)
                changed_fields.append(field)
                if verbose and not apply:
                    print(
                        f"- {entry.get('name', '(unnamed)')} (id {entry.get('id')}), field '{field}'"
                    )
                    print("  before:", val)
                    print("  after :", new_val)
                    if tokens:
                        print("  tokens:", render_tokens(tokens, color_log))
            entry_warnings.extend(find_warnings(new_val))
        if changed_fields:
            changed_entries.append(
                (entry.get("name"), changed_fields, entry_tokens.tokens)
            )
        if entry_warnings.tokens:
            warnings.append((entry.get("name"), entry_warnings.tokens))

    if apply and changed_entries:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    if apply:
        if changed_entries:
            print(f"{len(changed_entries)} entries changed.")
        else:
            print("No changes applied.")
    else:
        if not changed_entries:
            print("No changes suggested.")
        else:
            print(f"{len(changed_entries)} entries would change:")
            for name, fields_changed, tokens in changed_entries:
                fields_list = ", ".join(fields_changed)
                token_list = render_tokens(tokens, color_log)
                print(f"  - {name} [{fields_list}]: {token_list}")
            print("\nDry-run only. Re-run with --apply to write changes.")

    if warnings:
        print("\nWarnings (tokens found but not auto-coloured):")
        for name, tokens in warnings:
            print(f"  - {name}: {render_tokens(tokens, color_log)}")

    return len(changed_entries)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    if not args.json_path.exists():
        print(f"error: {args.json_path} does not exist", file=sys.stderr)
        return 1
    fields = args.fields.split(",") if args.fields else ["info"]
    tag_rules = get_tag_rules(args.patterns)
    merge_rules = get_merge_rules(args.patterns)
    process_file(
        args.json_path,
        args.apply,
        args.verbose,
        fields,
        tag_rules,
        merge_rules,
        args.fix,
        args.capitalized_only,
        args.color_log,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
