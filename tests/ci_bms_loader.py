"""Assert accepted BMS records survive the real contribution-to-SQL pipeline."""
import json
from pathlib import Path
import sys
import psycopg2
ROOT = Path(__file__).resolve().parents[1]
with psycopg2.connect(sys.argv[1]) as conn, conn.cursor() as cur:
    batch = json.loads((ROOT / 'review/batches/2026-10-09-bms-market.json').read_text())
    for entry in batch['candidates']:
        d = entry['document']
        cur.execute('SELECT r.lifecycle_evidence,r.bms_details,p.first_released FROM bd.product_revision r JOIN bd.product p ON p.id=r.product_id WHERE p.uid=%s', (d['product']['uid'],))
        rows = cur.fetchall()
        assert len(rows) == 1, (d['product']['uid'], rows)
        lifecycle, bms, first_released = rows[0]
        assert lifecycle == d['lifecycle'] and bms == d['bms'], d['product']['uid']
        assert first_released is None, 'A partial date or launch must not become an exact release date'
    cur.execute("SELECT value_native,condition_extra->>'scope' FROM bd.v_observation WHERE model_number='Orion BMS 2' AND quantity='bms_series_cells_max'")
    assert cur.fetchone() == (180, 'per main unit; capacity varies by purchased configuration')
    print('BMS evidence, partial release dates and controller/system scopes survived SQL loading')
