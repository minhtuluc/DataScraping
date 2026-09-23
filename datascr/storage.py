import json
import sqlite3
from contextlib import closing
from pathlib import Path


def save(result: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    path = output / f"{result['run_id']}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    with closing(sqlite3.connect(output / "runs.sqlite3")) as database:
        with database:
            database.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, entity TEXT, status TEXT, payload TEXT)")
            database.execute("INSERT INTO runs VALUES (?, ?, ?, ?)",
                             (result["run_id"], result["entity"], result["status"], text))
