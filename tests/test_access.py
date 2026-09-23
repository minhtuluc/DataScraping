import unittest
from unittest.mock import patch, Mock
from urllib.error import HTTPError

from datascr.access import Access, NoRedirect, public_url
from datascr.contracts import CollectionError


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.access = Access({"approved": True, "permission_note": "Owned test site",
                              "allowed_hosts": ["example.org"]})

    def test_unapproved_never_requests(self):
        self.access.policy["approved"] = False
        with patch.object(self.access, "_request") as request, self.assertRaises(CollectionError):
            self.access.get("https://example.org/page")
        request.assert_not_called()

    def test_robots_disallow_prevents_page_fetch(self):
        with patch("datascr.access.public_url", return_value="https://example.org"), patch.object(
            self.access, "_request", return_value="User-agent: *\nDisallow: /private"
        ) as request:
            with self.assertRaises(CollectionError):
                self.access.get("https://example.org/private")
        self.assertEqual(request.call_count, 1)

    def test_robot_interval_and_cache(self):
        with patch("datascr.access.public_url", return_value="https://example.org"), patch.object(
            self.access, "_request", side_effect=["User-agent: *\nAllow: /\nCrawl-delay: 5", "page", "page2"]
        ) as request:
            self.access.get("https://example.org/a")
            self.access.get("https://example.org/b")
        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args.args[2], 5)

    def test_challenge_stops_origin(self):
        with patch("datascr.access.public_url", return_value="https://example.org"), patch.object(
            self.access, "_request", side_effect=["User-agent: *\nAllow: /", "Verify you are human"]
        ) as request:
            for _ in range(2):
                with self.assertRaises(CollectionError):
                    self.access.get("https://example.org/page")
        self.assertEqual(request.call_count, 2)

    def test_http_failures_stop_origin_without_retry(self):
        for status in [301, 401, 403, 404, 429, 503]:
            with self.subTest(status=status):
                self.access.stopped.clear()
                self.access.opener = Mock()
                self.access.opener.open.side_effect = HTTPError("https://example.org", status, "Blocked", {}, None)
                with patch("datascr.access.time.sleep"), self.assertRaises(CollectionError):
                    self.access._request("https://example.org", "https://example.org", 2)
                self.assertIn("https://example.org", self.access.stopped)
                self.assertEqual(self.access.opener.open.call_count, 1)

    def test_redirects_are_not_followed(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "http://localhost"))

    def test_unavailable_robots_prevents_content_request(self):
        with patch("datascr.access.public_url", return_value="https://example.org"), patch.object(
            self.access, "_request", side_effect=CollectionError("Source HTTP 404")
        ) as request:
            with self.assertRaises(CollectionError):
                self.access.get("https://example.org/page")
        self.assertEqual(request.call_count, 1)

    def test_pacing_waits_before_next_request(self):
        self.access.last["https://example.org"] = 10
        self.access.opener = Mock()
        self.access.opener.open.side_effect = HTTPError("https://example.org", 403, "", {}, None)
        with patch("datascr.access.time.monotonic", return_value=11), patch("datascr.access.time.sleep") as sleep:
            with self.assertRaises(CollectionError):
                self.access._request("https://example.org", "https://example.org", 5)
        sleep.assert_called_once_with(4)

    def test_private_dns_and_nonapproved_hosts_rejected(self):
        with patch("datascr.access.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(CollectionError):
                public_url("https://example.org", ["example.org"])
        for url in ["http://example.org", "https://evil.org", "https://user:pass@example.org",
                    "https://example.org:8080", "file:///etc/passwd"]:
            with self.subTest(url=url), self.assertRaises(CollectionError):
                public_url(url, ["example.org"])


if __name__ == "__main__":
    unittest.main()
