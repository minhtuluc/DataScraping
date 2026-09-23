"""Run one configured collection job; prompt for a key without writing it to disk."""
import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datascr.config import load
from datascr.pipeline import run
from datascr.storage import save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = load(args.config)
    temporary_keys = []
    try:
        for model in config['models']:
            name = model.get('api_key_env')
            if name and not os.environ.get(name):
                os.environ[name] = getpass.getpass(f'{name} (hidden): ')
                temporary_keys.append(name)
        print('Collecting configured sources and extracting with MiMo; no automatic retries.', flush=True)
        start = time.monotonic()
        result = run(config)
        result['elapsed_seconds'] = round(time.monotonic() - start, 2)
        save(result, args.output)
        print(json.dumps({'run_id': result['run_id'], 'status': result['status'],
                          'documents': len(result['documents']), 'model_calls': result['model_calls'],
                          'seconds': result['elapsed_seconds'], 'issues': result['issues'],
                          'output': str((args.output / (result['run_id'] + '.json')).resolve())},
                         ensure_ascii=True, indent=2), flush=True)
    finally:
        for name in temporary_keys:
            os.environ.pop(name, None)


if __name__ == '__main__':
    main()
