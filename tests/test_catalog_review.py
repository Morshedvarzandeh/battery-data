"""Guard the catalog import against duplicate inflation and lost qualifiers."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from import_manufacturer_catalogs import measurement, reconcile, harding_rows
from build_web_data import product


class CatalogReviewTests(unittest.TestCase):
    def row(self, model='LP123456', row_id=1):
        return {'model': model, 'row_id': row_id, 'measurements': [
            measurement('capacity', '500', 'mAh'), measurement('voltage', '3.7', 'V'),
            measurement('thickness', '5', 'mm'), measurement('width', '30', 'mm'),
            measurement('length', '50', 'mm')]}

    def test_same_model_is_never_counted_twice(self):
        a, b = self.row(), self.row('lp123456', 2)
        kept, excluded, duplicates = reconcile([a, b])
        self.assertEqual(len(kept), 1)
        self.assertEqual(excluded, [])
        self.assertEqual(duplicates[0]['duplicate_rows'], [b])

    def test_conflicting_model_quarantines_every_row(self):
        a, b = self.row(), self.row(row_id=2)
        b['measurements'][0]['value'] = 600
        kept, excluded, duplicates = reconcile([a, b])
        self.assertEqual((kept, duplicates), ([], []))
        self.assertEqual(excluded[0]['rows'], [a, b])

    def test_implausible_source_row_is_not_published(self):
        row = self.row()
        row['measurements'][0]['value'] = 20000
        kept, excluded, _ = reconcile([row])
        self.assertEqual(kept, [])
        self.assertEqual(excluded[0]['reason'], 'energy_density_requires_source_clarification')

    def test_truncated_pdf_extraction_fails_closed(self):
        with self.assertRaises(ValueError):
            harding_rows('2019 Lithium Polymer Cell Selection Guide\n1 123456 ≥500 ≥3.7 ≤5 ≤30 ≤50 10')

    def test_import_reconciliation_accounts_for_every_source_row(self):
        for path in (ROOT / 'review/imports/2026-09-15-manufacturer-catalogs').glob('*.json'):
            batch = json.loads(path.read_text())
            counts = batch['reconciliation']
            self.assertEqual(counts['source_row_count'], counts['candidate_count'] +
                             counts['excluded_row_count'] + counts['duplicate_row_count'])
            self.assertEqual(len(batch['rows']), counts['candidate_count'])
            self.assertEqual(len({row['model'].lower() for row in batch['rows']}), len(batch['rows']))

    def test_public_details_keep_units_bounds_and_locator(self):
        path = ROOT / 'contrib/cells/harding-energy/501624.yaml'
        rendered = product(json.loads(path.read_text()), str(path))
        obs = {o['q']: o for o in rendered['obs']}
        self.assertEqual((obs['capacity']['v'], obs['capacity']['u']), (120, 'mAh'))
        self.assertTrue(obs['capacity']['lower_bound'])
        self.assertTrue(obs['width']['upper_bound'])
        self.assertFalse(obs['thickness']['upper_bound'])  # source prints plain 5.1
        self.assertEqual(obs['capacity']['pg'], 8)
        self.assertIn('row 275', obs['capacity']['section'])
        self.assertNotIn('nominal_voltage', obs)
        for key in ('ah', 'wh', 'whkg', 'whl', 'litres'):
            self.assertIsNone(rendered['m'][key])

    def test_point_estimates_still_convert_milliamphours(self):
        doc = {'product': {'uid': 'cell/example/a', 'kind': 'cell', 'manufacturer': 'Example',
                           'model_number': 'A'}, 'source': {}, 'observations': []}
        for q, value, unit in [('capacity', 500, 'mAh'), ('nominal_voltage', 3.7, 'V'), ('mass', 10, 'g')]:
            doc['observations'].append({'quantity': q, 'value': value, 'unit': unit,
                                        'locator': {'quote': 'test fixture only'}})
        rendered = product(doc, str(ROOT / 'example.yaml'))
        self.assertAlmostEqual(rendered['m']['ah'], 0.5)
        self.assertAlmostEqual(rendered['m']['wh'], 1.85)

    def test_review_decisions_match_accepted_and_pending_files(self):
        audit = json.loads((ROOT / 'review/audits/2026-09-16-catalog-review.json').read_text())
        decisions = audit['decisions']
        self.assertEqual(len({r['uid'] for r in decisions}), len(decisions))
        self.assertEqual(sum(r['decision'] == 'hold' for r in decisions), 106)
        for row in decisions:
            if row['decision'] == 'accept':
                path = ROOT / row['accepted_file']
                self.assertFalse((ROOT / row['candidate_file']).exists(), row['uid'])
                self.assertTrue(path.is_file(), row['uid'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                 row['accepted_document_sha256'], row['uid'])
            else:
                self.assertTrue(row['reasons'])
                self.assertTrue((ROOT / row['candidate_file']).is_file(), row['uid'])


if __name__ == '__main__':
    unittest.main()
