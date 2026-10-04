"""Acceptance must publish the reviewed bytes and leave concrete holds outside."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = 'review/audits/2026-10-04-catalog-acceptance.json'


class OctoberAcceptanceTests(unittest.TestCase):
    def test_each_decision_has_one_location_and_preserves_reviewed_bytes(self):
        audit = json.loads((ROOT / AUDIT).read_text())
        index = {r['uid']: r for r in json.loads((ROOT / 'review/index.json').read_text())['candidates']}
        issues = {r['uid'] for r in json.loads((ROOT / 'review/issues.json').read_text())}
        self.assertEqual(len(audit['decisions']), 1440)
        self.assertEqual(len({d['uid'] for d in audit['decisions']}), 1440)
        accepted = {'battery': 0, 'component': 0}
        held = 0
        for d in audit['decisions']:
            row = index[d['uid']]
            if d['decision'] == 'accept':
                path = ROOT / d['accepted_file']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), d['accepted_document_sha256'])
                self.assertEqual(d['reviewed_document_sha256'], d['accepted_document_sha256'])
                self.assertFalse((ROOT / d['candidate_file']).exists())
                self.assertEqual(row['state'], 'accepted')
                self.assertEqual(row['review_audit'], AUDIT)
                self.assertNotIn(d['uid'], issues)
                doc = json.loads(path.read_text())
                accepted['component' if doc['product']['kind'] == 'component' else 'battery'] += 1
            else:
                held += 1
                self.assertTrue(d['reasons'])
                self.assertTrue((ROOT / d['candidate_file']).is_file())
                self.assertEqual(row['state'], 'pending_review')
                self.assertNotIn('accepted_file', row)
                self.assertIn(d['uid'], issues)
        self.assertEqual(accepted, {'battery': 1284, 'component': 152})
        self.assertEqual(held, 4)


if __name__ == '__main__':
    unittest.main()
