"""One direct model request, independent of source fetching and extraction."""
import getpass
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    key = os.environ.get("COMMANDCODE_API_KEY") or getpass.getpass("Command Code key (hidden): ")
    url = "https://api.commandcode.ai/provider/v1/chat/completions"
    payload = {"model": "xiaomi/mimo-v2.6-flash", "messages": [
        {"role": "user", "content": "Reply with only PONG."}], "max_tokens": 128, "stream": False}
    request = Request(url, data=json.dumps(payload).encode(), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "User-Agent": "DataScr/0.1"}, method="POST")
    report = {"tested_at": datetime.now(timezone.utc).isoformat(), "endpoint": url,
              "model": payload["model"], "request": payload, "wikipedia_requested": False}
    report["user_agent"] = request.get_header("User-agent", "Python-urllib default")
    started = time.monotonic()
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=45) as response:
            report["http_status"] = response.status
            report["response_body"] = response.read(16000).decode("utf-8", errors="replace").replace(key, "[REDACTED]")
    except HTTPError as exc:
        report["http_status"] = exc.code
        report["response_body"] = exc.read(4000).decode("utf-8", errors="replace").replace(key, "[REDACTED]")
        report["diagnostics"] = {k: exc.headers[k] for k in ("server", "cf-ray", "cf-error-type") if k in exc.headers}
    except (URLError, OSError) as exc:
        report["error"] = str(exc).replace(key, "[REDACTED]")
    report["seconds"] = round(time.monotonic() - started, 2)
    path = Path("output") / ("mimo-ping-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
    print("Report: " + str(path.resolve()), flush=True)


if __name__ == "__main__":
    main()
