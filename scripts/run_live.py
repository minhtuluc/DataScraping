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
    parser.add_argument('--corpus', type=Path, help='Extract saved source documents without fetching again')
    parser.add_argument('--fields', nargs='+', help='Extract only selected fields; keep the complete output schema')
    parser.add_argument('--document-urls', nargs='+', help='Select document URLs from a saved corpus')
    args = parser.parse_args()
    config = load(args.config)
    if args.fields:
        if set(args.fields) - {f.name for f in config['field_specs']}:
            parser.error('Unknown field selection')
        config['extract_fields'] = args.fields
    if args.document_urls and not args.corpus:
        parser.error('--document-urls requires --corpus')
    temporary_keys = []
    try:
        for model in config['models']:
            name = model.get('api_key_env')
            if name and not os.environ.get(name):
                os.environ[name] = getpass.getpass(f'{name} (hidden): ')
                temporary_keys.append(name)
        print('Collecting configured sources and extracting with MiMo; no automatic retries.', flush=True)
        start = time.monotonic()
        corpus = json.loads(args.corpus.read_text(encoding='utf-8')) if args.corpus else None
        if args.document_urls:
            corpus['documents'] = [d for d in corpus['documents'] if d['url'] in args.document_urls]
            if not corpus['documents']:
                parser.error('No matching documents')
        def progress(partial, calls):
            args.output.mkdir(parents=True, exist_ok=True)
            checkpoint = args.output / (partial['run_id'] + '.checkpoint.json')
            temporary = checkpoint.with_suffix('.tmp')
            temporary.write_text(json.dumps({**partial, 'model_calls': calls},
                                           ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(checkpoint)
            last = partial['attempts'][-1]
            print(f"Call {calls}: " + last.get('error', f"{len(last.get('raw_claims', []))} raw claims"), flush=True)
        result = run(config, corpus=corpus, progress=progress)
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
