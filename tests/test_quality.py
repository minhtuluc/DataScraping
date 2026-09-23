import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from datascr.config import load
from datascr.contracts import CollectionError, Document, Field
from datascr.models import RulesModel
from datascr.pipeline import run
from datascr.sources import WikipediaSource, html_text
from datascr.validation import validate
from datascr.numbers import parse_number

ROOT = Path(__file__).resolve().parents[1]


class QualityTests(unittest.TestCase):
    def test_configured_equipment_filter_keeps_weapons_and_audits_exclusions(self):
        field = load(ROOT / 'examples/asahi-mimo.toml')['field_specs'][-1]
        value = '高性能２０ミリ機関砲×２、ＶＬＳ装置、多機能レーダー、水上艦用ソーナーシステム'
        quote = '主要兵装 : ' + value
        accepted = validate({'field': 'armament', 'value': value, 'quote': quote},
                            [field], Document('fixture', quote, 'ja'))
        self.assertEqual(accepted['value'], '高性能２０ミリ機関砲×２、ＶＬＳ装置')
        self.assertEqual(accepted['raw_value'], value)
        self.assertEqual(accepted['excluded_segments'], ['多機能レーダー', '水上艦用ソーナーシステム'])

    def test_string_value_must_be_supported_by_quote(self):
        field = Field('name', 'name', kind='string')
        with self.assertRaises(ValueError):
            validate({'field': 'name', 'value': 'Invented', 'quote': 'Name: Real'},
                     [field], Document('fixture', 'Name: Real'))

    def test_japanese_fullwidth_decimal_evidence(self):
        for quote, value in [('長さ １５０．５ｍ', 150.5), ('幅 １８．３ｍ', 18.3)]:
            with self.subTest(quote=quote):
                result = validate({'field': 'length', 'value': value, 'unit': 'm', 'quote': quote},
                                  [Field('length', '', unit='m')], Document('fixture', quote, 'ja'))
                self.assertEqual(result['value'], value)
                self.assertEqual(result['quote'], quote)

    def test_wrong_unit_in_real_quote_rejected(self):
        with self.assertRaises(ValueError):
            validate({'field': 'length', 'value': 100, 'unit': 'ft', 'quote': 'Length: 100 m'},
                     [Field('length', '', unit='m')], Document('fixture', 'Length: 100 m', 'en'))

    def test_attached_unit_and_scientific_notation(self):
        for quote, value in [('Length: 100m', 100), ('Length: 1e-10 m', 1e-10)]:
            self.assertEqual(validate({'field': 'length', 'value': value, 'unit': 'm', 'quote': quote},
                             [Field('length', '', unit='m')], Document('fixture', quote, 'en'))['value'], value)

    def test_inequality_cannot_become_exact_value(self):
        for quote, language in [('Speed: over 30 knots', 'en'), ('Tốc độ: hơn 30 knots', 'vi'),
                                ('Speed: >30 knots', 'en'), ('Speed: 30+ knots', 'en')]:
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                validate({'field': 'speed', 'value': 30, 'unit': 'knots', 'quote': quote},
                         [Field('speed', '', unit='kn')], Document('fixture', quote, language))

    def test_ambiguous_and_malformed_numbers_rejected(self):
        for value, language in [('1,234', 'und'), ('1.234', 'und'), ('12,34.5', 'en'),
                                ('1e999', 'en'), (True, 'en'), ('1 23', 'fr')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_number(value, language)

    def test_partial_translation_is_visible_in_pipeline(self):
        config = load(ROOT / 'examples/custom-demo.toml')
        source = Mock()
        source.issues = [{'language': 'vi', 'message': 'Source HTTP 403'}]
        source.collect.return_value = [Document('fixture', 'mass: 2 kg', 'en')]
        with patch('datascr.pipeline.make_source', return_value=source):
            result = run(config)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['issues'][0]['language'], 'vi')
        self.assertEqual(result['fields']['mass']['value'], 2)

    def test_html_table_keeps_label_value_and_inline_units(self):
        text = html_text('<table><tr><th>Length</th><td><b>100</b> <span>m</span></td></tr>'
                         '<tr><th>Crew</th><td>120</td></tr></table>')
        self.assertEqual(text, 'Length: 100 m\nCrew: 120')
        claims = RulesModel().extract(Document('fixture', text, 'en'), [Field('length', '', unit='m')])
        self.assertEqual(claims[0]['value'], 100)

    def test_locale_numbers_and_ranges(self):
        for language, raw, expected in [('en', '1,234.5 m', 1234.5), ('vi', '1.234,5 m', 1234.5),
                                        ('fr', '1\u202f234,5 m', 1234.5), ('en', '120-140 m', {'min': 120, 'max': 140}),
                                        ('en', '-5--2 m', {'min': -5, 'max': -2})]:
            with self.subTest(raw=raw):
                doc = Document('fixture', 'Length: ' + raw, language)
                fields = [Field('length', '', unit='m')]
                claims = RulesModel().extract(doc, fields)
                self.assertEqual(len(claims), 1)
                self.assertEqual(validate(claims[0], fields, doc)['value'], expected)

    def test_wrong_number_in_real_quote_rejected(self):
        with self.assertRaises(ValueError):
            validate({'field': 'length', 'value': 900, 'unit': 'm', 'quote': 'Length: 100 m'},
                     [Field('length', '', unit='m')], Document('fixture', 'Length: 100 m', 'en'))

    def test_locale_numeric_string_and_unit_alias(self):
        claim = {'field': 'length', 'value': '1.234,5', 'unit': ' mét ', 'quote': 'Chiều dài: 1.234,5 mét'}
        result = validate(claim, [Field('length', '', unit='m')], Document('fixture', claim['quote'], 'vi'))
        self.assertEqual(result['value'], 1234.5)
        self.assertEqual(result['raw_value'], '1.234,5')

    def test_tiny_valid_quantity_not_rounded_to_zero(self):
        claim = {'field': 'length', 'value': 0.0000000001, 'unit': 'm', 'quote': 'Length: 0.0000000001 m'}
        self.assertGreater(validate(claim, [Field('length', '', unit='m')], Document('fixture', claim['quote'], 'en'))['value'], 0)

    def test_one_translation_failure_preserves_others(self):
        access = Mock()
        access.get.side_effect = [json.dumps({'parse': {'revid': 1, 'text': '<p>Length: 100 m</p>',
            'langlinks': [{'lang': 'vi', 'title': 'Tàu'}, {'lang': 'fr', 'title': 'Navire'}]}}),
            CollectionError('Source HTTP 403'), json.dumps({'parse': {'revid': 3, 'text': '<p>Longueur: 100 m</p>'}})]
        source = WikipediaSource(access)
        docs = source.collect({'title': 'Example', 'languages': ['vi', 'fr']})
        self.assertEqual([d.language for d in docs], ['en', 'fr'])
        self.assertEqual(source.issues[0]['language'], 'vi')

    def test_duplicate_source_not_fetched_twice(self):
        config = load(ROOT / 'examples/custom-demo.toml')
        config['sources'].append(dict(config['sources'][0]))
        source = Mock()
        source.issues = []
        source.collect.return_value = [Document('fixture', 'mass: 2 kg', 'en')]
        with patch('datascr.pipeline.make_source', return_value=source):
            result = run(config)
        self.assertEqual(source.collect.call_count, 1)
        self.assertEqual(result['model_calls'], 1)


if __name__ == '__main__':
    unittest.main()
