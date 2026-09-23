import json
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from datascr.config import load
from datascr.contracts import Document, Field
from datascr.models import RulesModel
from datascr.pipeline import run
from datascr.storage import save
from datascr.validation import resolve, validate

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_demo_provenance_normalization_conflict_and_storage(self):
        result = run(load(ROOT / "examples/warships-demo.toml"))
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["needs_review"])
        self.assertEqual(result["fields"]["length"]["value"], 100)
        self.assertEqual(result["fields"]["displacement"]["value"], 5000)
        self.assertEqual(result["fields"]["speed"]["status"], "conflict")
        self.assertIsNone(result["fields"]["speed"]["value"])
        self.assertEqual(result["fields"]["crew"]["value"], {"min": 120, "max": 140})
        self.assertEqual(len(result["fields"]["length"]["candidates"]), 2)
        self.assertIn("quote", result["fields"]["length"]["candidates"][0])
        with tempfile.TemporaryDirectory() as directory:
            save(result, Path(directory))
            data = json.loads((Path(directory) / (result["run_id"] + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(data["run_id"], result["run_id"])
            import sqlite3
            with closing(sqlite3.connect(Path(directory) / "runs.sqlite3")) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM runs").fetchone()[0], 1)

    def test_new_domain_needs_no_code_changes(self):
        result = run(load(ROOT / "examples/custom-demo.toml"))
        self.assertEqual(result["fields"]["available"]["value"], True)
        self.assertEqual(result["fields"]["mass"]["value"], 2)
        self.assertFalse(result["needs_review"])

    def test_budget_and_duplicate_sources(self):
        config = load(ROOT / "examples/warships-demo.toml")
        config["sources"].insert(0, config["sources"][0])
        config["limits"]["max_model_calls"] = 1
        result = run(config)
        self.assertEqual(len(result["documents"]), 2)
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["status"], "partial")

    def test_multiple_models_keep_separate_provenance(self):
        config = load(ROOT / "examples/custom-demo.toml")
        config["models"].append({"provider": "ollama", "model": "test"})
        class Other(RulesModel):
            name = "test:other"
        with patch("datascr.pipeline.make_model", side_effect=[RulesModel(), Other()]):
            result = run(config)
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual({c["model"] for c in result["fields"]["mass"]["candidates"]},
                         {"rules:labelled-lines-v1", "test:other"})

    def test_oversized_document_is_reported(self):
        config = load(ROOT / "examples/custom-demo.toml")
        config["limits"]["max_chars"] = 1
        result = run(config)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["model_calls"], 0)

    def test_failed_source_does_not_hide_successful_source(self):
        config = load(ROOT / "examples/custom-demo.toml")
        config["sources"].append({"kind": "fixture", "path": "missing.txt"})
        result = run(config)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["fields"]["available"]["value"])

    def test_live_requires_explicit_source_review(self):
        result = run(load(ROOT / "examples/warships-wikipedia.toml"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("approved=true", result["issues"][0]["message"])


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.doc = Document("https://example.org", "Length: 10 ft")
        self.fields = [Field("length", "Hull length", unit="m")]
        self.claim = {"field": "length", "value": 10, "unit": "ft", "quote": "Length: 10 ft"}

    def test_conversion(self):
        self.assertAlmostEqual(validate(self.claim, self.fields, self.doc)["value"], 3.048)

    def test_rejects_bad_quote_unknown_field_boolean_nan_and_wrong_unit(self):
        for change in [{"quote": "Length: 30 ft"}, {"field": "unknown"}, {"value": True},
                       {"value": float("nan")}, {"unit": "knots"}, {"unit": "tons"},
                       {"value": {"min": 20, "max": 10}}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate({**self.claim, **change}, self.fields, self.doc)

    def test_missing_is_not_zero(self):
        result = resolve([], self.fields)["length"]
        self.assertEqual(result["status"], "missing")
        self.assertIsNone(result["value"])


if __name__ == "__main__":
    unittest.main()
