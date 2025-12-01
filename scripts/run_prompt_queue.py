import argparse
import glob
import subprocess
import time
from pathlib import Path
from typing import List, Tuple
import tomllib

DEFAULT_PROMPT_GLOB = "work/prompts/reformat_ready/*.txt"


def collect_prompts(pattern: str, explicit_paths: List[str]) -> List[Path]:
    """Return sorted prompt file paths from explicit paths or a glob pattern."""
    paths: List[Path] = []
    if explicit_paths:
        for entry in explicit_paths:
            p = Path(entry)
            if p.is_dir():
                paths.extend(sorted(p.glob("*.txt")))
            elif p.is_file():
                paths.append(p)
            else:
                print(f"[skip] no such file/dir: {entry}")
    else:
        paths = [Path(p) for p in glob.glob(pattern)]

    seen = set()
    unique: List[Path] = []
    for p in paths:
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return sorted(unique)


def ensure_state_dir(config_path: Path) -> Path:
    """Ensure the codex-mcp-wrapper state directory exists."""
    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    state_dir = cfg.get("state_dir", "state")
    state_path = Path(state_dir)
    if not state_path.is_absolute():
        state_path = config_path.parent / state_path
    state_path.mkdir(parents=True, exist_ok=True)
    (state_path / "logs").mkdir(parents=True, exist_ok=True)
    return state_path


def launch(prompt_path: Path, config: Path, model: str, log_errors: bool) -> subprocess.Popen:
    """Start a codex-mcp-wrapper chat for the given prompt file."""
    prompt_text = prompt_path.read_text(encoding="utf-8")
    cmd = [
        "codex-mcp-wrapper",
        "chat",
        prompt_text,
        "--config",
        str(config),
        "--transport",
        "streamable-http",
        "--port",
        "0",
        "--light",
        "--",
        "--model",
        model,
    ]
    stderr_target = subprocess.PIPE if log_errors else subprocess.DEVNULL
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=stderr_target, text=True)


def main():
    ap = argparse.ArgumentParser(description="Run prompt files directly with concurrent Codex agents (no output collection).")
    ap.add_argument("--prompt-glob", default=DEFAULT_PROMPT_GLOB, help="Glob for prompt files to run (sorted) when no paths are provided.")
    ap.add_argument("--config", default="../codex-mcp-wrapper/wrapper.toml", help="codex-mcp-wrapper config path.")
    ap.add_argument("--model", default="gpt-5.1-codex-mini", help="Model name for codex-mcp-wrapper.")
    ap.add_argument("--concurrency", type=int, default=5, help="Number of concurrent agents.")
    ap.add_argument("--dry-run", action="store_true", help="List prompts without launching agents.")
    ap.add_argument("--log-errors", action="store_true", help="Print stderr for prompts that exit non-zero.")
    ap.add_argument("paths", nargs="*", help="Prompt file(s) or directories; overrides --prompt-glob when provided.")
    args = ap.parse_args()

    config_path = Path(args.config)
    ensure_state_dir(config_path)

    prompts = collect_prompts(args.prompt_glob, args.paths)
    if not prompts:
        print(f"No prompts found for pattern: {args.prompt_glob}")
        return

    if args.dry_run:
        for p in prompts:
            print(f"[dry-run] {p}")
        print(f"Total prompts: {len(prompts)}")
        return

    procs: List[Tuple[subprocess.Popen, Path]] = []
    idx = 0

    try:
        while idx < len(prompts) or procs:
            while idx < len(prompts) and len(procs) < args.concurrency:
                prompt_path = prompts[idx]
                proc = launch(prompt_path, Path(args.config), args.model, args.log_errors)
                procs.append((proc, prompt_path))
                idx += 1
                print(f"[start] {prompt_path.name}")

            done = []
            for proc, prompt_path in procs:
                ret = proc.poll()
                if ret is None:
                    continue
                if args.log_errors and ret != 0 and proc.stderr is not None:
                    _out, err = proc.communicate()
                    err_msg = (err or "").strip()
                    if err_msg:
                        print(f"[fail] {prompt_path.name} exit {ret}: {err_msg}")
                    else:
                        print(f"[fail] {prompt_path.name} exit {ret}")
                else:
                    print(f"[done] {prompt_path.name} exit {ret}")
                done.append((proc, prompt_path))

            for entry in done:
                procs.remove(entry)

            if not done:
                time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupted; terminating running agents...")
        for proc, _ in procs:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc, _ in procs:
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
        raise

    print("All prompts completed.")


if __name__ == "__main__":
    main()
