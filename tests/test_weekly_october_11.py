"""Preserve operating/insulation voltage and conditioned contactor ratings."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WeeklyOctober11Tests(unittest.TestCase):
    def test_configuration_limits_and_review_state(self):
        batch = json.loads((ROOT / 'review/batches/2026-10-11-electrical-components.json').read_text())
        index = {r['uid']: r for r in json.loads((ROOT / 'review/index.json').read_text())['candidates']}
        self.assertEqual(len(batch['candidates']), 2)
        for entry, amps, temp, conductor in zip(batch['candidates'], [300, 500], [70, 40], ['185 mm²', '2x 150 mm²']):
            doc = entry['document']
            self.assertIn('options unspecified', doc['product']['model_number'])
            voltage, current = doc['observations']
            self.assertEqual((voltage['value'], voltage['conditions']['extra']['rating_basis']), (1000, 'Ue'))
            self.assertEqual(current['value'], amps)
            self.assertEqual(current['conditions']['temperature_c'], temp)
            self.assertEqual(current['conditions']['conductor_description'], conductor)
            self.assertIn('temperature_reference', current['conditions']['unstated'])
            row = index[doc['product']['uid']]
            self.assertEqual(row['state'], 'accepted')
            accepted = json.loads((ROOT / row['accepted_file']).read_text())
            self.assertEqual(accepted['observations'], doc['observations'])
            self.assertEqual(accepted['lifecycle']['release']['status'], 'not_found')
            self.assertEqual(accepted['lifecycle']['market_status'], 'manufacturer_listed')
            self.assertFalse((ROOT / row['candidate_file']).exists())
            self.assertNotIn('sha256', doc['source'])
            self.assertIn('C360', doc['source']['note'])


if __name__ == '__main__':
    unittest.main()
