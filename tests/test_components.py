"""Protect electrical identity, unit and variant distinctions in the starter batch."""
import copy
import json
from pathlib import Path
import sys
import unittest
import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_web_data import product
from render_review_issues import conditions_text

BATCH = json.loads((ROOT / 'review/batches/2026-09-16-electrical-components.json').read_text())
DOCS = {r['document']['product']['model_number']: r['document'] for r in BATCH['candidates']}
SCHEMA = json.loads((ROOT / 'json-schema/cell-contribution.schema.json').read_text())


def observations(model, quantity):
    return [o for o in DOCS[model]['observations'] if o['quantity'] == quantity]


class ComponentTests(unittest.TestCase):
    def test_component_requires_category_and_battery_cannot_claim_one(self):
        doc = copy.deepcopy(DOCS['EV200AAANA'])
        jsonschema.validate(doc, SCHEMA)
        del doc['product']['component_type']
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(doc, SCHEMA)
        doc['product']['component_type'] = 'contactor'
        doc['product']['kind'] = 'cell'
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(doc, SCHEMA)

    def test_sources_cover_all_categories_without_accepted_components(self):
        categories = set(json.loads((ROOT/'components/categories.json').read_text())['categories'])
        self.assertEqual({d['product']['component_type'] for d in DOCS.values()}, categories)
        index = json.loads((ROOT/'review/index.json').read_text())['candidates']
        # This initial batch is reviewable; adding it cannot inflate the battery milestone.
        for doc in DOCS.values():
            matching = [r for r in index if r['uid'] == doc['product']['uid']]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]['kind'], 'component')

    def test_125_amp_fuse_exception_and_native_kiloamps(self):
        for amps, voltage in [(70,1000), (100,1000), (125,900)]:
            model = f'25EV1K{amps:03}.ZXBDM'
            self.assertEqual(observations(model,'fuse_voltage_rating')[0]['value'], voltage)
            breaking = observations(model,'interrupting_current')[0]
            self.assertEqual((breaking['value'],breaking['unit']), (30,'kA'))
            self.assertEqual(breaking['conditions']['test_voltage_v'], voltage)

    def test_coil_voltage_is_distinct_from_main_contact_voltage(self):
        self.assertEqual(observations('EV200AAANA','contact_voltage_rating')[0]['value'], 900)
        self.assertEqual(observations('EV200AAANA','coil_voltage_max')[0]['value'], 36)
        self.assertEqual(observations('GV200CC-1','coil_nominal_voltage')[0]['value'], 24)

    def test_conductor_dependent_ratings_survive_export(self):
        doc = DOCS['GV211BAX']
        rendered = product(doc, str(ROOT/'review/example.yaml'))
        self.assertEqual(rendered['component_type'], 'precharge_contactor')
        ratings = [o for o in rendered['obs'] if o['q'] == 'continuous_carry_current']
        self.assertEqual([o['v'] for o in ratings], [100,150])
        self.assertEqual([o['cond']['conductor_description'] for o in ratings],
                         ['8.4 mm² / 8 AWG','21 mm² / 4 AWG'])
        self.assertEqual(ratings[0]['cond']['extra']['power_terminal_temperature_max_c'], 150)
        self.assertIn('temperature_c', ratings[0]['unstated'])

    def test_inverter_watts_and_temperature_are_preserved(self):
        ratings = observations('Inverter VE.Direct 12/250 (230 V)', 'rated_power')
        self.assertEqual([(o['value'],o['unit'],o['conditions']['temperature_c']) for o in ratings],
                         [(200,'W',25),(175,'W',40)])

    def test_charger_modes_visible_in_review_and_export(self):
        model='Blue Smart IP22 12/15 (1 output, 230 VAC)'
        currents=observations(model,'rated_output_current')
        self.assertEqual([o['value'] for o in currents], [15,7.5])
        self.assertIn('night or low', conditions_text(currents[1]['conditions']))
        voltage=observations(model,'rated_output_voltage')[0]
        self.assertEqual(voltage['conditions']['extra']['charge_stage'], 'absorption')
        rendered=product(DOCS[model],str(ROOT/'review/example.yaml'))
        self.assertEqual(rendered['source']['retrieved_at'], '2026-09-16')
        self.assertTrue(any(o['cond'].get('extra',{}).get('mode')=='night or low' for o in rendered['obs']))


if __name__ == '__main__':
    unittest.main()
