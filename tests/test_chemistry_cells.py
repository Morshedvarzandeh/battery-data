"""Protect evidence boundaries in the mixed-chemistry cell expansion."""
from collections import Counter
import json
from pathlib import Path
import sys
import unittest

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import import_chemistry_cells as importer
from build_web_data import product as web_product

MANIFEST = json.loads(importer.MANIFEST.read_text())
BATCH = json.loads(importer.BATCH.read_text())
DOCS = {e['document']['product']['model_number']: e['document'] for e in BATCH['candidates']}


def obs(model, quantity):
    return [o for o in DOCS[model]['observations'] if o['quantity'] == quantity]


class ChemistryEvidenceTests(unittest.TestCase):
    def test_all_documents_are_valid_and_reproducible(self):
        self.assertEqual(importer.build(MANIFEST), BATCH)
        schema = json.loads((ROOT / 'json-schema/cell-contribution.schema.json').read_text())
        for document in DOCS.values():
            jsonschema.validate(document, schema)
            for o in document['observations']:
                conditions = o.get('conditions', {})
                for field in importer.REGISTRY[o['quantity']]:
                    self.assertTrue(field in conditions or field in conditions.get('unstated', []))
                if conditions.get('rate_unit') == 'C':
                    self.assertEqual(conditions['rate_reference_source'],
                                     'Manufacturer C-rate label; reference capacity not stated')
                    self.assertIn('rate_reference_capacity_ah', conditions['unstated'])
                    self.assertNotIn('rate_reference_capacity_ah', conditions)
        self.assertEqual(len(DOCS), 32)
        self.assertEqual(sum(len(d['observations']) for d in DOCS.values()), 262)
        self.assertEqual(Counter(d['product']['manufacturer'] for d in DOCS.values()),
                         {'WeLion': 10, 'LG Energy Solution': 8, 'HiNa Battery': 4,
                          'CATL': 2, 'EVE Energy': 3, 'CALB': 5})

    def test_lg_minimum_nominal_and_rate_exceptions(self):
        standard = obs('E101A', 'capacity')[0]
        self.assertEqual((standard['statistic'], standard['conditions']['rate_value']), ('minimum', .3))
        jp = obs('JP3', 'capacity')[0]
        self.assertEqual((jp['value'], jp['statistic'], jp['conditions']['rate_value']), (62.4, 'minimum', .5))
        for model, capacity in [('M52V', 5.07)]:
            o = obs(model, 'capacity')[0]
            self.assertEqual((o['value'], o['statistic'], o['conditions']['rate_value']), (capacity, 'nominal', .2))
            self.assertTrue(o['conditions']['extra']['reference_value_only'])
        self.assertEqual(DOCS['E72B']['chemistry']['anode_text'], 'Graphite+SiO')

    def test_suspicious_lg_fields_are_not_reconstructed(self):
        for model in ['JF2', 'JH4']:
            self.assertEqual(obs(model, 'nominal_voltage'), [])
        self.assertEqual(obs('JH4', 'length'), [])
        self.assertEqual(obs('JF2', 'mass')[0]['statistic'], 'maximum')

    def test_semi_solid_is_electrolyte_and_trials_remain_preliminary(self):
        for model, doc in DOCS.items():
            if doc['product']['manufacturer'] != 'WeLion':
                continue
            self.assertEqual(doc['chemistry']['designation'], 'NMC+')
            self.assertEqual(doc['chemistry']['electrolyte_text'], 'Semi-Solid-State')
            self.assertNotIn('anode_text', doc['chemistry'])
            c = obs(model, 'capacity')[0]
            self.assertEqual(c['statistic'], 'typical')
            self.assertIn('rate_value', c['conditions']['unstated'])
            self.assertEqual(obs(model, 'max_continuous_discharge_current'), [])
            if model.endswith('-TRIAL'):
                self.assertFalse(doc['source']['is_final'])
                self.assertIn(model.removesuffix('-TRIAL'), doc['product']['aliases'])
        t = obs('SHP270-30', 'operating_temperature_max')
        self.assertEqual({o['conditions']['direction']: o['value'] for o in t}, {'charge': 55, 'discharge': 55})

    def test_sodium_aliases_and_power_rates_are_retained(self):
        self.assertEqual(DOCS['NE170']['product']['aliases'], ['NaPP72173204-NE170'])
        for model, unit in [('MP10', 'C'), ('HE240', 'P'), ('NE170', 'P'), ('MP200', 'C')]:
            self.assertEqual(DOCS[model]['chemistry']['designation'], 'Sodium-ion')
            o = obs(model, 'cycle_life')[0]
            self.assertEqual(o['conditions']['rate_unit'], unit)
            self.assertEqual(o['conditions']['extra']['source_comparator'], '>')
            self.assertIn('temperature_c', o['conditions']['unstated'])
            self.assertIn('direction', obs(model, 'operating_temperature_min')[0]['conditions']['unstated'])
        self.assertEqual(obs('MP10', 'cycle_life')[0]['value'], 10000)  # Not 100000 pulse events.

    def test_catl_table_row_overrides_headline_without_inventing_voltage(self):
        for model, cycles, mass in [('314Ah LFP ESS cell', 7000, 5.58), ('587Ah LFP ESS cell', 8000, 9.83)]:
            o = obs(model, 'cycle_life')[0]
            self.assertEqual((o['value'], o['conditions']['rate_unit']), (cycles, 'P'))
            self.assertEqual(o['conditions']['extra']['end_of_life_soh_pct'], 70)
            self.assertEqual(o['locator']['page'], 9)
            self.assertEqual(obs(model, 'mass')[0]['value'], mass)
            self.assertEqual(obs(model, 'nominal_voltage'), [])

    def test_eve_does_not_borrow_the_mislabelled_graphic(self):
        self.assertEqual(obs('LF206', 'nominal_voltage')[0]['value'], 3.22)
        c = obs('LF206', 'cycle_life')[0]['conditions']
        self.assertEqual((c['rate_value'], c['rate_unit'], c['direction']), (.5, 'C', 'discharge'))
        self.assertEqual(c['extra']['charge_rate_value'], 1)
        self.assertIn('temperature_c', obs('LF235L', 'cycle_life')[0]['conditions']['unstated'])
        self.assertIn('rate_unit', obs('MB30', 'cycle_life')[0]['conditions']['unstated'])
        self.assertEqual(obs('LF235L', 'length')[0]['value'], 173.936)

    def test_calb_cell_and_system_boundaries(self):
        self.assertEqual(obs('L173F314', 'nominal_voltage')[0]['value'], 3.2)
        self.assertFalse(DOCS['L173F314']['source']['is_final'])
        self.assertEqual(obs('L173F314', 'capacity')[0]['locator']['page'], 114)
        self.assertEqual(obs('684Ah ESS cell', 'energy'), [])
        self.assertNotIn('chemistry', DOCS['684Ah ESS cell'])
        for cap in [392, 588, 661]:
            model = f'ZHIJIU {cap}Ah long-cycle ESS cell'
            self.assertNotIn('chemistry', DOCS[model])
            self.assertEqual(obs(model, 'cycle_life')[0]['conditions']['extra']['end_of_life_criterion'], 'not stated')

    def test_web_export_retains_electrolyte_evidence(self):
        path = ROOT / 'review/candidates/welion/shp350-30-trial.yaml'
        item = web_product(DOCS['SHP350-30-TRIAL'], str(path))
        self.assertEqual(item['chem']['electrolyte'], 'Semi-Solid-State')
        self.assertEqual(item['chem']['electrolyte_locator']['page'], 1)
        self.assertIn('NMC+', item['chem']['electrolyte_locator']['quote'])

    def test_existing_and_held_cells_are_not_counted_again(self):
        uids = {d['product']['uid'] for d in DOCS.values()}
        self.assertEqual(len(uids), 32)
        for name in ['MB31', 'LF280K', 'LF280K-V3', 'C46M-V1', 'C46M-V2', 'M50L', 'M50LT',
                     'Naxtra passenger EV sodium-ion cell', 'SHP350-30', 'SHP350-40']:
            self.assertNotIn(name, DOCS)
        held_lg = next(h for h in MANIFEST['held'] if h['model'] == 'M50L')
        self.assertEqual(held_lg['existing_uid'], 'cell/lg-energy-solution/inr21700-m50lt')
        self.assertEqual(held_lg['transcription']['capacity_ah'], 4.93)
        self.assertEqual(len(MANIFEST['sources']), 35)
        for source in MANIFEST['sources'].values():
            self.assertRegex(source['sha256'], r'^[a-f0-9]{64}$')
            self.assertTrue(source['url'].startswith('https://'))


if __name__ == '__main__':
    unittest.main()
