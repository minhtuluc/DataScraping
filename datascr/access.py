"""Single HTTP GET boundary for source collection; never follows redirects."""

import ipaddress
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from .contracts import CollectionError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_url(url: str, hosts: list[str]) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment
            or parsed.hostname not in hosts):
        raise CollectionError("URL must use HTTPS and an exact approved host")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise CollectionError("Source DNS lookup failed") from exc
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise CollectionError("Private/reserved source addresses are forbidden")
    return f"https://{parsed.hostname}"


class Access:
    def __init__(self, policy: dict):
        self.policy = policy
        self.agent = policy.get("user_agent", "DataScrBot/0.1")
        self.interval = float(policy.get("min_interval_seconds", 2))
        if self.interval < 1:
            raise ValueError("min_interval_seconds must be at least 1")
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.last: dict[str, float] = {}
        self.robots: dict[str, RobotFileParser] = {}
        self.stopped: set[str] = set()

    def _request(self, url: str, origin: str, interval: float) -> str:
        wait = interval - (time.monotonic() - self.last.get(origin, 0))
        if wait > 0:
            time.sleep(wait)
        self.last[origin] = time.monotonic()
        req = Request(url, headers={"User-Agent": self.agent, "Accept-Encoding": "identity"})
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise CollectionError("Source response exceeds 2 MB")
                return raw.decode(response.headers.get_content_charset() or "utf-8")
        except HTTPError as exc:
            self.stopped.add(origin)
            # Stop the origin for this run, including 429 / Retry-After. No retries.
            raise CollectionError(f"Source HTTP {exc.code}; origin stopped for this run") from exc
        except (URLError, OSError, UnicodeError) as exc:
            self.stopped.add(origin)
            raise CollectionError("Source transport/decoding failed; origin stopped") from exc

    def get(self, url: str) -> str:
        if self.policy.get("approved") is not True or not self.policy.get("permission_note", "").strip():
            raise CollectionError("Source requires approved=true and a permission_note after review")
        origin = public_url(url, self.policy.get("allowed_hosts", []))
        if origin in self.stopped:
            raise CollectionError("Origin already stopped for this run")
        if origin not in self.robots:
            # Conservative: even 404/unavailable robots stops collection.
            body = self._request(origin + "/robots.txt", origin, self.interval)
            if "<html" in body.lower():
                self.stopped.add(origin)
                raise CollectionError("Unexpected HTML at robots.txt")
            robot = RobotFileParser()
            robot.parse(body.splitlines())
            self.robots[origin] = robot
        robot = self.robots[origin]
        if not robot.can_fetch(self.agent, url):
            raise CollectionError("robots.txt disallows this URL")
        interval = max(self.interval, robot.crawl_delay(self.agent) or 0)
        rate = robot.request_rate(self.agent)
        if rate:
            interval = max(interval, rate.seconds / rate.requests)
        text = self._request(url, origin, interval)
        if any(marker in text.lower() for marker in (
            "cf-chl-", "g-recaptcha", "hcaptcha", "verify you are human", "access denied")):
            self.stopped.add(origin)
            raise CollectionError("Possible access challenge; origin stopped")
        return text
