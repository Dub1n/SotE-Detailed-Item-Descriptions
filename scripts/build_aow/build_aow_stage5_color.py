import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Colors mirror Stage 4.
PHYSICAL_COLOR = "#F395C4"
MAGIC_COLOR = "#57DBCE"
FIRE_COLOR = "#F48C25"
LIGHTNING_COLOR = "#FFE033"
HOLY_COLOR = "#F5EB89"
HEADER_COLOR = "#C0B194"
POISON_COLOR = "#40BF40"
ROT_COLOR = "#EF7676"
BLEED_COLOR = "#C84343"
FROST_COLOR = "#9DD7FB"
MADNESS_COLOR = "#EEAA2B"
SLEEP_COLOR = "#A698F4"
DEATH_COLOR = "#A17945"

FP_COLOR = "#b9bec3ff"
FP_CHARGED_COLOR = "#dabd9dff"
CHARGED_COLOR = "#ffd59aff"
DIVIDER_COLOR = "#e0ded9ff"
FP_DIVIDER_COLOR = "#d9e0e0ff"


def wrap_segment(text: str, color: str | None) -> str:
    if not text or not color:
        return text
    return f'<font color="{color}">{text}</font>'


def merge_segments(segments: List[Tuple[str | None, str]]) -> str:
    merged: List[Tuple[str | None, str]] = []
    for color, text in segments:
        if not text:
            continue
        if merged and merged[-1][0] == color:
            merged[-1] = (color, merged[-1][1] + text)
        else:
            merged.append((color, text))
    parts: List[str] = []
    for color, text in merged:
        parts.append(wrap_segment(text, color) if color else text)
    return "".join(parts)


def color_for_damage_type(label: str) -> str | None:
    l = label.lower()
    if l in {"standard", "physical", "phys", "pierce", "slash", "strike", "blunt"}:
        return PHYSICAL_COLOR
    if l == "magic":
        return MAGIC_COLOR
    if l == "fire":
        return FIRE_COLOR
    if l in {"lightning", "ltng"}:
        return LIGHTNING_COLOR
    if l == "holy":
        return HOLY_COLOR
    return None


def color_for_status(label: str) -> str | None:
    l = label.lower()
    if l in {"blood loss", "hemorrhage"}:
        return BLEED_COLOR
    if l in {"poison", "deadly poison"}:
        return POISON_COLOR
    if l in {"scarlet rot", "rot"}:
        return ROT_COLOR
    if l in {"frost", "frostbite"}:
        return FROST_COLOR
    if l in {"madness"}:
        return MADNESS_COLOR
    if l in {"sleep", "eternal sleep"}:
        return SLEEP_COLOR
    if l in {"death blight"}:
        return DEATH_COLOR
    return None


def colorize_fp_block(block: str) -> str:
    # block includes brackets
    content = block[1:-1]
    if "|" not in content:
        return wrap_segment(block, FP_COLOR)
    left_raw, right_raw = content.split("|", 1)
    left = left_raw.strip()
    right = right_raw.strip()
    if left == "0" and right == "0":
        return wrap_segment(block, FP_COLOR)
    segments = [
        (FP_COLOR, "["),
        (FP_COLOR, left_raw),
        (FP_DIVIDER_COLOR, "|"),
        (FP_CHARGED_COLOR, right_raw),
        (FP_COLOR, "]"),
    ]
    return merge_segments(segments)


def colorize_main_part(part: str) -> str:
    if "|" not in part:
        return part
    left, right = part.split("|", 1)
    divider = wrap_segment("|", DIVIDER_COLOR)
    right_colored = wrap_segment(right, CHARGED_COLOR)
    return f"{left}{divider}{right_colored}"


def colorize_numeric_payload(payload: str) -> str:
    if not payload:
        return payload
    tokens = re.split(r"(\[[^\]]*\])", payload)
    # Move trailing spaces before non-numeric brackets (e.g., [AR]) onto the bracket token
    # so they are not captured inside colored numeric spans.
    for idx in range(len(tokens) - 1):
        tok = tokens[idx]
        next_tok = tokens[idx + 1]
        if (
            next_tok
            and next_tok.startswith("[")
            and next_tok.endswith("]")
            and not re.search(r"\d", next_tok)
        ):
            stripped = tok.rstrip(" ")
            if stripped != tok:
                trailing = tok[len(stripped) :]
                tokens[idx] = stripped
                tokens[idx + 1] = trailing + next_tok
    pieces: List[str] = []
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("[") and tok.endswith("]") and re.search(r"\d", tok):
            pieces.append(colorize_fp_block(tok))
        else:
            pieces.append(colorize_main_part(tok))
    return "".join(pieces)


def color_label(label: str) -> str:
    base_label = label.strip()
    color: str | None = None
    if base_label.lower().startswith("stance"):
        color = HEADER_COLOR
    elif "(%)" in base_label:
        status_name = base_label.replace("(%)", "").strip()
        color = color_for_status(status_name)
    else:
        color = color_for_damage_type(base_label)
    text = f"{base_label}:"
    return wrap_segment(text, color) if color else text


def colorize_line(line: str) -> str:
    m = re.match(r"^(?P<indent>\s*)(?P<label>[^:]+):\s*(?P<body>.*)$", line)
    if not m:
        return line
    indent = m.group("indent")
    label = m.group("label")
    body = m.group("body")
    colored_label = color_label(label)
    colored_body = colorize_numeric_payload(body)
    return f"{indent}{colored_label} {colored_body}"


def colorize_md_lines(lines: List[str]) -> List[str]:
    return [colorize_line(line) for line in lines]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Colorize plain AoW-data-5 markdown (Stage 5 output without colors)."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("work/aow_pipeline/AoW-data-5.md"),
        help="Path to plain AoW-data-5.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("work/aow_pipeline/AoW-data-5-colored.md"),
        help="Path to write colored markdown",
    )
    args = parser.parse_args()

    lines = args.input.read_text(encoding="utf-8").splitlines()
    colored_lines = colorize_md_lines(lines)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(colored_lines) + "\n", encoding="utf-8")
    print(f"Wrote colored markdown to {args.output}")


if __name__ == "__main__":
    main()
