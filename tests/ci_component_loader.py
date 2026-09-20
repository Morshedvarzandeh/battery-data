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
        expansion=json.loads((ROOT/'review/batches/2026-09-21-battery-fuses-precharge-resistors.json').read_text())['candidates']
        sample={'GFPA415B','ABAT15C500-AIA','ABAT15C500-LIA','15NH1XLGBAT50','15NH3LGBAT450B',
                'HRHAFC22R0JB','LTO150H22000JTE3'}
        docs += [e for e in expansion if e['document']['product']['model_number'] in sample]
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
        cur.execute("SELECT value_native,unit_native,value_si,test_voltage_v,condition_extra->>'system_inductance_uh' FROM bd.v_observation WHERE model_number='GFPA415B' AND quantity='interrupting_current' ORDER BY test_voltage_v")
        assert cur.fetchall()==[(15.5,'kA',15500,650,'12'),(12,'kA',12000,850,'4')]
        cur.execute("SELECT value_native,tol_plus,tol_minus FROM bd.v_observation WHERE model_number='GFPA415B' AND quantity='fuse_trip_current'")
        assert tuple(cur.fetchone())==(1500,100,400)
        cur.execute("SELECT count(*),count(DISTINCT condition_set_id) FROM bd.observation o JOIN bd.quantity q ON q.id=o.quantity_id JOIN bd.product_revision r ON r.id=o.product_revision_id JOIN bd.product p ON p.id=r.product_id WHERE p.model_number='HRHAFC22R0JB' AND q.code='resistor_pulse_energy'")
        assert tuple(cur.fetchone())==(4,4), 'Pulse mounting/wait conditions collapsed'
        cur.execute("SELECT value_native,pulse_duration_s,pulse_wait_s,mounting_condition,pulse_waveform FROM bd.v_observation WHERE model_number='HRHAFC22R0JB' AND quantity='resistor_pulse_energy' ORDER BY pulse_wait_s")
        assert cur.fetchall()==[(1850,0.74,30,'stainless steel, 6 mm thick','RC discharge wave, Fig. 4'),
                                (1850,0.74,34,'Pamitherm, 6 mm thick','RC discharge wave, Fig. 4'),
                                (9000,1.8,100,'stainless steel, 6 mm thick','short circuit wave, Fig. 3'),
                                (9000,1.8,167,'Pamitherm, 6 mm thick','short circuit wave, Fig. 3')]
        cur.execute("SELECT temperature_reference,temperature_c,mounting_condition FROM bd.v_observation WHERE model_number='LTO150H22000JTE3' AND quantity='resistor_power_rating' AND value_native=150")
        assert tuple(cur.fetchone())==('component_case',45,'direct contact with heatsink, clip mounted')
        cur.execute("SELECT value_native,unit_native,value_si FROM bd.v_observation WHERE model_number='HRHAFC22R0JB' AND quantity='resistance_tolerance'")
        assert tuple(cur.fetchone())==(5,'%',0.05)
        print(f'Validated {len(docs)} component models, {promoted} promoted observations; rolling back test data')
finally:
    connection.rollback()
    connection.close()
