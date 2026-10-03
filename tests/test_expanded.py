import json
import unittest
from email.message import Message
from unittest.mock import MagicMock, patch
from datascr.access import Access
from datascr.contracts import Document, Field
from datascr.models import JsonModel
from datascr.pipeline import chunks
from datascr.validation import validate, resolve
from datascr.config import load
from datascr.pipeline import run
from pathlib import Path

class ExpandedTests(unittest.TestCase):
    def test_targeted_extraction_preserves_schema_and_reports_progress(self):
        config=load(Path(__file__).resolve().parents[1]/'examples/warships-demo.toml')
        config['extract_fields']=['length']
        calls=[]
        result=run(config,progress=lambda result,count:calls.append(count))
        self.assertEqual(calls,list(range(1,result['model_calls']+1)))
        self.assertTrue(all(a['fields']==['length'] for a in result['attempts']))
        self.assertEqual(result['fields']['speed']['status'],'missing')
        self.assertEqual(result['fields']['length']['value'],100)

    def test_two_distinct_numbers_do_not_prove_a_range(self):
        doc=Document('fixture:range','16 cells, space reserved for 32 cells','en')
        with self.assertRaises(ValueError):
            validate({'field':'cells','value':{'min':16,'max':32},'quote':doc.text},
                     [Field('cells','')],doc)

    def test_multiplicity_without_spaces(self):
        doc=Document('fixture:mounts','2x3 HOS-303','en')
        self.assertEqual(validate({'field':'tubes','value':3,'quote':'2x3'},
                                 [Field('tubes','')],doc)['value'],3)

    def test_unit_in_table_header(self):
        doc=Document('fixture:header','Length, m: 151.0','en')
        self.assertEqual(validate({'field':'length','value':151,'unit':'m','quote':doc.text},
                                 [Field('length','',unit='m')],doc)['value'],151)

    def test_scope_does_not_hide_same_class_conflict(self):
        claims = [{'field':'length','value':v,'source_scope':s} for v,s in
                  [(150.5,'class'),(151,'class'),(151,'DD-119')]]
        result = resolve(claims,[Field('length','',unit='m')])['length']
        self.assertEqual(result['status'],'conflict')
        self.assertEqual(len(result['scope_groups']),2)

    def test_qualified_japanese_crew(self):
        field=Field('crew','',unit='persons',allow_qualified=True)
        doc=Document('fixture:crew','乗員約２２０名','ja')
        claim={'field':'crew','value':220,'unit':'名','quote':doc.text,'qualifier':'approx'}
        self.assertEqual(validate(claim,[field],doc)['value'],{'amount':220,'qualifier':'approx'})
        claim.pop('qualifier')
        with self.assertRaises(ValueError): validate(claim,[field],doc)

    def test_unit_must_belong_to_quantity(self):
        doc=Document('fixture:units','2 engines deliver 30 MW','en')
        with self.assertRaises(ValueError):
            validate({'field':'power','value':2,'unit':'MW','quote':doc.text},
                     [Field('power','',unit='mw')],doc)

    def test_ps_conversion(self):
        doc=Document('fixture:power','馬力６２,５００ＰＳ','ja')
        value=validate({'field':'power','value':62500,'unit':'PS','quote':doc.text},
                       [Field('power','',unit='mw')],doc)['value']
        self.assertAlmostEqual(value,45.968671875)

    def test_records_keep_supported_properties_audit_rejected_count(self):
        doc=Document('fixture:weapons','Two 127 mm guns','en')
        field=Field('weapons','',kind='records',properties={
            'name':{'kind':'string'},'count':{'kind':'number'},
            'caliber':{'kind':'number','unit':'mm'}})
        claim={'field':'weapons','value':[{'quote':doc.text,'properties':{
            'name':{'value':'guns','quote':'guns'},
            'count':{'value':4,'quote':doc.text},
            'caliber':{'value':127,'unit':'mm','quote':'127 mm'}}}]}
        result=validate(claim,[field],doc)
        self.assertEqual(result['value'],[{'name':'guns','caliber':127}])
        self.assertEqual(result['rejected_properties'][0]['property'],'count')
        claim['value'][0]['properties']['count']['value']=2
        self.assertEqual(validate(claim,[field],doc)['value'][0]['count'],2)

    def test_chunks_cover_late_evidence(self):
        doc=Document('fixture:long','intro\n'*300+'crew: 220 persons')
        parts=list(chunks(doc,500,40))
        self.assertGreater(len(parts),1)
        self.assertIn('crew: 220 persons',parts[-1][2].text)
        for start,end,chunk in parts:
            self.assertEqual(chunk.text,doc.text[start:end])

    def test_shift_jis_windows_extension(self):
        access=Access({'min_interval_seconds':1})
        response=MagicMock()
        response.read.return_value='<meta charset="Shift_JIS">髙'.encode('cp932')
        response.headers=Message()
        response.__enter__.return_value=response
        access.opener.open=MagicMock(return_value=response)
        self.assertIn('髙',access._request('https://example.com','https://example.com',1))

    def test_anthropic_messages_contract(self):
        model=JsonModel({'provider':'anthropic','base_url':'https://example.com/v1',
                         'model':'test','api_key_env':'TEST_MODEL_KEY'},'test',200)
        response=MagicMock()
        response.read.return_value=json.dumps({'stop_reason':'end_turn',
            'content':[{'type':'text','text':'{"claims": []}'}]}).encode()
        response.__enter__.return_value=response
        model.opener.open=MagicMock(return_value=response)
        with patch.dict('os.environ',{'TEST_MODEL_KEY':'test-value'}):
            self.assertEqual(model.extract(Document('fixture:test','test'),[]),[])
        request=model.opener.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://example.com/v1/messages')
        self.assertEqual(request.get_header('X-api-key'),'test-value')
        payload=json.loads(request.data)
        self.assertIn('system',payload)
        self.assertEqual(payload['messages'][0]['role'],'user')

if __name__ == '__main__':
    unittest.main()
