#!/usr/bin/env python3
"""Exercise component promotion in the disposable CI DB, then roll back all data."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import psycopg2
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import load_contrib as loader

connection=psycopg2.connect(sys.argv[1])
try:
    with connection.cursor() as cur:
        registry=json.loads((ROOT/'json-schema/quantity-registry.json').read_text())
        cur.execute('SELECT code,required_conditions FROM bd.quantity')
        assert {q:list(c or []) for q,c in cur.fetchall()} == registry, 'SQL/offline quantity registry drift'
        reviewer=loader.ensure_contributor(cur,'user/ci-component-review','CI transaction only')
        args=SimpleNamespace(stage_only=False,extraction='manual_entry')
        docs=json.loads((ROOT/'review/batches/2026-09-16-electrical-components.json').read_text())['candidates']
        index={r['uid']:r for r in json.loads((ROOT/'review/index.json').read_text())['candidates']}
        promoted=0
        for entry in docs:
            doc=entry['document']; record=index[doc['product']['uid']]
            path=ROOT/(record.get('accepted_file') or record['candidate_file'])
            result=loader.load_file(cur,str(path),args,reviewer)
            assert not result.get('invalid'), result
            promoted+=result.get('promoted',0)
        cur.execute("SELECT value_native,unit_native,value_si,test_voltage_v FROM bd.v_observation WHERE model_number='25EV1K125.ZXBDM' AND quantity='interrupting_current'")
        assert tuple(cur.fetchone()) == (30,'kA',30000,900)
        cur.execute("SELECT conductor_description,value_native FROM bd.v_observation WHERE model_number='GV211BAX' AND quantity='continuous_carry_current' ORDER BY value_native")
        assert cur.fetchall()==[('8.4 mm² / 8 AWG',100),('21 mm² / 4 AWG',150)]
        cur.execute("SELECT component_type,condition_extra->>'mode',conditions_unstated FROM bd.v_observation WHERE model_number='Blue Smart IP22 12/15 (1 output, 230 VAC)' AND quantity='rated_output_current' ORDER BY value_native")
        assert cur.fetchall()==[('charger','night or low',['temperature_c']),('charger','normal',['temperature_c'])]
        cur.execute("SELECT retrieved_at::date::text FROM bd.source WHERE uid='src/victron-charger-inspected-2026-09-16'")
        assert cur.fetchone()[0]=='2026-09-16'
        print(f'Validated {len(docs)} component models, {promoted} promoted observations; rolling back test data')
finally:
    connection.rollback()
    connection.close()
