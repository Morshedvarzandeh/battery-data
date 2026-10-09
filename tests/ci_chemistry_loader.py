#!/usr/bin/env python3
"""Promote every new cell in disposable CI, verify chemistry, then roll back."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import load_contrib as loader

connection = psycopg2.connect(sys.argv[1])
try:
    with connection.cursor() as cur:
        reviewer = loader.ensure_contributor(cur, 'user/ci-chemistry-review', 'CI transaction only')
        args = SimpleNamespace(stage_only=False, extraction='manual_entry')
        batch = json.loads((ROOT / 'review/batches/2026-09-21-sodium-semisolid-lithium-cells.json').read_text())
        index = {r['uid']: r for r in json.loads((ROOT / 'review/index.json').read_text())['candidates']}
        promoted = 0
        for entry in batch['candidates']:
            doc = entry['document']
            record = index[doc['product']['uid']]
            result = loader.load_file(cur, str(ROOT / (record.get('accepted_file') or record['candidate_file'])), args, reviewer)
            assert not result.get('invalid'), result
            promoted += result.get('promoted', 0)
        # Accepted files were already loaded by the preceding CI step. Loading
        # the mixed batch again must neither lose nor duplicate observations.
        cur.execute("""SELECT count(*) FROM bd.observation o
                         JOIN bd.product_revision r ON r.id=o.product_revision_id
                         JOIN bd.product p ON p.id=r.product_id
                        WHERE p.uid=ANY(%s)""",
                    ([e['document']['product']['uid'] for e in batch['candidates']],))
        assert cur.fetchone()[0] == 262
        cur.execute("""SELECT c.designation, c.cathode_text, c.electrolyte_text, l.page, l.section, l.quote, r.is_preliminary
                         FROM bd.product_chemistry c JOIN bd.product_revision r ON r.id=c.product_revision_id
                         JOIN bd.product p ON p.id=r.product_id JOIN bd.provenance pv ON pv.id=c.provenance_id
                         JOIN bd.source_location l ON l.id=pv.source_location_id
                        WHERE p.model_number='SHP350-30-TRIAL'""")
        chemistry = cur.fetchone()
        assert chemistry[:4] == ('NMC+', 'NMC+', 'Semi-Solid-State', 1), chemistry
        assert 'header' in chemistry[4] and 'Semi-Solid-State' in chemistry[5] and chemistry[6]
        cur.execute("SELECT value_native, rate_unit FROM bd.v_observation WHERE model_number='HE240' AND quantity='cycle_life'")
        assert tuple(cur.fetchone()) == (8000, 'P')
        cur.execute("SELECT value_native, rate_value, rate_unit, statistic FROM bd.v_observation WHERE model_number='M52V' AND quantity='capacity'")
        assert tuple(cur.fetchone()) == (5.07, .2, 'C', 'nominal')
        cur.execute("""SELECT c.rate_reference_capacity_ah, c.rate_reference_source, c.unstated
                         FROM bd.condition_set c JOIN bd.observation o ON o.condition_set_id=c.id
                         JOIN bd.v_observation v ON v.observation_id=o.id
                        WHERE v.model_number='M52V' AND v.quantity='capacity'""")
        reference = cur.fetchone()
        assert reference[0] is None and reference[1] == 'Manufacturer C-rate label; reference capacity not stated'
        assert 'rate_reference_capacity_ah' in reference[2]
        cur.execute("SELECT count(*) FROM bd.v_observation WHERE model_number IN ('JF2','JH4') AND quantity='nominal_voltage'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT value_native FROM bd.v_observation WHERE model_number='L173F314' AND quantity='nominal_voltage'")
        assert cur.fetchone()[0] == 3.2
        # The legacy whole-source fallback and separator column use synthetic
        # data in this rolled-back test only, never a real manufacturer's claim.
        legacy = {'schema_version': '1', 'product': {'uid': 'cell/ci-chemistry/fixture', 'kind': 'cell',
                  'manufacturer': 'CI chemistry fixture', 'model_number': 'CI chemistry fixture'},
                  'source': {'uid': 'src/ci-chemistry-fixture', 'kind': 'datasheet',
                             'title': 'Synthetic CI fixture, rolled back',
                             'url': 'https://example.invalid/ci-chemistry-fixture'},
                  'chemistry': {'designation': 'test only', 'separator_text': 'synthetic separator',
                                'electrolyte_text': 'synthetic electrolyte'}}
        org = loader.ensure_organization(cur, 'ci-chemistry', 'CI chemistry fixture')
        source = loader.ensure_source(cur, legacy['source'], org)
        loader.promote_file(cur, legacy, org, source, [], 'CI fixture only', args, reviewer)
        cur.execute("""SELECT c.separator_text, c.electrolyte_text, l.page FROM bd.product_chemistry c
                         JOIN bd.provenance pv ON pv.id=c.provenance_id
                         JOIN bd.source_location l ON l.id=pv.source_location_id
                        WHERE c.designation='test only'""")
        assert tuple(cur.fetchone()) == ('synthetic separator', 'synthetic electrolyte', None)
        print(f'Validated 32 cells / {promoted} observations and chemistry provenance; rolling back test data')
finally:
    connection.rollback()
    connection.close()
