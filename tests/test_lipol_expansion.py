"""Protect the new catalog batch against inflated counts and invented facts."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import import_lipol_expansion as importer


class ExtractionTests(unittest.TestCase):
    def row(self, model='LP603450', row_no=1, cells=None, header=None, key='lipol-1000-3000'):
        return importer.parse_row(key, 2, row_no, header or importer.LWT,
                                  cells or [model, '1000mAh', '50 x 34 x 6', '3.7V'])

    def decisions(self, rows, baseline=None, prior=None, assemblies=None):
        return importer.reconcile(rows, baseline or {'same_manufacturer_records': []},
                                  prior or [], assemblies or [])

    def test_column_axes_and_native_units_are_preserved(self):
        a = self.row()
        b = self.row(header=importer.TWL, cells=['LP603450', '1000mAh', '6', '34', '50'])
        c = self.row(header=importer.SPLIT_LWT,
                     cells=['LP603450', '1000 mAh', '50', '34', '6.0', '3.7V'])
        self.assertEqual(a['values'], c['values'])
        self.assertEqual({k: v for k, v in a['values'].items() if k != 'voltage'}, b['values'])
        self.assertEqual(a['values']['capacity'], 1000)
        self.assertEqual(a['values']['length'], 50)
        self.assertEqual(a['values']['thickness'], 6)

    def test_identical_rows_count_once(self):
        decisions = self.decisions([self.row(), self.row(row_no=2)])
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]['disposition'], 'pending_review')
        self.assertEqual(len(decisions[0]['row_ids']), 2)

    def test_conflict_in_partial_crosscheck_holds_entire_model(self):
        cross = self.row(header=importer.TWL, key='lipol-crosscheck-1000',
                         cells=['LP603450', '1200mAh', '6', '34', '50'])
        decision = self.decisions([self.row(), cross])[0]
        self.assertEqual(decision['disposition'], 'conflicting_source_values')
        self.assertEqual(decision['conflicts']['capacity'], [1000, 1200])
        self.assertNotIn('representative_row_id', decision)

    def test_missing_primary_voltage_is_never_filled_from_another_page(self):
        primary = self.row(header=importer.TWL, cells=['LP603450', '1000mAh', '6', '34', '50'])
        cross = self.row(key='lipol-crosscheck-1000')
        self.assertNotIn('voltage', primary['values'])
        self.assertEqual(self.decisions([primary, cross])[0]['disposition'], 'missing_complete_primary_row')

    def test_blank_voltage_is_absent(self):
        row = self.row(header=importer.SPLIT_LWT,
                       cells=['LP603450', '1000 mAh', '50', '34', '6', ''])
        self.assertNotIn('voltage', row['values'])
        self.assertEqual(row['parse_errors'], [])

    def test_existing_alias_is_excluded_even_if_specs_differ(self):
        baseline = {'same_manufacturer_records': [
            {'product': {'uid': 'cell/lipol-battery/old-code', 'model_number': 'Old code',
                         'aliases': ['lp-603450']}}]}
        decision = self.decisions([self.row()], baseline=baseline)[0]
        self.assertEqual(decision['disposition'], 'already_in_library_or_review')
        self.assertEqual(decision['existing_uids'], ['cell/lipol-battery/old-code'])

    def test_previous_unresolved_conflicts_stay_held(self):
        self.assertEqual(self.decisions([self.row()], prior=['lp603450'])[0]['disposition'],
                         'previous_unresolved_conflict')

    def test_protected_assembly_is_not_silently_treated_as_bare_cell(self):
        self.assertEqual(self.decisions([self.row()], assemblies=[{'model': 'LP603450'}])[0]['disposition'],
                         'protected_assembly_scope_requires_review')

    def test_source_typo_is_quarantined_not_corrected(self):
        row = self.row(cells=['LP603450', '1000mAh', '5 x 34 x 6', '3.7V'])
        self.assertEqual(row['values']['length'], 5)
        self.assertEqual(self.decisions([row])[0]['disposition'], 'dimension_capacity_sanity_check')

    def test_model_dimension_pattern_only_holds_never_corrects(self):
        row = self.row(cells=['LP103228', '1000mAh', '22 x 32 x 10', '3.7V'])
        self.assertEqual(self.decisions([row])[0]['disposition'], 'model_dimension_pattern_requires_review')
        self.assertEqual(row['values']['length'], 22)

    def test_unsupported_dimension_retains_raw_evidence_and_blocks_identity(self):
        invalid = self.row(header=importer.TWL, key='lipol-crosscheck-general',
                           cells=['LP603450', '1000mAh', '6', '34', '0R'])
        self.assertEqual(invalid['cells'][-1], '0R')
        self.assertTrue(invalid['parse_errors'])
        self.assertEqual(self.decisions([self.row(), invalid])[0]['disposition'], 'unsupported_source_value')

    def test_changed_header_or_truncated_table_fails_closed(self):
        config = deepcopy(importer.SOURCES['lipol-1000-3000'])
        config['tables'] = [(importer.LWT, 2, 'LP603450', 'LP604050')]
        head = '<tr>' + ''.join(f'<th>{x}</th>' for x in importer.LWT) + '</tr>'
        one = '<tr><td>LP603450</td><td>1000mAh</td><td>50 x 34 x 6</td><td>3.7V</td></tr>'
        two = one.replace('LP603450', 'LP604050').replace('50 x 34', '50 x 40')
        good = '<table>' + head + one + two + '</table>'
        with patch.dict(importer.SOURCES, {'lipol-1000-3000': config}):
            self.assertEqual(len(importer.extract('lipol-1000-3000', good)[0]), 2)
            for bad in [good.replace(two, ''), good.replace('L x W x T(mm)', 'T x W x L(mm)')]:
                with self.assertRaises(ValueError):
                    importer.extract('lipol-1000-3000', bad)


class CommittedBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(importer.IMPORT.read_text())
        cls.batch = json.loads(importer.BATCH_FILE.read_text())

    def test_committed_decisions_and_batch_reproduce_from_facts(self):
        m = self.manifest
        self.assertEqual(importer.reconcile(m['rows'], m['baseline'], m['previous_excluded_models'],
                                            m['individual_assembly_tables']), m['decisions'])
        self.assertEqual(importer.make_batch(m), self.batch)

    def test_every_source_row_is_accounted_for_exactly_once(self):
        rows = [r['id'] for r in self.manifest['rows']]
        assigned = [rid for d in self.manifest['decisions'] for rid in d['row_ids']]
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual(Counter(rows), Counter(assigned))
        counts = self.manifest['reconciliation']
        self.assertEqual(len(rows), counts['source_catalog_row_count'])
        self.assertEqual(sum(r['primary'] for r in self.manifest['rows']), counts['primary_catalog_row_count'])
        self.assertEqual(Counter(d['disposition'] for d in self.manifest['decisions']), counts['model_dispositions'])

    def test_every_transcribed_row_reparses_with_its_original_columns(self):
        for row in self.manifest['rows']:
            header = importer.SOURCES[row['source_key']]['tables'][row['table'] - 1][0]
            self.assertEqual(importer.parse_row(row['source_key'], row['table'], row['data_row'],
                                               header, row['cells']), row)

    def test_at_least_590_new_distinct_models_without_baseline_overlap(self):
        docs = [c['document'] for c in self.batch['candidates']]
        identities = {importer.compact_identifier(d['product']['model_number']) for d in docs}
        self.assertGreaterEqual(len(docs), 590)
        self.assertEqual(len(docs), len(identities))
        self.assertEqual(len(docs), self.batch['candidate_count'])
        for existing in self.manifest['baseline']['same_manufacturer_records']:
            product = existing['product']
            for name in [product['model_number'], *product.get('aliases', [])]:
                self.assertNotIn(importer.compact_identifier(name), identities)
            self.assertEqual(hashlib.sha256((ROOT / existing['file']).read_bytes()).hexdigest(), existing['sha256'])

    def test_evidence_and_conditions_survive_candidate_generation(self):
        sources = {s['url']: s for s in self.manifest['sources']}
        for candidate in self.batch['candidates']:
            doc = candidate['document']
            source = doc['source']
            self.assertEqual(source['sha256'], sources[source['url']]['sha256'])
            self.assertEqual(source['retrieved_at'], '2026-09-21')
            self.assertFalse(source['redistributable'])
            observations = {o['quantity']: o for o in doc['observations']}
            self.assertEqual(set(observations), importer.REQUIRED)
            self.assertEqual(observations['capacity']['conditions']['unstated'], importer.CAPACITY_UNSTATED)
            self.assertEqual(observations['capacity']['unit'], 'mAh')
            self.assertNotIn('statistic', observations['voltage'])
            self.assertIn(doc['product']['model_number'], observations['capacity']['locator']['quote'])
            self.assertIn('Specification table', observations['capacity']['locator']['section'])

    def test_real_cross_page_capacity_conflict_is_excluded(self):
        decision = next(d for d in self.manifest['decisions'] if d['model_key'] == 'lp2884157')
        self.assertIn(4000, decision['conflicts']['capacity'])
        self.assertIn(4400, decision['conflicts']['capacity'])
        self.assertEqual(decision['disposition'], 'conflicting_source_values')

    def test_review_payloads_disclose_source_limitations(self):
        issues = {item['uid']: item for item in json.loads((ROOT / 'review/issues.json').read_text())}
        for candidate in self.batch['candidates']:
            doc = candidate['document']
            self.assertIn(doc['source']['note'], issues[doc['product']['uid']]['body'])


if __name__ == '__main__':
    unittest.main()
