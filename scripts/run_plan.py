import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import List, Dict

PLAN_PATH = Path('work/batch_plan.json')


def launch(entry: Dict, config: str, model: str, output_dir: str):
    cmd = [
        '.venv/bin/python', 'scripts/run_batches.py',
        '--batch-size', str(entry.get('batch_size', entry.get('limit', 100))),
        '--start', str(entry['start']),
        '--limit', str(entry['limit']),
        '--category', entry['category'],
        '--batch-prefix', entry.get('prefix', ''),
        '--config', config,
        '--model', model,
        '--output-dir', output_dir,
        # Always skip ids already produced into the ready folder to avoid duplicate work.
        '--processed-glob', 'work/responses/ready/*_response*.json',
        '--execute'
    ]
    if entry.get('save_raw', False):
        cmd.append('--save-raw')
    return subprocess.Popen(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', default=str(PLAN_PATH))
    ap.add_argument('--config', default='../codex-mcp-wrapper/wrapper.toml')
    ap.add_argument('--model', default='gpt-5.1-codex-mini')
    ap.add_argument('--concurrency', type=int, default=5)
    ap.add_argument('--output-dir', default='work/responses/pending')
    args = ap.parse_args()

    plan = json.load(open(args.plan, encoding='utf-8'))
    procs: List[subprocess.Popen] = []
    idx = 0
    try:
        while idx < len(plan) or procs:
            while idx < len(plan) and len(procs) < args.concurrency:
                entry = plan[idx]
                p = launch(entry, args.config, args.model, args.output_dir)
                procs.append(p)
                idx += 1
            # wait for any to finish
            done = []
            for p in procs:
                ret = p.poll()
                if ret is not None:
                    done.append(p)
            for p in done:
                procs.remove(p)
            if not done:
                time.sleep(1)
        print("Plan run complete")
    except KeyboardInterrupt:
        print("KeyboardInterrupt received; terminating running batches...")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        raise

if __name__ == '__main__':
    main()
