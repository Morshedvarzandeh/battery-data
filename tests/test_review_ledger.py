"""The revision ledger must chain: every revision starts from the bytes the
ledger holds, and the current bytes of every audited file match its head."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import review_ledger


class ReviewLedgerTests(unittest.TestCase):
    def test_chain_is_unbroken_and_files_match_their_head(self):
        current, fields = review_ledger._ledger()  # raises on a broken chain
        self.assertGreater(len(current), 3000)
        for path, digest in current.items():
            f = ROOT / path
            if not f.exists():  # a later audit may have retired a file; holds live elsewhere
                continue
            self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), digest, path)

    def test_form_factor_revision_is_recorded_for_every_polymer_catalog_cell(self):
        audit = json.loads((ROOT / 'review/audits/2026-10-25-form-factor-revision.json').read_text())
        self.assertEqual(len(audit['revisions']), 3047)
        for r in audit['revisions']:
            doc = json.loads((ROOT / r['file']).read_text())
            self.assertEqual(doc['product']['form_factor'], 'pouch', r['uid'])
            self.assertIn('migrate_form_factor.py', doc['source']['note'], r['uid'])
            self.assertEqual(r['fields'], ['product.form_factor', 'source.note'])

    def test_without_fields_removes_only_the_named_paths(self):
        doc = {'product': {'uid': 'x', 'form_factor': 'pouch'}, 'source': {'note': 'n', 'url': 'u'}}
        out = review_ledger.without_fields(doc, ['product.form_factor', 'source.note', 'missing.path'])
        self.assertEqual(out, {'product': {'uid': 'x'}, 'source': {'url': 'u'}})
        self.assertEqual(doc['product']['form_factor'], 'pouch')  # input untouched


if __name__ == '__main__':
    unittest.main()
