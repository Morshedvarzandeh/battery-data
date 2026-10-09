"""Prevent unsafe rating conflation and invented component identities."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import import_battery_components as importer
import check_duplicates as duplicates
import validate_contrib
from build_web_data import product as web_product
from render_review_issues import conditions_text

MANIFEST = json.loads(importer.MANIFEST.read_text())
BATCH = json.loads(importer.BATCH.read_text())
DOCS = {e['document']['product']['model_number']: e['document'] for e in BATCH['candidates']}
SCHEMA = json.loads((ROOT / 'json-schema/cell-contribution.schema.json').read_text())
REGISTRY = json.loads((ROOT / 'json-schema/quantity-registry.json').read_text())


def observations(model, q):
    return [o for o in DOCS[model]['observations'] if o['quantity'] == q]


class ComponentEvidenceTests(unittest.TestCase):
    def test_resistance_codes_have_family_specific_precision(self):
        for model, family, expected in [('HRHAFC1000KB', 'vishay-hrha', 100),
                                         ('HRHAFN1R20KB', 'vishay-hrha', 1.2),
                                         ('LTO150H22000JTE3', 'vishay-lto150h', 2200),
                                         ('LTO150H48R70GTE3', 'vishay-lto150h', 48.7)]:
            self.assertEqual(importer.decode_resistor(model, family)['resistance_ohm'], expected)

    def test_custom_and_unsupported_variants_are_held(self):
        self.assertEqual(len(MANIFEST['held']), 5)
        for row in MANIFEST['held']:
            self.assertNotIn(row['model'], DOCS)
            with self.assertRaises(ValueError):
                importer.decode_resistor(row['model'], row['source_key'])

    def test_complete_part_lists_account_for_pagination(self):
        rows = MANIFEST['rows'] + MANIFEST['held']
        for family, expected in [('vishay-hrha', 30), ('vishay-lto150h', 27)]:
            actual = [r for r in rows if r['source_key'] == family]
            self.assertEqual(len(actual), expected)
            self.assertEqual({r['identity_row'] for r in actual}, set(range(1, expected + 1)))
            self.assertEqual(len({r['model'] for r in actual}), expected)

    def test_caption_overlapping_table_does_not_hide_63_amp_fuse(self):
        text = ('PRODUCT RANGE\n10NH1GBAT50B 10NH1GBAT63B L1068613 1 63 A '
                '1.46 kA²s 13 W 5.4 W 5.35 kA²s 3 0.4 kg\n')
        with patch.dict(importer.EXPECTED_ROWS, {'mersen-nhgbat': 1}):
            row = importer.parse_mersen('mersen-nhgbat', text)[0]
            self.assertEqual((row['model'], row['current_a']), ('10NH1GBAT63B', 63))
            with self.assertRaises(ValueError):
                importer.parse_mersen('mersen-nhgbat', text.replace('63 A', '63 mA'))
        with self.assertRaises(ValueError):
            importer.parse_mersen('mersen-nhgbat', text)

    def test_reproduction_and_distinct_model_counts(self):
        self.assertEqual(importer.build(MANIFEST), BATCH)
        self.assertEqual(BATCH['candidate_count'], len(DOCS))
        self.assertEqual(Counter(d['product']['component_type'] for d in DOCS.values()),
                         {'fuse': 81, 'precharge_resistor': 52})
        self.assertEqual(sum(len(d['observations']) for d in DOCS.values()), 728)
        self.assertEqual(Counter(r['source_key'] for r in MANIFEST['rows'] if r['source_key'].startswith('mersen-')),
                         importer.EXPECTED_ROWS)

    def test_sensata_continuous_trip_and_interrupt_are_separate(self):
        self.assertEqual(observations('GFPA415B', 'fuse_current_rating')[0]['value'], 400)
        trip = observations('GFPA415B', 'fuse_trip_current')[0]
        self.assertEqual((trip['value'], trip['tol_plus'], trip['tol_minus']), (1500, 100, 400))
        breaking = observations('GFPA415B', 'interrupting_current')
        self.assertEqual([(o['value'], o['conditions']['test_voltage_v'], o['conditions']['extra']['system_inductance_uh'])
                          for o in breaking], [(15.5, 650, 12), (12, 850, 4)])
        self.assertNotIn('sha256', DOCS['GFPA415B']['source'])

    def test_mersen_terminal_and_minimum_interruption_distinctions(self):
        for model, maximum, minimum in [('ABAT15C500-AIA', 250, 6), ('ABAT15C500-LIA', 200, 7.5),
                                        ('ABAT13G3200-DIA', 250, 38.4)]:
            self.assertEqual(observations(model, 'interrupting_current')[0]['value'], maximum)
            m = observations(model, 'minimum_interrupting_current')[0]
            self.assertEqual(m['value'], minimum)
            self.assertEqual(m['conditions']['extra']['circuit_time_constant_ms'], 3)
        self.assertIn('ABAT15C1000-AIB', DOCS)
        self.assertNotIn('ABAT15C1000-AIA', DOCS)  # not a generated suffix cross-product

    def test_nh_revision_15_qualifiers_override_old_ul_table_and_headline(self):
        for model, current, voltage in [('10NH1GBAT50', 100, 1000), ('10NH2GBAT200', 100, 1000),
                                        ('15NH1XLGBAT50', 50, 1500), ('15NH2XLGBAT125', 100, 1500),
                                        ('15NH3LGBAT400', 150, 1500), ('15NH3LGBAT450B', 200, 1500)]:
            o = observations(model, 'interrupting_current')[0]
            self.assertEqual(o['value'], current)
            self.assertEqual(o['conditions']['test_voltage_v'], voltage)
            self.assertEqual(o['conditions']['extra']['circuit_time_constant_ms'], 3)
            self.assertEqual(o['conditions']['extra']['circuit_time_constant_comparator'], '<=')
            self.assertEqual(o['conditions']['extra']['rating_basis'], 'I.R. DC')
            self.assertEqual(DOCS[model]['source']['revision'], 'DS-NHGBATF-15-1026_EN')

    def test_hrha_mounting_and_four_pulse_conditions_survive_export(self):
        doc = DOCS['HRHAFC22R0JB']
        power = observations('HRHAFC22R0JB', 'resistor_power_rating')
        self.assertEqual([o['value'] for o in power], [90, 54])
        pulse = observations('HRHAFC22R0JB', 'resistor_pulse_energy')
        self.assertEqual([(o['value'], o['conditions']['pulse_duration_s'], o['conditions']['pulse_wait_s']) for o in pulse],
                         [(9000, 1.8, 100), (1850, 0.74, 30), (9000, 1.8, 167), (1850, 0.74, 34)])
        out = web_product(doc, str(ROOT / 'review/test.yaml'))
        actual = [o['cond'] for o in out['obs'] if o['q'] == 'resistor_pulse_energy']
        self.assertEqual(actual, [o['conditions'] for o in pulse])
        self.assertIn('167', conditions_text(pulse[2]['conditions']))

    def test_lto_case_temperature_free_air_and_voltage_limit(self):
        model = 'LTO150H22000JTE3'
        power = observations(model, 'resistor_power_rating')
        self.assertEqual([(o['value'], o['conditions']['temperature_c']) for o in power], [(150, 45), (4.5, 25)])
        self.assertEqual(power[0]['conditions']['temperature_reference'], 'component_case')
        self.assertIn('temperature_reference', power[1]['conditions']['unstated'])
        self.assertEqual(observations(model, 'resistor_pulse_energy'), [])
        voltage = observations(model, 'resistor_voltage_limit')[0]
        self.assertEqual(voltage['value'], 500)
        self.assertEqual(voltage['conditions']['unstated'], ['electrical_system'])

    def test_missing_pulse_wait_fails_semantic_validation(self):
        doc = deepcopy(DOCS['HRHAFC22R0JB'])
        pulse = next(o for o in doc['observations'] if o['quantity'] == 'resistor_pulse_energy')
        del pulse['conditions']['pulse_wait_s']
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.yaml'; path.write_text(json.dumps(doc))
            self.assertTrue(any('pulse_wait_s' in e for e in validate_contrib.check(str(path), SCHEMA, REGISTRY)))
        pulse['conditions']['pulse_wait_s'] = -1
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(doc, SCHEMA)

    def test_item_alias_catches_duplicate_and_component_values_detect_conflicts(self):
        doc = deepcopy(DOCS['ABAT15C500-AIA'])
        alias_doc = deepcopy(doc)
        alias_doc['product'].update(uid='component/mersen/b1200486', model_number='B1200486', aliases=[])
        self.assertIn(ROOT / 'contrib/components', duplicates.DEFAULT_PATHS)
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / n for n in ['one.yaml', 'two.yaml']]
            paths[0].write_text(json.dumps(doc)); paths[1].write_text(json.dumps(alias_doc))
            finding = duplicates.find_duplicates(duplicates.load_records(paths))[0]
            self.assertEqual(finding.classification, 'probable_duplicate')
            alias_doc['observations'][0]['value'] = 550
            paths[1].write_text(json.dumps(alias_doc))
            finding = duplicates.find_duplicates(duplicates.load_records(paths))[0]
            self.assertEqual(finding.classification, 'identity_collision')

    def test_candidate_schema_and_review_notes(self):
        validator = jsonschema.Draft202012Validator(SCHEMA)
        issues = {e['uid']: e for e in json.loads((ROOT / 'review/issues.json').read_text())}
        index = {e['uid']: e for e in json.loads((ROOT / 'review/index.json').read_text())['candidates']}
        for doc in DOCS.values():
            validator.validate(doc)
            self.assertNotIn('is_rechargeable', doc['product'])
            row = index[doc['product']['uid']]
            if row['state'] == 'accepted':
                self.assertEqual(json.loads((ROOT / row['accepted_file']).read_text()), doc)
                self.assertNotIn(doc['product']['uid'], issues)
            else:
                self.assertIn(doc['source']['note'], issues[doc['product']['uid']]['body'])


if __name__ == '__main__':
    unittest.main()
