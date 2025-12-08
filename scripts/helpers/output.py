from pathlib import Path


LIGHT_BLUE = "\033[94m"
RESET = "\033[0m"


def format_path_for_console(path: Path, root: Path | None = None) -> str:
    """
    Render a path with the repo root stripped (if provided) and
    wrapped in a light-blue ANSI color for console output.
    """
    resolved = path.resolve()
    display = resolved.as_posix()
    if root:
        try:
            rel = resolved.relative_to(root.resolve())
            display = "/" + rel.as_posix()
        except ValueError:
            display = resolved.as_posix()
    return f"{LIGHT_BLUE}{display}{RESET}"
