"""Dates must not make historical or unreleased hardware appear newly available."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from catalog_dates import date_value, load_timeline, record_dates
from validate_contrib import check_events, check, SCHEMA, REGISTRY
import build_web_data
import export_catalog_snapshot


class CatalogDateTests(unittest.TestCase):
    def test_partial_and_unknown_dates_never_gain_precision(self):
        for value, precision in [('2015', 'year'), ('2015-03', 'month'), ('2015-03-17', 'day')]:
            self.assertEqual(date_value(value), {'status': 'recorded', 'date': value, 'precision': precision})
        self.assertEqual(date_value(None)['status'], 'not_recorded')
        for bad in ['2026-02-30', '2026-13', '0000', '03/04/2026', '2026-1-01']:
            with self.assertRaises(ValueError):
                date_value(bad)

    def test_source_or_identifier_date_is_not_release_or_recheck(self):
        doc = {'source': {'uid': 'source-2026-10-11', 'title': 'Catalog 2026',
                          'url': 'https://example.com/20261011.pdf',
                          'document_date': '2013', 'revision': '2013 catalog'}}
        before = copy.deepcopy(doc)
        dates = record_dates(doc)
        self.assertEqual(dates['release']['status'], 'not_researched')
        self.assertEqual(dates['source_document']['date'], '2013')
        self.assertIsNone(dates['source_retrieved']['date'])
        self.assertIsNone(dates['lifecycle_checked']['date'])
        self.assertEqual(doc, before)

    def test_battery_and_component_exports_use_identical_projection(self):
        paths = ['contrib/cells/welion/shp270-16.yaml',
                 'contrib/components/lithium-balance/c-bms24x.yaml']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in paths:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / rel).read_bytes())
            result = export_catalog_snapshot.build(root, 'a' * 40)
            self.assertEqual(result['technology_milestones'], [])
            self.assertEqual(result['counts']['products'], 2)
            for row in result['records']:
                original = export_catalog_snapshot.load_record(root / row['file'])
                self.assertEqual(row['record'], original)
                self.assertEqual(row['dates'], build_web_data.product(original, str(ROOT / row['file']))['dates'])
            cell = next(r for r in result['records'] if r['record']['product']['kind'] == 'cell')
            self.assertEqual(cell['dates']['source_document']['date'], '2025-04-09')
            self.assertEqual(cell['dates']['release']['status'], 'not_researched')

    def test_scope_plans_and_article_date_remain_distinct(self):
        milestones = load_timeline()
        calb = next(m for m in milestones if m['id'] == 'calb-zhijiu-launch-2026')
        self.assertEqual(calb['event']['date'], '2026-04-01')
        self.assertEqual(calb['source_document_date'], '2026-04-02')
        self.assertEqual(calb['scope'], 'product_family')
        past_plan = next(m['event'] for m in milestones if m['id'] == 'hithium-n162-production-plan-2025')
        self.assertEqual(past_plan['event_type'], 'planned_availability')
        self.assertEqual(past_plan['date_text'], 'Q4 2025')
        self.assertNotIn('date', past_plan)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'technology'
            folder.mkdir()
            payload = json.loads((ROOT / 'technology/milestones.json').read_text())
            payload['milestones'][0]['product_uid'] = 'cell/catl/302ah-lifepo4'
            (folder / 'milestones.json').write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_timeline(root)  # No implicit product link or inherited release.
            del payload['milestones'][0]['product_uid']
            payload['milestones'].append(payload['milestones'][0])
            (folder / 'milestones.json').write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'duplicate milestone'):
                load_timeline(root)

    def test_future_observed_events_and_late_evidence_are_rejected(self):
        event = copy.deepcopy(load_timeline()[0]['event'])
        event['date'] = '2028-01-01'
        self.assertTrue(check_events('test', [event], '2026-10-11'))
        event['event_type'] = 'planned_availability'
        self.assertEqual(check_events('test', [event], '2026-10-11'), [])
        event['evidence']['retrieved_at'] = '2026-10-12'
        self.assertTrue(check_events('test', [event], '2026-10-11'))

    def test_invalid_source_dates_fail_the_contribution_pipeline(self):
        doc = export_catalog_snapshot.load_record(ROOT / 'contrib/cells/welion/shp270-16.yaml')
        schema, registry = json.loads(Path(SCHEMA).read_text()), json.loads(Path(REGISTRY).read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.yaml'
            for value in ['2026-02-30', '2026-13', '0000']:
                doc['source']['document_date'] = value
                path.write_text(json.dumps(doc))
                self.assertTrue(check(str(path), schema, registry))

    def test_milestones_change_digest_without_changing_product_facts(self):
        rel = 'contrib/cells/welion/shp270-16.yaml'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / rel
            target.parent.mkdir(parents=True)
            target.write_bytes((ROOT / rel).read_bytes())
            before = export_catalog_snapshot.build(root, 'b' * 40)
            timeline = root / 'technology/milestones.json'
            timeline.parent.mkdir()
            timeline.write_bytes((ROOT / 'technology/milestones.json').read_bytes())
            after = export_catalog_snapshot.build(root, 'b' * 40)
            self.assertEqual(before['records'], after['records'])
            self.assertEqual(before['counts'], after['counts'])
            self.assertNotEqual(before['release'], after['release'])
            self.assertEqual(len(after['technology_milestones']), 11)
if __name__ == '__main__':
    unittest.main()
