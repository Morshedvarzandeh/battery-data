#!/usr/bin/env python3
"""Reproduce the September battery-fuse/precharge-resistor review batch offline.

Default: build from committed facts. --check: refuse drift. --source-dir: verify
original-byte hashes and re-extract listed identities/table rows with pdftotext.
Source bodies stay outside Git. No ordering-code Cartesian products are made.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NAME = '2026-09-21-battery-fuses-precharge-resistors'
MANIFEST = ROOT / f'review/imports/{NAME}.json'
BATCH = ROOT / f'review/batches/{NAME}.json'
NUMBER = r'\d+(?:[.,]\d+)?'
EXPECTED_ROWS = {'mersen-abat15c': 16, 'mersen-abat13c': 8,
                 'mersen-abat13d': 3, 'mersen-abat13g': 3, 'mersen-nhgbat': 50}


def number(value):
    n = float(value.replace(',', '.'))
    return int(n) if n.is_integer() else n


def decode_resistor(model, family):
    """Decode only listed, standard order codes covered by the inspected PDF."""
    if family == 'vishay-hrha':
        m = re.fullmatch(r'HRHAF([CN])([0-9R]{4})([JK])B', model)
        if not m:
            raise ValueError('Termination/coating or custom suffix outside documented HRHA standard code')
        coating, code, tolerance = m.groups()
        extra = {'termination': 'faston', 'coating': 'coated' if coating == 'C' else 'not coated'}
        upper = 1000
    elif family == 'vishay-lto150h':
        m = re.fullmatch(r'LTO150H([0-9R]{5})([GJK])TE3', model)
        if not m:
            raise ValueError('Tolerance or suffix outside documented LTO150H standard G/J/K, T, E3 code')
        code, tolerance = m.groups()
        extra = {'package': 'TO-247', 'packaging': 'tube', 'termination_finish': 'pure tin'}
        upper = 2200
    else:
        raise ValueError(f'Unknown resistor family: {family}')
    if not re.fullmatch(r'\d+(?:R\d+)?', code):
        raise ValueError(f'Invalid resistance code: {code}')
    ohms = number(code.replace('R', '.')) if 'R' in code else int(code[:-1]) * 10 ** int(code[-1])
    if not 1 <= ohms <= upper:
        raise ValueError(f'Resistance outside inspected family range: {model}')
    return {'resistance_ohm': ohms, 'tolerance_pct': {'G': 2, 'J': 5, 'K': 10}[tolerance],
            'resistance_code': code, 'tolerance_code': tolerance, 'configuration': extra}


def parse_mersen(key, text):
    rows = []
    pages = text.replace('\u200b', '').split('\f')
    for page_no, page in enumerate(pages, 1):
        if 'PRODUCT RANGE' not in page:
            continue
        if key == 'mersen-nhgbat':
            pattern = rf'^\s*((?:10|15)NH\w+)\s+([A-Z]\d{{7}})\s+(\w+)\s+({NUMBER}) A\s+({NUMBER}) kA²s\s+({NUMBER}) W\s+({NUMBER}) W\s+({NUMBER}) kA²s\s+(\d+)\s+({NUMBER}) kg\s*$'
        else:
            pattern = rf'^\s*(ABAT\w+-[A-Z]+)\s+([A-Z]\d{{7}})\s+({NUMBER})\s*V\s+({NUMBER}) A\s+({NUMBER}) kA²s\s+({NUMBER}) kA²s\s+({NUMBER}) W\s+({NUMBER}) W\s+({NUMBER}) kA'
            pattern += rf'\s+({NUMBER}) kA\s+({NUMBER}) kg\s*$' if key == 'mersen-abat15c' else r'\s*$'
        for line in page.splitlines():
            # On NH page 2 the image caption shares a line with the 63 A row.
            # Remove only a bare caption followed by a complete model/item pair.
            line = re.sub(r'^\s*(?:10|15)NH\w+\s+(?=(?:10|15)NH\w+\s+[A-Z]\d{7}\s)', '', line)
            m = re.fullmatch(pattern, line)
            if not m:
                # Captions contain just a model, but a model + item is a data row.
                if re.match(r'^\s*(?:ABAT|(?:10|15)NH)\S+\s+[A-Z]\d{7}', line):
                    raise ValueError(f'Unparsed {key} page {page_no} row: {line}')
                continue
            cells = list(m.groups())
            row = {'source_key': key, 'page': page_no, 'model': cells[0],
                   'item_number': cells[1], 'cells': cells}
            row['current_a'] = number(cells[3])
            if key == 'mersen-nhgbat':
                row.update(size=cells[2], voltage_v=1000 if page_no == 2 else 1500,
                           mass_kg=number(cells[9]),
                           terminal='direct mounting' if cells[0].endswith('B') else 'plain blade')
            else:
                row.update(voltage_v=number(cells[2]), min_breaking_ka=number(cells[8]))
                if key == 'mersen-abat15c':
                    row.update(max_breaking_ka=number(cells[9]), mass_kg=number(cells[10]),
                               terminal='LI blades' if '-LI' in cells[0] else 'TTF flush ends')
                else:
                    row.update(max_breaking_ka=250, mass_kg={'mersen-abat13c': 1.85,
                               'mersen-abat13d': 3.4, 'mersen-abat13g': 7.79}[key],
                               terminal='plates' if key.endswith('13g') else 'flush ends')
            rows.append(row)
    if len(rows) != EXPECTED_ROWS[key] or len({r['model'] for r in rows}) != len(rows):
        raise ValueError(f'{key}: expected {EXPECTED_ROWS[key]} unique rows, got {len(rows)}')
    return rows


def extract(source_dir, sources):
    rows, held = [], []
    for key, meta in sources.items():
        if 'sha256' not in meta:
            continue
        suffix = '.html' if key.endswith('-quality') else '.pdf'
        raw = (source_dir / (key + suffix)).read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta['sha256']:
            raise ValueError(f'{key}: source bytes changed; inspect before updating the manifest')
        if key in EXPECTED_ROWS:
            text = subprocess.run(['pdftotext', '-layout', str(source_dir / (key + suffix)), '-'],
                                  check=True, capture_output=True, text=True).stdout
            rows.extend(parse_mersen(key, text))
        elif key.endswith('-quality'):
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', raw.decode(), re.S)
            if not match:
                raise ValueError(f'{key}: missing part list')
            data = json.loads(match[1])['props']['pageProps']
            parts = data['qualityTabResults']
            expected = 30 if key == 'vishay-hrha-quality' else 27
            if len(parts) != expected or len({r['MAT_NO'] for r in parts}) != expected:
                raise ValueError(f'{key}: part list changed or is duplicated/truncated')
            family = key.removesuffix('-quality')
            for n, part in enumerate(parts, 1):
                row = {'source_key': family, 'identity_source_key': key,
                       'identity_row': n, 'model': part['MAT_NO']}
                try:
                    row.update(decode_resistor(row['model'], family))
                    rows.append(row)
                except ValueError as exc:
                    held.append({**row, 'reason': str(exc)})
    return sorted(rows, key=lambda r: (r['source_key'], r['model'])), sorted(held, key=lambda r: r['model'])


def observation(quantity, value, unit, page, section, quote, conditions=None, statistic='rated', **kwargs):
    doc = {'quantity': quantity, 'value': value, 'unit': unit, 'statistic': statistic,
           'locator': {'page': page, 'section': section, 'quote': quote}, **kwargs}
    if conditions:
        doc['conditions'] = deepcopy(conditions)
    return doc


def source(meta):
    return {k: deepcopy(v) for k, v in meta.items() if k in
            {'uid', 'kind', 'title', 'url', 'revision', 'retrieved_at', 'sha256', 'license', 'redistributable', 'note'}}


def document(maker, maker_slug, model, category, src, observations, aliases=None):
    product = {'uid': f'component/{maker_slug}/{model.lower()}', 'kind': 'component',
               'component_type': category, 'manufacturer': maker, 'model_number': model}
    if aliases:
        product['aliases'] = aliases
    return {'schema_version': '1', 'product': product, 'source': source(src), 'observations': observations}


def mersen_document(row, sources):
    key, model, page = row['source_key'], row['model'], row['page']
    voltage, current = row['voltage_v'], row['current_a']
    extra = {'terminal_configuration': row['terminal'], 'item_number': row['item_number'],
             'characteristic': 'gBat' if key == 'mersen-nhgbat' else 'aBat'}
    loc = f'Product range / {model} / {row["item_number"]}'
    obs = [observation('fuse_current_rating', current, 'A', page, loc, f'{model}: {current} A',
                       {'unstated': ['temperature_c', 'conductor_description'], 'extra': extra}),
           observation('fuse_voltage_rating', voltage, 'V', page, loc, f'{voltage} V DC',
                       {'electrical_system': 'DC', 'extra': extra}),
           observation('mass', row['mass_kg'], 'kg', page if key in {'mersen-nhgbat', 'mersen-abat15c'} else 1,
                       loc if key in {'mersen-nhgbat', 'mersen-abat15c'} else 'Technical data overview / weight',
                       f'Weight: {row["mass_kg"]} kg', statistic='nominal')]
    if key == 'mersen-nhgbat':
        # Revision 15 replaces the old UL-specific overview. Retain its
        # size/current-qualified ratings and the upper bound on L/R.
        if sources[key]['revision'] != 'DS-NHGBATF-15-1026_EN':
            raise ValueError('NH interruption table requires reviewed revision 15')
        breaking = (100 if row['size'] in ('1', '2', '2XL') else
                    50 if row['size'] == '1XL' else 150 if current <= 400 else 200)
        obs.append(observation('interrupting_current', breaking, 'kA', 1,
                   f'Technical data overview / I.R. DC / size {row["size"]}',
                   f'{voltage} Vdc; size {row["size"]}: {breaking} kA; L/R up to 3 ms',
                   {'electrical_system': 'DC', 'test_voltage_v': voltage,
                    'extra': {**extra, 'rating_basis': 'I.R. DC', 'circuit_time_constant_ms': 3,
                              'circuit_time_constant_comparator': '<='}}))
    else:
        cond = {'electrical_system': 'DC', 'test_voltage_v': voltage,
                'extra': {**extra, 'circuit_time_constant_ms': 3}}
        obs += [observation('minimum_interrupting_current', row['min_breaking_ka'], 'kA', page,
                            loc + ' / minimum breaking capacity',
                            f'{row["min_breaking_ka"]} kA at {voltage} V DC, L/R=3 ms', cond, 'minimum'),
                observation('interrupting_current', row['max_breaking_ka'], 'kA',
                            page if key == 'mersen-abat15c' else 1,
                            loc + ' / breaking capacity' if key == 'mersen-abat15c' else 'Technical data overview / maximum breaking capacity',
                            f'{row["max_breaking_ka"]} kA at {voltage} V DC, L/R=3 ms', cond)]
    return document('Mersen', 'mersen', model, 'fuse', sources[key], obs, [row['item_number']])


def resistor_document(row, sources):
    key, model = row['source_key'], row['model']
    hrha = key == 'vishay-hrha'
    page = 3 if hrha else 7
    identity = sources[row['identity_source_key']]
    decoded = decode_resistor(model, key)
    if any(row[k] != v for k, v in decoded.items()):
        raise ValueError(f'{model}: decoded identity drift')
    origin = {'identity_source_url': identity['url'], 'identity_source_sha256': identity['sha256'],
              'identity_row': row['identity_row'], 'value_basis': 'Decoded from an actually listed part using the datasheet ordering legend',
              **row['configuration']}
    obs = [observation('resistance_rating', row['resistance_ohm'], 'ohm', page, 'Global part number information',
                       f'Ordering-code transcription: {model}; {row["resistance_code"]} = {row["resistance_ohm"]} ohm',
                       {'unstated': ['temperature_c'], 'extra': origin}, 'nominal'),
           observation('resistance_tolerance', row['tolerance_pct'], '%', page, 'Global part number information / tolerance',
                       f'{model}; {row["tolerance_code"]} = ±{row["tolerance_pct"]} %', {'extra': origin}, 'nominal')]
    if hrha:
        for mount, watts, short_wait, rc_wait in [('stainless steel, 6 mm thick', 90, 100, 30),
                                                  ('Pamitherm, 6 mm thick', 54, 167, 34)]:
            cond = {'temperature_c': 30, 'temperature_reference': 'ambient', 'mounting_condition': mount,
                    'extra': {'bottom_case_temperature_limit_c': 250}}
            obs.append(observation('resistor_power_rating', watts, 'W', 1,
                       'Standard electrical specifications, note 1; page 2 Fig. 2 at Tamb=30°C',
                       f'{watts} W on {mount}; Fig. 2: Tamb=30°C', cond))
            for energy, duration, wait, wave in [(9000, 1.8, short_wait, 'short circuit wave, Fig. 3'),
                                                (1850, 0.74, rc_wait, 'RC discharge wave, Fig. 4')]:
                obs.append(observation('resistor_pulse_energy', energy, 'J', 3, 'Energy / continuous cycle',
                           f'{mount}: {energy} J; duration {duration} s; wait {wait} s; {wave}',
                           {**cond, 'pulse_duration_s': duration, 'pulse_waveform': wave, 'pulse_wait_s': wait,
                            'extra': {**cond['extra'], 'duty': 'continuous cycle'}}))
        obs.append(observation('resistor_voltage_limit', 1000, 'V', 1, 'General characteristics / voltage between terminals',
                   '1000 V DC', {'electrical_system': 'DC', 'extra': {'basis': 'By-design terminal voltage ceiling; power and resistance also constrain operation'}}, 'maximum'))
    else:
        obs += [observation('resistor_power_rating', 150, 'W', 2, 'Technical specifications / dissipation',
                            '150 W at +45°C case; heatsink + clip',
                            {'temperature_c': 45, 'temperature_reference': 'component_case',
                             'mounting_condition': 'direct contact with heatsink, clip mounted'}),
                observation('resistor_power_rating', 4.5, 'W', 2, 'Technical specifications / dissipation',
                            'Free air: 4.5 W at +25°C', {'temperature_c': 25, 'mounting_condition': 'free air',
                            'unstated': ['temperature_reference']}),
                observation('resistor_voltage_limit', 500, 'V', 1, 'Standard electrical specifications / limiting element voltage UL',
                            'UL = 500 V', {'unstated': ['electrical_system'], 'extra': {
                            'basis': 'Limiting element voltage; actual working voltage also constrained by power and resistance. AC/DC not specified in the table.'}}, 'maximum')]
    return document('Vishay', 'vishay', model, 'precharge_resistor', sources[key], obs)


def sensata_document(sources):
    obs = [observation('fuse_current_rating', 400, 'A', 1, 'Highlights; page 3 note 2', '400 A; 4/0 busbars',
                       {'conductor_description': '4/0 busbars', 'unstated': ['temperature_c'],
                        'extra': {'qualification': 'Application- and busbar-dependent; see note 2'}}),
           observation('fuse_voltage_rating', 1000, 'V', 2, 'Technical specifications / rated voltage', 'Rated voltage: 1000 V',
                       {'electrical_system': 'DC', 'extra': {'qualification': 'At 1000 V above 3 kA, consult Sensata; note 3'}}),
           observation('fuse_trip_current', 1500, 'A', 2, 'Ordering example GFPA415B and trip tolerance',
                       'GFPA415B; 1500 A; +100/-400 A', {'unstated': ['temperature_c']}, 'nominal', tol_plus=100, tol_minus=400),
           observation('mass', 790, 'g', 2, 'Technical specifications / active variant mass', 'Active mass: 790 g', statistic='nominal')]
    for voltage, current, inductance, basis in [(650, 15.5, 12, 'Validated at 650 V'), (850, 12, 4, 'Validated up to 850 V')]:
        obs.append(observation('interrupting_current', current, 'kA', 3, 'General notes / note 3',
                   f'{voltage} V; {current} kA; {inductance} µH',
                   {'electrical_system': 'DC', 'test_voltage_v': voltage,
                    'extra': {'system_inductance_uh': inductance, 'voltage_qualification': basis,
                              'qualification': 'Performance depends on environment and system isolation; see note 3'}}))
    return document('Sensata GIGAVAC', 'sensata-gigavac', 'GFPA415B', 'fuse', sources['sensata-gfp400'], obs)


def build(manifest):
    docs = []
    for row in manifest['rows']:
        docs.append(mersen_document(row, manifest['sources']) if row['source_key'].startswith('mersen-')
                    else resistor_document(row, manifest['sources']))
    docs.append(sensata_document(manifest['sources']))
    docs.sort(key=lambda d: d['product']['uid'])
    if len({d['product']['uid'] for d in docs}) != len(docs):
        raise ValueError('Duplicate identities in component batch')
    return {'schema_version': 1, 'batch': NAME,
            'origin': f'Manufacturer-listed battery protection and precharge parts; see review/imports/{NAME}.json. Pending review.',
            'candidate_count': len(docs), 'candidates': [{'document': d} for d in docs]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    if args.source_dir:
        rows, held = extract(args.source_dir, manifest['sources'])
        if args.check:
            if rows != manifest['rows'] or held != manifest['held']:
                raise SystemExit('Source extraction differs from committed facts')
        else:
            manifest.update(rows=rows, held=held)
            MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    batch = build(manifest)
    value = json.dumps(batch, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if BATCH.read_text() != value:
            raise SystemExit('Component batch is stale')
    else:
        BATCH.write_text(value)
    docs = [e['document'] for e in batch['candidates']]
    print(json.dumps({'models': len(docs), 'categories': dict(Counter(d['product']['component_type'] for d in docs)),
                      'observations': sum(len(d['observations']) for d in docs), 'held': len(manifest['held'])}))


if __name__ == '__main__':
    main()
