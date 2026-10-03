import re
import tomllib
from pathlib import Path

from .contracts import Field


def load(path: Path) -> dict:
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    config["base_dir"] = path.resolve().parent
    fields = config.get("fields", [])
    if schema_file := config.get('schema_file'):
        with (config['base_dir'] / schema_file).open('rb') as stream:
            fields = tomllib.load(stream).get('fields', []) + fields
    if not fields:
        raise ValueError("At least one [[fields]] entry is required")
    parsed = [Field(**item) for item in fields]
    if len({f.name for f in parsed}) != len(parsed):
        raise ValueError("Field names must be unique")
    for f in parsed:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", f.name):
            raise ValueError("Field names must be snake_case")
        if f.kind not in {"number", "string", "boolean", "records"}:
            raise ValueError("Field kind must be number, string, boolean, or records")
        if type(f.allow_qualified) is not bool:
            raise ValueError('allow_qualified must be boolean')
        if f.kind == 'records':
            if not f.properties or 'name' not in f.properties:
                raise ValueError('Record fields require a name property')
            for key, spec in f.properties.items():
                if not re.fullmatch(r'[a-z][a-z0-9_]*', key) or not isinstance(spec, dict):
                    raise ValueError('Invalid record property')
                if spec.get('kind', 'string') not in {'number', 'string'}:
                    raise ValueError('Record properties must be scalar strings or numbers')
            if f.properties['name'].get('kind', 'string') != 'string':
                raise ValueError('Record name must be string')
        if f.kind != "number" and f.unit:
            raise ValueError("Only numeric fields can have units")
        if f.list_separator or f.exclude_terms:
            if f.kind != 'string' or not f.list_separator:
                raise ValueError('List filtering requires a string field and list_separator')
            if not isinstance(f.exclude_terms, list) or any(not isinstance(x, str) or not x.strip() for x in f.exclude_terms):
                raise ValueError('exclude_terms must be nonempty strings')
    if not config.get("sources") or not config.get("models"):
        raise ValueError("At least one source and model are required")
    if not config.get("entity", "").strip():
        raise ValueError("entity is required; use one entity per job")
    for model in config["models"]:
        if model.get("provider") not in {"rules", "ollama", "chat_completions", "anthropic"}:
            raise ValueError("Unknown model provider")
        if model["provider"] != "rules" and not model.get("model"):
            raise ValueError("Remote/local LLM adapters require a model name")
    for source in config["sources"]:
        if source.get("kind") not in {"fixture", "html", "wikipedia", "pdf"}:
            raise ValueError("Unknown source kind")
        required = {"fixture": "path", "html": "url", "pdf": "url", "wikipedia": "title"}[source["kind"]]
        if not isinstance(source.get(required), str) or not source[required].strip():
            raise ValueError(f"Source {source['kind']} requires {required}")
    limits = config.setdefault("limits", {})
    for key, default in {"max_documents": 10, "max_model_calls": 20,
                         "max_chars": 30000, "max_output_tokens": 2048}.items():
        value = limits.setdefault(key, default)
        if type(value) is not int or value <= 0:
            raise ValueError(f"limits.{key} must be a positive integer")
    for key, default in {"chunk_chars": 12000, "chunk_overlap": 300,
                         "field_batch_size": 12, "max_source_bytes": 12000000}.items():
        value = limits.setdefault(key, default)
        if type(value) is not int or value < (0 if key == 'chunk_overlap' else 1):
            raise ValueError(f"Invalid {key}")
    if limits["chunk_overlap"] >= limits["chunk_chars"]:
        raise ValueError("chunk_overlap must be smaller than chunk_chars")
    discovery = config.setdefault("discovery", {})
    for key, default in {"max_pages": 0, "max_candidates": 40}.items():
        value = discovery.setdefault(key, default)
        if type(value) is not int or value < 0:
            raise ValueError(f"Invalid discovery {key}")
    config["field_specs"] = parsed
    return config
