"""Small, opt-in live check. Key stays in process memory; never saved in reports."""
import getpass
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datascr.access import NoRedirect
from datascr.contracts import CollectionError, Document, Field
from datascr.models import JsonModel
from datascr.validation import validate

BASE = "https://api.commandcode.ai/provider/v1"


def main():
    key = os.environ.get("COMMANDCODE_API_KEY") or getpass.getpass("Command Code key (hidden): ")
    os.environ["COMMANDCODE_API_KEY"] = key
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(BASE + "/models", headers={"Authorization": "Bearer " + key,
                                                "User-Agent": "DataScr/0.1", "Accept": "application/json"})
    report = {"tested_at": datetime.now(timezone.utc).isoformat(), "base_url": BASE, "tests": []}
    try:
        with opener.open(request, timeout=30) as response:
            catalog = json.load(response)
        models = catalog.get("data", [])
        report["catalog_status"] = "ok"
        report["catalog"] = [{"id": m["id"], "supported_endpoints": m.get("supported_endpoints")} for m in models]
        print(f"Catalog: {len(models)} models", flush=True)
        selected = []
        for family in ("deepseek/", "qwen/", "moonshotai/", "z-ai/", "minimax/"):
            matches = [m["id"] for m in models if m["id"].lower().startswith(family)
                       and any("chat/completions" in route for route in m.get("supported_endpoints", []))]
            if matches:
                selected.append(sorted(matches, key=lambda name: ("flash" not in name, name))[0])
            if len(selected) == 3:
                break
        if not selected:
            report["selection_error"] = "No matching models advertising chat/completions"
        if len(sys.argv) > 1:
            selected = [m for m in sys.argv[1:4] if m in {entry["id"] for entry in models}]
        document = Document("fixture:live-probe", "Synthetic Example ship. Length: 100 m. Crew: 120 persons.")
        fields = [Field("length", "Overall length", unit="m"), Field("crew", "Crew count")]
        for model_id in selected:
            print("Testing " + model_id, flush=True)
            started = time.monotonic()
            model = JsonModel({"provider": "chat_completions", "base_url": BASE,
                               "model": model_id, "api_key_env": "COMMANDCODE_API_KEY"}, "Synthetic Example ship", 1024)
            item = {"model": model_id}
            try:
                claims = model.extract(document, fields)
                accepted = [validate(c, fields, document) for c in claims]
                values = {c["field"]: c["value"] for c in accepted}
                item.update(status="passed" if values == {"length": 100, "crew": 120} else "unexpected_values", claims=accepted)
            except (CollectionError, ValueError) as exc:
                item.update(status="failed", error=str(exc).replace(key, "[REDACTED]"))
                if isinstance(exc.__cause__, HTTPError):
                    item["http_status"] = exc.__cause__.code
                    item["response_body"] = exc.__cause__.read(2000).decode("utf-8", errors="replace").replace(key, "[REDACTED]")
            item["seconds"] = round(time.monotonic() - started, 2)
            report["tests"].append(item)
            print(json.dumps(item), flush=True)
            if item.get("http_status") in {401, 403, 429}:
                report["stopped_reason"] = "Authentication/access/rate-limit response; remaining calls skipped"
                break
    except HTTPError as exc:
        report["catalog_status"] = exc.code
        body = exc.read(2000).decode("utf-8", errors="replace").replace(key, "[REDACTED]")
        report["catalog_error"] = body
        print(json.dumps({"http_status": exc.code, "body": body}), flush=True)
    except (URLError, OSError, ValueError) as exc:
        report["catalog_status"] = "transport_or_json_error"
        report["catalog_error"] = str(exc).replace(key, "[REDACTED]")
        print(report["catalog_error"], flush=True)
    finally:
        os.environ.pop("COMMANDCODE_API_KEY", None)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = Path(f"output/commandcode-probe-{stamp}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Report: " + str(target.resolve()), flush=True)


if __name__ == "__main__":
    main()
