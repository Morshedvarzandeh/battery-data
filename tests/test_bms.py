"""Prevent misleading BMS release dates, inferred interfaces and lost evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import jsonschema
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import validate_contrib as validate
import build_web_data as web
import build_bms_catalog as catalog


class BmsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = [e['document'] for e in json.loads((ROOT/'review/batches/2026-10-09-bms-market.json').read_text())['candidates']]
        cls.by_model = {d['product']['model_number']:d for d in cls.docs}
        cls.schema = json.loads((ROOT/'json-schema/cell-contribution.schema.json').read_text())
        cls.registry = json.loads((ROOT/'json-schema/quantity-registry.json').read_text())

    def errors(self, doc):
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
            json.dump(doc, f); f.flush()
            return validate.check(f.name,self.schema,self.registry)

    def test_all_records_valid_and_exported_without_losing_lifecycle(self):
        self.assertEqual(len({d['product']['uid'] for d in self.docs}),len(self.docs))
        for d in self.docs:
            self.assertEqual(self.errors(d),[],d['product']['uid'])
            output=web.product(d,str(ROOT/'contrib/placeholder.yaml'))
            self.assertEqual(output['lifecycle'],d['lifecycle'])
            self.assertEqual(output['bms'],d['bms'])

    def test_reviewed_bytes_are_published_once(self):
        audit=json.loads((ROOT/'review/audits/2026-10-11-bms-acceptance.json').read_text())
        decisions={d['uid']:d for d in audit['decisions']}
        for doc in self.docs:
            decision=decisions[doc['product']['uid']]
            path=ROOT/decision['accepted_file']
            self.assertEqual(json.loads(path.read_text()),doc)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),decision['accepted_document_sha256'])
            self.assertFalse((ROOT/decision['candidate_file']).exists())

    def test_bms_requires_both_scope_and_lifecycle(self):
        for key in ['bms','lifecycle']:
            d=copy.deepcopy(self.docs[0]);del d[key]
            self.assertTrue(self.errors(d))

    def test_document_date_cannot_become_release_and_dates_keep_precision(self):
        d=copy.deepcopy(self.by_model['c-BMS24X'])
        for kind in ['document_revision','planned_availability','announcement']:
            d['lifecycle']['release']['event']['event_type']=kind
            self.assertTrue(self.errors(d),kind)
        d=copy.deepcopy(self.by_model['Lithiumate Pro Master'])
        self.assertEqual(d['lifecycle']['release']['event']['date'],'2007')
        d['lifecycle']['release']['event']['date']='2007-01-01'
        self.assertTrue(self.errors(d))

    def test_calendar_and_future_observed_dates_rejected(self):
        for value in ['2023-02-30','2027-01-01']:
            d=copy.deepcopy(self.by_model['c-BMS24X'])
            d['lifecycle']['release']['event']['date']=value
            self.assertTrue(self.errors(d),value)
        self.assertFalse(self.errors(self.by_model['G5 Plus High-Voltage BMS']))

    def test_announcements_legacy_and_optional_can_stay_distinct(self):
        self.assertEqual(self.by_model['G5 Plus High-Voltage BMS']['lifecycle']['market_status'],'announced')
        self.assertEqual(self.by_model['G5 High-Voltage BMS']['lifecycle']['release']['status'],'conflicting')
        self.assertEqual(self.by_model['Lithiumate HD Master']['lifecycle']['market_status'],'legacy_support_only')
        for model in ['TinyBMS v2.1 High Power','TinyBMS v2.2 High Power','Orion Jr 2 BMS']:
            d=self.by_model[model]
            self.assertNotIn('bms_can_ports',[o['quantity'] for o in d['observations']])
        self.assertEqual(self.by_model['n3-BMS (CMU12 system)']['lifecycle']['events'][1]['precision'],'unspecified')
        self.assertNotIn('date',self.by_model['n3-BMS (CMU12 system)']['lifecycle']['events'][1])

    def test_comparison_is_generated_and_discloses_non_exhaustive_scope(self):
        rendered=catalog.render()
        self.assertEqual((ROOT/'components/bms.md').read_text(),rendered)
        for text in ['non-exhaustive','per main unit','launch announcement','Legacy support only','Conflicting dates','Not established']:
            self.assertIn(text,rendered)


if __name__ == '__main__':
    unittest.main()
