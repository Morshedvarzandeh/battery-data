"""Keep the current-cell collection bounded, traceable and outside acceptance."""
from collections import Counter
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / 'collections/current-cell-research-set-v1.json'


class CurrentCellResearchSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collection = json.loads(COLLECTION.read_text())
        cls.entries = cls.collection['entries']
        cls.documents = []
        for entry in cls.entries:
            path = ROOT / entry['candidate']
            cls.documents.append((entry, path, json.loads(path.read_text())))

    def test_collection_has_a_bounded_unique_pending_scope(self):
        self.assertEqual(self.collection['format'], 'lemonergy/current-cell-research-set@1')
        self.assertEqual(self.collection['review_status'], 'pending_review')
        self.assertEqual(self.collection['decision_scope'], 'screening_only')
        self.assertEqual(len(self.entries), 40)
        self.assertEqual(len({entry['uid'] for entry in self.entries}), 40)

    def test_every_entry_resolves_to_source_linked_non_draft_cell_evidence(self):
        for entry, path, document in self.documents:
            self.assertTrue(path.is_file(), entry['candidate'])
            self.assertTrue(entry['candidate'].startswith('review/candidates/'))
            self.assertEqual(document['product']['uid'], entry['uid'])
            self.assertEqual(document['product']['kind'], 'cell')
            self.assertNotIn(document['source'].get('is_final'), [False])
            self.assertTrue(document['source']['url'].startswith('https://'))
            self.assertTrue(document['observations'])
            for observation in document['observations']:
                self.assertIn('quantity', observation)
                self.assertIn('unit', observation)
                self.assertTrue(observation.get('locator'))

    def test_set_covers_the_requested_manufacturers_and_technology_segments(self):
        makers = Counter(document['product']['manufacturer'] for _, _, document in self.documents)
        self.assertEqual(makers, {
            'EVE Energy': 10, 'LG Energy Solution': 8, 'WeLion': 6, 'CATL': 5,
            'CALB': 4, 'HiNa Battery': 4, 'HiTHIUM': 3,
        })
        segments = Counter(entry['segment'] for entry in self.entries)
        for required in ['high-energy-ev', 'high-power-cylindrical', 'lfp-ess',
                         'large-format-ess', 'sodium-ion', 'semi-solid']:
            self.assertGreater(segments[required], 0)

    def test_known_drafts_and_trials_are_not_present(self):
        uids = {entry['uid'] for entry in self.entries}
        self.assertNotIn('cell/calb/l173f314', uids)
        self.assertFalse(any(uid.endswith('-trial') for uid in uids))

    def test_source_revisions_remain_linked_to_one_pending_product(self):
        entry = next(e for e in self.entries if e['uid'] == 'cell/catl/587ah-lfp-ess-cell')
        self.assertTrue((ROOT / entry['source_review']).is_file())
        original = json.loads((ROOT / entry['candidate']).read_text())
        revision = json.loads((ROOT / entry['revision_files'][0]).read_text())
        self.assertEqual(original['product']['uid'], revision['product']['uid'])
        self.assertNotEqual(original['source']['uid'], revision['source']['uid'])
        self.assertEqual(revision['source']['kind'], 'user_submission')
        mass = lambda doc: next(o['value'] for o in doc['observations'] if o['quantity'] == 'mass')
        self.assertEqual((mass(original), mass(revision)), (9.83, 10.6))
        self.assertIn('relationship', original['source']['note'])


if __name__ == '__main__':
    unittest.main()
