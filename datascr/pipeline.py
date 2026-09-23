import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from .access import Access
from .contracts import CollectionError
from .models import PROMPT_VERSION, make_model
from .sources import make_source
from .validation import resolve, validate


def run(config: dict) -> dict:
    fields = config["field_specs"]
    limits = config["limits"]
    result = {"run_id": uuid4().hex, "entity": config["entity"],
              "profile": config.get("profile", "custom"), "prompt_version": PROMPT_VERSION,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "schema": [asdict(f) for f in fields],
              "documents": [], "attempts": [], "issues": []}
    access = Access(config.get("access", {}))
    documents = []
    seen = set()
    requested = set()
    for index, source in enumerate(config["sources"]):
        signature = json.dumps(source, sort_keys=True, ensure_ascii=False)
        if signature in requested:
            continue
        requested.add(signature)
        remaining = limits["max_documents"] - len(documents)
        if remaining <= 0:
            result["issues"].append({"stage": "budget", "message": "Document limit reached"})
            break
        # Wikipedia source has one base document plus selected translations.
        source = dict(source)
        if source["kind"] == "wikipedia":
            languages = list(dict.fromkeys(source.get("languages", [])))
            languages = [l for l in languages if l != source.get("language", "en")]
            if len(languages) > remaining - 1:
                result["issues"].append({"stage": "budget", "message": "Language selection limited by document budget"})
            source["languages"] = languages[:remaining - 1]
        try:
            adapter = make_source(source["kind"], config["base_dir"], access)
            collected = adapter.collect(source)
            for issue in getattr(adapter, 'issues', []):
                result['issues'].append({'stage': 'source', 'source_index': index, **issue})
            for document in collected:
                key = (document.url, document.revision)
                if key not in seen:
                    seen.add(key)
                    documents.append(document)
        except (CollectionError, OSError, ValueError, KeyError, TypeError) as exc:
            result["issues"].append({"stage": "source", "source_index": index, "message": str(exc)})
    claims = []
    calls = 0
    for document in documents:
        doc_id = hashlib.sha256((document.url + "\n" + document.text).encode()).hexdigest()
        result["documents"].append({**asdict(document), "id": doc_id,
                                    "sha256": hashlib.sha256(document.text.encode()).hexdigest()})
        if len(document.text) > limits["max_chars"]:
            result["issues"].append({"stage": "budget", "document": doc_id,
                                      "message": "Document too long; skipped without silent truncation"})
            continue
        for model_config in config["models"]:
            if calls >= limits["max_model_calls"]:
                result["issues"].append({"stage": "budget", "message": "Model call limit reached"})
                break
            model = make_model(model_config, config["entity"], limits["max_output_tokens"])
            calls += 1
            attempt = {"document": doc_id, "model": model.name}
            result["attempts"].append(attempt)
            try:
                raw = model.extract(document, fields)
                attempt["raw_claims"] = raw
                for claim in raw:
                    try:
                        accepted = validate(claim, fields, document)
                        accepted.update(document=doc_id, source_url=document.url,
                                        language=document.language, revision=document.revision, model=model.name)
                        claims.append(accepted)
                    except ValueError as exc:
                        result["issues"].append({"stage": "validation", "document": doc_id,
                                                  "model": model.name, "message": str(exc)})
            except CollectionError as exc:
                attempt["error"] = str(exc)
                result["issues"].append({"stage": "model", "model": model.name, "message": str(exc)})
    result["fields"] = resolve(claims, fields)
    result["model_calls"] = calls
    result["status"] = "failed" if not claims else "partial" if result["issues"] else "completed"
    result["needs_review"] = any(f["status"] != "observed" for f in result["fields"].values())
    return result
