"""Preserve family identity, coil-dependent limits and non-scalar evidence."""
import copy
import json
from pathlib import Path
import sys
import unittest

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_web_data import product
from validate_contrib import check

BATCH = json.loads((ROOT / 'review/batches/2026-09-29-gx-contactors.json').read_text())
DOCS = {row['document']['product']['model_number']: row['document'] for row in BATCH['candidates']}
SCHEMA = json.loads((ROOT / 'json-schema/cell-contribution.schema.json').read_text())
REGISTRY = json.loads((ROOT / 'json-schema/quantity-registry.json').read_text())


def observations(model, quantity):
    return [o for o in DOCS[model]['observations'] if o['quantity'] == quantity]


class GxContactorTests(unittest.TestCase):
    def test_families_cannot_claim_a_selected_variant(self):
        for doc in DOCS.values():
            jsonschema.validate(doc, SCHEMA)
            self.assertEqual(doc['product']['identity_scope'], 'family')
            self.assertEqual(doc['product']['variant_selection']['status'], 'required')
            missing = copy.deepcopy(doc)
            del missing['product']['variant_selection']
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(missing, SCHEMA)
            selected = copy.deepcopy(doc)
            selected['product']['variant_selection']['status'] = 'selected'
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(selected, SCHEMA)

    def test_pending_records_are_reproducible_and_sources_do_not_claim_hashes(self):
        sources = json.loads((ROOT / 'components/sources-2026-09-29-gx-contactors.json').read_text())
        self.assertEqual(sources, [d['source'] for d in DOCS.values()])
        index = {r['uid']: r for r in json.loads((ROOT / 'review/index.json').read_text())['candidates']}
        for doc in DOCS.values():
            row = index[doc['product']['uid']]
            self.assertEqual(row['identity_scope'], 'family')
            self.assertEqual(row['state'], 'pending_review')
            path = ROOT / row['candidate_file']
            self.assertEqual(json.loads(path.read_text()), doc)
            self.assertEqual(check(str(path), SCHEMA, REGISTRY), [])
            self.assertNotIn('sha256', doc['source'])
            self.assertIn('HTTP 403', doc['source']['note'])
            self.assertIn('visual verification', doc['source']['note'])
            self.assertTrue(doc['source']['url'].startswith('https://www.sensata.com/'))

    def test_typical_resistance_is_an_interval_not_an_invented_point(self):
        for model, doc in DOCS.items():
            values = observations(model, 'contact_resistance')
            self.assertEqual([(o['statistic'], o['value']) for o in values],
                             [('maximum', 0.4), ('typical', 0.15), ('typical', 0.3)])
            for o in values:
                self.assertEqual(o['unit'], 'mohm')
                self.assertEqual(o['conditions']['extra']['measurement_current_min_exclusive_a'], 100)
                self.assertIn('temperature_c', o['conditions']['unstated'])
            self.assertTrue(values[1]['is_lower_bound'])
            self.assertTrue(values[2]['is_upper_bound'])
            rendered = product(doc, str(ROOT / 'review/example.yaml'))
            self.assertEqual(rendered['identity_scope'], 'family')
            self.assertEqual(rendered['variant_selection'], doc['product']['variant_selection'])
            typical = [o for o in rendered['obs'] if o['q'] == 'contact_resistance' and o['stat'] == 'typical']
            self.assertEqual([(o['value_min'], o['value_max']) for o in typical], [(0.15, 0.3)] * 2)
            self.assertEqual([(o['lower_bound'], o['upper_bound']) for o in typical], [(True, False), (False, True)])

    def test_ac_coils_keep_their_longer_release_limits(self):
        for model in ['GX11', 'GX12']:
            times = {o['conditions']['extra']['coil_designation']: o for o in observations(model, 'release_time')}
            voltages = {o['conditions']['extra']['coil_designation']: o for o in observations(model, 'coil_nominal_voltage')}
            self.assertEqual(set(times), set('BCFHJKLST'))
            self.assertEqual({c: o['value'] for c, o in times.items()},
                             dict(zip('BCFHJKLST', [12, 12, 12, 12, 12, 50, 55, 12, 12])))
            self.assertTrue(all(o['is_upper_bound'] and o['unit'] == 'ms' for o in times.values()))
            self.assertEqual(voltages['K']['conditions']['electrical_system'], 'AC')
            self.assertEqual(voltages['L']['conditions']['electrical_system'], 'AC')
            self.assertEqual(voltages['C']['conditions']['electrical_system'], 'DC')
            self.assertEqual(voltages['C']['value'], 24)
        self.assertEqual([(o['statistic'], o['value']) for o in observations('GX14', 'operate_time')],
                         [('maximum', 20), ('typical', 13)])
        release = observations('GX14', 'release_time')[0]
        self.assertNotIn('coil_designation', release['conditions']['extra'])
        self.assertIn('temperature_c', release['conditions']['unstated'])

    def test_carry_current_preserves_thermal_and_conductor_basis(self):
        expected = {'GX11': [(325, '2/0 AWG'), (225, '2 AWG')],
                    'GX12': [(375, '4/0 AWG'), (350, '2/0 AWG')],
                    'GX14': [(400, '4/0 AWG'), (350, '2/0 AWG')]}
        for model, pairs in expected.items():
            values = observations(model, 'continuous_carry_current')
            self.assertEqual([(o['value'], o['conditions']['conductor_description']) for o in values], pairs)
            for o in values:
                self.assertEqual(o['conditions']['extra']['terminal_temperature_rise_c'], 85)
                self.assertIn('temperature_c', o['conditions']['unstated'])
            self.assertEqual(observations(model, 'interrupting_current'), [])


if __name__ == '__main__':
    unittest.main()
