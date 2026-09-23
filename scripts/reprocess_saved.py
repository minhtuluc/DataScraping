"""Revalidate saved raw model claims after validator changes; makes no network calls."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datascr.contracts import Document, Field
from datascr.config import load
from datascr.validation import resolve, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--config', type=Path, help='Apply the current configured field schema to saved raw claims')
    args = parser.parse_args()
    original = json.loads(args.source.read_text(encoding='utf-8'))
    fields = load(args.config)['field_specs'] if args.config else [Field(**spec) for spec in original['schema']]
    documents = {d['id']: Document(d['url'], d['text'], d['language'], d.get('revision'))
                 for d in original['documents']}
    claims, issues = [], []
    for attempt in original['attempts']:
        doc = documents[attempt['document']]
        for raw in attempt.get('raw_claims', []):
            try:
                claim = validate(raw, fields, doc)
                claim.update(document=attempt['document'], source_url=doc.url,
                             language=doc.language, revision=doc.revision, model=attempt['model'])
                claims.append(claim)
            except ValueError as exc:
                issues.append({'model': attempt['model'], 'field': raw.get('field'), 'message': str(exc)})
    reviewed = dict(original)
    reviewed['schema'] = [vars(field) for field in fields]
    reviewed['fields'] = resolve(claims, fields)
    reviewed['issues'] = [issue for issue in original['issues'] if issue.get('stage') != 'validation'] + issues
    reviewed['status'] = 'failed' if not claims else 'partial' if reviewed['issues'] else 'completed'
    reviewed['needs_review'] = any(item['status'] != 'observed' for item in reviewed['fields'].values())
    reviewed['review'] = {'reprocessed_from': str(args.source.resolve()),
                          'filter_config': str(args.config.resolve()) if args.config else None,
                          'note': 'Raw source text and original model claims preserved; model was not called again.'}
    target = args.source.with_name(args.source.stem + ('.filtered.json' if args.config else '.reviewed.json'))
    target.write_text(json.dumps(reviewed, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'output': str(target.resolve()), 'accepted_claims': len(claims),
                      'issues': issues, 'field_status': {k: v['status'] for k, v in reviewed['fields'].items()}},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
