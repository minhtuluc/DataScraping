"""Bounded source discovery, chunked extraction, provenance and coverage reporting."""
import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from .access import Access
from .contracts import CollectionError, Document
from .models import PROMPT_VERSION, make_model
from .sources import make_source
from .validation import resolve, validate


def chunks(document, size, overlap):
    start = 0
    while start < len(document.text):
        end = min(start + size, len(document.text))
        if end < len(document.text):
            boundary = document.text.rfind('\n', start + size // 2, end)
            if boundary > start:
                end = boundary + 1
        yield start, end, replace(document, text=document.text[start:end])
        if end == len(document.text):
            break
        start = max(start + 1, end - overlap)


def collect(config, result):
    limits = config['limits']
    access = Access({**config.get('access', {}), 'max_source_bytes': limits.get('max_source_bytes', 12000000)})
    documents, requested, fingerprints = [], set(), set()
    queue = [(s, False) for s in config['sources']]
    scheduled = {s['url'] for s in config['sources'] if 'url' in s}
    discovery = config.get('discovery', {})
    max_pages = discovery.get('max_pages', 0)
    candidate_limit = discovery.get('max_candidates', 40)
    terms = [x.casefold() for x in discovery.get('terms', [])]
    followed, candidates_seen = 0, set()
    while queue:
        source, discovered = queue.pop(0)
        key = source.get('url') or json.dumps(source, sort_keys=True)
        if key in requested:
            continue
        if len(documents) >= limits['max_documents']:
            result['issues'].append({'stage': 'budget', 'message': 'Document limit reached',
                                     'remaining_sources': len(queue) + 1})
            break
        requested.add(key)
        remaining = limits['max_documents'] - len(documents)
        source = dict(source)
        if source['kind'] == 'wikipedia':
            languages = list(dict.fromkeys(source.get('languages', [])))
            languages = [l for l in languages if l != source.get('language', 'en')]
            if len(languages) > remaining - 1:
                result['issues'].append({'stage': 'budget', 'message': 'Language selection limited by document budget'})
            source['languages'] = languages[:remaining - 1]
        attempt = {'source': source, 'discovered': discovered, 'status': 'pending'}
        result['source_attempts'].append(attempt)
        try:
            adapter = make_source(source['kind'], config['base_dir'], access)
            collected = adapter.collect(source)
            for issue in getattr(adapter, 'issues', []):
                result['issues'].append({'stage': 'source', 'source_url': source.get('url'), **issue})
            attempt['status'], attempt['documents'] = 'collected', len(collected)
            for document in collected:
                fingerprint = hashlib.sha256(document.text.encode()).hexdigest()
                if fingerprint in fingerprints:
                    attempt.setdefault('duplicates', []).append(document.url)
                    continue
                if len(documents) >= limits['max_documents']:
                    result['issues'].append({'stage': 'budget', 'message': 'PDF/source documents exceed document limit'})
                    break
                fingerprints.add(fingerprint)
                metadata = {k: source[k] for k in ('publisher', 'source_type', 'scope', 'attribution', 'published_at') if k in source}
                metadata['retrieved_at'] = datetime.now(timezone.utc).isoformat()
                document.metadata.update(metadata)
                documents.append(document)
                if not max_pages or not terms:
                    continue
                for link in document.metadata.get('links', []):
                    url = link['url']
                    path = urlsplit(url).path.lower()
                    if url in scheduled or any(path.endswith(ext) for ext in (
                            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.mp4', '.mp3', '.zip', '.css', '.js')):
                        continue
                    if url in candidates_seen or len(candidates_seen) >= candidate_limit:
                        continue
                    label = (link.get('text', '') + ' ' + url).casefold()
                    if not any(t in label for t in terms):
                        continue
                    candidates_seen.add(url)
                    host = urlsplit(url).hostname
                    eligible = host in access.policy.get('allowed_hosts', []) and host == urlsplit(document.url).hostname
                    candidate = {'url': url, 'found_on': document.url, 'anchor': link.get('text', ''),
                                 'status': 'queued' if eligible and followed < max_pages else 'review_required'}
                    result['discovery'].append(candidate)
                    if candidate['status'] == 'queued':
                        scheduled.add(url)
                        # Never inherit a ship scope to a different document without review.
                        queue.append(({'kind': 'pdf' if urlsplit(url).path.lower().endswith('.pdf') else 'html',
                                       'url': url, 'language': document.language,
                                       'publisher': metadata.get('publisher', host),
                                       'source_type': metadata.get('source_type', 'discovered')}, True))
                        followed += 1
        except (CollectionError, OSError, ValueError, KeyError, TypeError) as exc:
            attempt.update(status='failed', error=str(exc))
            result['issues'].append({'stage': 'source', 'source_url': source.get('url'), 'message': str(exc)})
    return documents


def coverage(result, fields):
    missing, conflicts, scoped = [], [], []
    groups = {}
    for spec in fields:
        status = result['fields'][spec.name]['status']
        group = groups.setdefault(spec.group, {'total': 0, 'with_evidence': 0})
        group['total'] += 1
        group['with_evidence'] += status != 'missing'
        if status == 'missing':
            missing.append(spec.name)
        elif status == 'conflict':
            conflicts.append(spec.name)
        elif status == 'scoped':
            scoped.append(spec.name)
    publishers = {d['metadata'].get('publisher', urlsplit(d['url']).hostname or d['url'])
                  for d in result['documents']}
    return {'total_fields': len(fields), 'fields_with_evidence': len(fields) - len(missing),
            'missing_fields': missing, 'conflicting_fields': conflicts, 'scoped_fields': scoped,
            'groups': groups, 'documents': len(result['documents']), 'publishers': sorted(publishers),
            'publisher_count': len(publishers),
            'accepted_claims': sum(len(f['candidates']) for f in result['fields'].values()),
            'rejected_claims': len(result['rejected_claims']),
            'follow_up_queries': [result['entity'] + ' ' + name.replace('_', ' ') for name in missing]}


def run(config, corpus=None, collect_only=False, progress=None):
    fields, limits = config['field_specs'], config['limits']
    extraction_fields = [f for f in fields if f.name in config.get('extract_fields', [f.name for f in fields])]
    if not extraction_fields:
        raise ValueError('No configured extraction fields selected')
    result = {'run_id': uuid4().hex, 'entity': config['entity'], 'profile': config.get('profile', 'custom'),
              'prompt_version': PROMPT_VERSION, 'created_at': datetime.now(timezone.utc).isoformat(),
              'schema': [asdict(f) for f in fields], 'documents': [], 'attempts': [], 'issues': [],
              'source_attempts': [], 'discovery': [], 'rejected_claims': []}
    if corpus is not None:
        if corpus.get('entity') != config['entity']:
            raise ValueError('Corpus entity differs from requested entity')
        documents = [Document(d['url'], d['text'], d.get('language', 'und'),
                              d.get('revision'), d.get('metadata', {})) for d in corpus['documents']]
        result['source_attempts'] = corpus.get('source_attempts', [])
        result['discovery'] = corpus.get('discovery', [])
        result['issues'] = [i for i in corpus.get('issues', []) if i.get('stage') == 'source']
        result['replayed_from'] = corpus.get('run_id')
        if len(documents) > limits['max_documents']:
            result['issues'].append({'stage': 'budget', 'message': 'Corpus exceeds document budget'})
            documents = documents[:limits['max_documents']]
    else:
        documents = collect(config, result)
    claims, calls, seen_claims = [], 0, set()
    for document in documents:
        doc_id = hashlib.sha256((document.url + '\n' + document.text).encode()).hexdigest()
        result['documents'].append({**asdict(document), 'id': doc_id,
                                   'sha256': hashlib.sha256(document.text.encode()).hexdigest()})
        if collect_only:
            continue
        if len(document.text) > limits['max_chars']:
            result['issues'].append({'stage': 'budget', 'document': doc_id,
                                     'message': 'Document exceeds total character budget; extraction skipped'})
            continue
        for start, end, chunk in chunks(document, limits.get('chunk_chars', 12000), limits.get('chunk_overlap', 300)):
            batch_size = limits.get('field_batch_size', len(fields))
            for offset in range(0, len(extraction_fields), batch_size):
                batch = extraction_fields[offset:offset + batch_size]
                for model_config in config['models']:
                    if calls >= limits['max_model_calls']:
                        if not any(i.get('message') == 'Model call limit reached' for i in result['issues']):
                            result['issues'].append({'stage': 'budget', 'message': 'Model call limit reached'})
                        break
                    model = make_model(model_config, config['entity'], limits['max_output_tokens'])
                    calls += 1
                    attempt = {'document': doc_id, 'model': model.name,
                               'chunk_start': start, 'chunk_end': end, 'fields': [f.name for f in batch]}
                    result['attempts'].append(attempt)
                    try:
                        raw = model.extract(chunk, batch)
                        attempt['raw_claims'] = raw
                        for claim in raw:
                            try:
                                accepted = validate(claim, batch, chunk)
                                accepted.update(document=doc_id, source_url=document.url, language=document.language,
                                                revision=document.revision, model=model.name,
                                                page=document.metadata.get('page'),
                                                publisher=document.metadata.get('publisher', urlsplit(document.url).hostname),
                                                source_scope=document.metadata.get('scope', ''),
                                                source_type=document.metadata.get('source_type', 'unspecified'))
                                for issue in accepted.get('rejected_properties', []):
                                    result['rejected_claims'].append({'document': doc_id, 'field': accepted['field'], **issue})
                                signature = json.dumps(accepted, sort_keys=True, ensure_ascii=False)
                                if signature not in seen_claims:
                                    seen_claims.add(signature)
                                    claims.append(accepted)
                            except ValueError as exc:
                                rejected = {'stage': 'validation', 'document': doc_id, 'model': model.name,
                                            'field': claim.get('field') if isinstance(claim, dict) else None,
                                            'message': str(exc), 'raw_claim': claim}
                                result['rejected_claims'].append(rejected)
                                result['issues'].append({k: v for k, v in rejected.items() if k != 'raw_claim'})
                    except CollectionError as exc:
                        attempt['error'] = str(exc)
                        result['issues'].append({'stage': 'model', 'model': model.name, 'message': str(exc)})
                    if progress:
                        progress(result, calls)
    result['fields'] = resolve(claims, fields)
    result['model_calls'] = calls
    result['coverage'] = coverage(result, fields)
    result['needs_review'] = any(f['status'] != 'observed' for f in result['fields'].values())
    if collect_only:
        result['status'] = 'collected' if documents else 'failed'
    else:
        result['status'] = 'failed' if not claims else 'partial' if result['issues'] or result['needs_review'] else 'completed'
    return result
