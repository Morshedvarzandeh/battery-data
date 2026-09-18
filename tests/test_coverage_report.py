"""Guard the coverage report: a gap has to appear as a zero, not as a silence.

The whole value of the report is that it lists what the library does NOT
state. A report that enumerated only the quantities present would grow
quieter as the gaps grew, which is the opposite of useful. These tests pin
that behaviour, the cells-only population, and the tie between the report's
gate descriptions and the document that schedules the work.
"""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from coverage_report import GATES, as_markdown, envelopes, quantities, report  # noqa: E402

DOC = ROOT / 'docs' / '10-acquisition-list.md'


def observation(quantity, value=1.0, unit='Ah'):
    return {'quantity': quantity, 'value': value, 'unit': unit}


def entry(uid, kind, manufacturer, observations, document_date=None):
    source = {'uid': 'src/x', 'kind': 'datasheet', 'title': 'x', 'url': 'https://example.com/x.pdf'}
    if document_date:
        source['document_date'] = document_date
    return {
        'file': f'contrib/cells/{uid}.yaml',
        'record': {
            'product': {'uid': uid, 'kind': kind, 'manufacturer': manufacturer, 'model_number': uid},
            'source': source,
            'observations': observations,
        },
    }


def snapshot():
    return {'records': [
        entry('a', 'cell', 'EVE Energy', [
            observation('capacity'), observation('mass', 70, 'g'),
            observation('diameter', 21, 'mm'), observation('height', 70, 'mm'),
            observation('cycle_life', 4000, 'cycles'),
        ], document_date='2025-04-01'),
        entry('b', 'cell', 'EVE Energy', [
            observation('capacity'), observation('length', 62, 'mm'),
            observation('width', 35, 'mm'), observation('thickness', 5, 'mm'),
        ]),
        entry('c', 'primary_cell', 'Energizer', [observation('capacity')]),
        entry('d', 'pack', 'Toshiba', [observation('capacity'), observation('cycle_life', 9, 'cycles')]),
    ]}


class CoverageReportTests(unittest.TestCase):
    def test_a_quantity_no_record_states_is_reported_as_zero(self):
        rows = {row['quantity']: row for row in report(snapshot())['quantities']}
        # The three gaps that block the power and life analyses are absent
        # from this library entirely, and each one still has a row.
        for quantity in ('internal_resistance_dc', 'specific_power', 'max_pulse_discharge_current'):
            self.assertIn(quantity, rows, quantity)
            self.assertEqual(rows[quantity]['cells'], 0)
            self.assertTrue(rows[quantity]['gates'], f'{quantity} must name the analysis it blocks')
        # And every quantity the gate map knows about is on the report,
        # whether the library carries it or not.
        for quantity in GATES:
            self.assertIn(quantity, rows, quantity)

    def test_the_population_is_cells_and_the_pack_is_counted_separately(self):
        data = report(snapshot())
        self.assertEqual(data['cells'], 3)
        self.assertEqual(data['products'], 4)
        self.assertEqual(data['kinds']['pack'], 1)
        rows = {row['quantity']: row for row in data['quantities']}
        self.assertEqual(rows['cycle_life']['cells'], 1, 'the pack cycle life is not a cell cycle life')
        self.assertEqual(rows['capacity']['cells'], 3)
        self.assertEqual(rows['capacity']['share_pct'], 100.0)
        self.assertEqual(data['manufacturers'], {'EVE Energy': 2, 'Energizer': 1})
        self.assertEqual(data['dated_sources'], 1, 'a source with no document date is counted as having none')

    def test_every_cell_has_exactly_one_envelope_or_none(self):
        data = report(snapshot())
        shape = data['envelopes']
        self.assertEqual(shape, {'box': 1, 'cylinder': 1, 'none': 1})
        self.assertEqual(shape['box'] + shape['cylinder'] + shape['none'], data['cells'],
                         'a cell is a box, a cylinder, or counted as publishing no dimensions')
        # A record stating both is one envelope, not two: the cylinder wins,
        # because diameter and height are the narrower claim.
        both = {'records': [entry('e', 'cell', 'X', [
            observation('diameter', 21, 'mm'), observation('height', 70, 'mm'),
            observation('length', 21, 'mm'), observation('width', 21, 'mm'), observation('thickness', 21, 'mm'),
        ])]}
        self.assertEqual(envelopes(both['records']), {'box': 0, 'cylinder': 1, 'none': 0})

    def test_one_record_stating_a_quantity_twice_counts_once(self):
        records = [entry('f', 'cell', 'X', [observation('capacity', 4.9), observation('capacity', 4.75)])]
        self.assertEqual(quantities(records)['capacity'], 1,
                         'coverage counts records, not observations: two capacities are one covered cell')

    def test_the_markdown_marks_an_absent_quantity_rather_than_printing_a_zero(self):
        text = as_markdown(report(snapshot()))
        self.assertIn('| `internal_resistance_dc` | **none** |', text)
        self.assertIn('| `capacity` | 3 |', text)
        self.assertIn('Envelopes: 1 box, 1 cylinder, 1 publish no dimensions at all.', text)

    def test_the_document_schedules_every_gap_the_report_can_find(self):
        doc = DOC.read_text(encoding='utf-8')
        # The document is allowed to go stale on counts — it says so, and the
        # tool is the source of truth — but it may not omit a blocked
        # analysis, because then the work would stop being scheduled.
        for quantity in ('internal_resistance_dc', 'specific_power', 'cycle_life',
                         'max_continuous_discharge_current', 'capacity_retention'):
            self.assertIn(quantity, doc, quantity)
        self.assertIn('python tools/coverage_report.py', doc, 'the numbers must be reproducible from the document')
        self.assertRegex(doc, r'the tool is right and this file is stale',
                         'the document must name the tool as the authority over its own copy of the numbers')
        # A maker with no records is a maker whose documents were not
        # transcribed. The document says that, rather than implying a verdict.
        self.assertIn('not a judgement about their cells', doc)
        for maker in ('Molicel', 'LG Energy Solution', 'CATL', 'BYD', 'Samsung SDI'):
            self.assertIn(maker, doc, maker)

    def test_the_report_is_json_serialisable_so_it_can_be_published(self):
        json.dumps(report(snapshot()))


if __name__ == '__main__':
    unittest.main()
