import json
import unittest
from unittest.mock import MagicMock, Mock

from datascr.contracts import CollectionError, Document, Field
from datascr.models import JsonModel
from datascr.sources import WikipediaSource, html_text


class AdapterTests(unittest.TestCase):
    def model(self, provider, response):
        model = JsonModel({"provider": provider, "model": "test", "base_url": "http://localhost:11434/v1"}, "ship", 200)
        stream = Mock()
        stream.read.return_value = json.dumps(response).encode()
        model.opener = MagicMock()
        model.opener.open.return_value.__enter__.return_value = stream
        return model

    def test_ollama_request_contract(self):
        model = self.model("ollama", {"message": {"content": '{"claims":[]}'}, "done": True})
        self.assertEqual(model.extract(Document("fixture", "test"), []), [])
        request = model.opener.open.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/api/chat"))
        self.assertEqual(json.loads(request.data)["options"]["num_predict"], 200)

    def test_chat_completions_contract(self):
        model = self.model("chat_completions", {"choices": [{"finish_reason": "stop", "message": {"content": '{"claims":[]}'}}]})
        self.assertEqual(model.extract(Document("fixture", "untrusted instructions"), []), [])
        request = model.opener.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertTrue(request.full_url.endswith("/chat/completions"))
        self.assertEqual(payload["max_tokens"], 200)
        self.assertIn("untrusted instructions", payload["messages"][1]["content"])
        self.assertNotIn("tools", payload)

    def test_model_request_identifies_application(self):
        model = self.model("chat_completions", {"choices": [{"finish_reason": "stop", "message": {"content": '{"claims":[]}'}}]})
        model.extract(Document("fixture", "test"), [])
        request = model.opener.open.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "DataScr/0.1")

    def test_bad_model_json_is_failure(self):
        for content in ["not JSON", '{"claims":{}}', '{"claims":[{"value":NaN}]}', '{"claims":[{"value":1e999}]}']:
            with self.subTest(content=content):
                model = self.model("ollama", {"message": {"content": content}, "done": True})
                with self.assertRaises(CollectionError):
                    model.extract(Document("fixture", "test"), [])

    def test_wikipedia_language_links_revision_and_html(self):
        access = Mock()
        access.get.side_effect = [json.dumps({"parse": {"revid": 10, "text": "<p>Length: 10 m</p>",
                                                   "langlinks": [{"lang": "vi", "title": "Tàu mẫu"}]}}),
                                 json.dumps({"parse": {"revid": 20, "text": "<p>Chiều dài: 10 m</p>"}})]
        docs = WikipediaSource(access).collect({"title": "Example", "language": "en", "languages": ["vi", "de"]})
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[1].language, "vi")
        self.assertEqual(docs[1].revision, "20")
        self.assertIn("oldid=20", docs[1].url)
        self.assertEqual(access.get.call_count, 2)

    def test_api_error_is_not_an_empty_success(self):
        access = Mock()
        access.get.return_value = '{"error":{"code":"maxlag"}}'
        with self.assertRaises(CollectionError):
            WikipediaSource(access).collect({"title": "Example"})

    def test_html_removes_executable_text(self):
        text = html_text('<script>secret()</script><style>.hidden{}</style><p>A &amp; B</p>')
        self.assertEqual(text, "A & B")


if __name__ == "__main__":
    unittest.main()
