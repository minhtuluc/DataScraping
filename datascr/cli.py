import argparse
import json
import sys
from pathlib import Path

from .config import load
from .pipeline import run
from .storage import save


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evidence-first configurable data collection")
    parser.add_argument("command", choices=["check", "run"])
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output"))
    args = parser.parse_args(argv)
    try:
        config = load(args.config)
        if args.command == "check":
            print(f"Valid: {config['entity']} | {len(config['field_specs'])} fields | {len(config['models'])} models")
            return 0
        result = run(config)
        save(result, args.output)
        print(json.dumps({"status": result["status"], "needs_review": result["needs_review"],
                          "output": str((args.output / (result['run_id'] + '.json')).resolve()),
                          "issues": result["issues"]}, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "completed" else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Configuration/output error: {exc}", file=sys.stderr)
        return 1
