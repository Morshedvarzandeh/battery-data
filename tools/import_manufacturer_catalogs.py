#!/usr/bin/env python3
"""Extract two public manufacturer catalogs into reproducible review facts.

Download documents separately; this command is offline and never stores their
bodies in the repository. Repeated, inconsistent model numbers are quarantined
as a group, not turned into extra products or resolved by picking a row.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review/imports/2026-09-15-manufacturer-catalogs'
NUMBER = r'\d+(?:\.\d+)?'
HARDING_ROW = re.compile(
    rf'^\s*(\d+)\s+(?:(\d+)\s+)?([A-Za-z0-9]+)\s+'
    rf'(≥?{NUMBER})\s+(≥?{NUMBER})\s+(≤?{NUMBER})\s+'
    rf'(≤?{NUMBER})\s+(≤?{NUMBER})\s+({NUMBER})\s*$'
)


def number(token):
    value = float(token.lstrip('≥≤').removesuffix('V'))
    if value <= 0:
        raise ValueError(f'non-positive catalog value: {token}')
    return int(value) if value.is_integer() else value


def measurement(quantity, token, unit):
    item = {'quantity': quantity, 'value': number(token), 'unit': unit}
    if token.startswith('≥'):
        item.update(statistic='minimum', is_lower_bound=True)
    elif token.startswith('≤'):
        item.update(statistic='maximum', is_upper_bound=True)
    return item


def harding_rows(text):
    rows = []
    pages = text.rstrip('\f\n').split('\f')
    if len(pages) != 37 or '2019 Lithium Polymer Cell Selection Guide' not in pages[0]:
        raise ValueError('expected the 37-page Harding 2019 selection guide')
    for page, body in enumerate(pages, 1):
        for line in body.splitlines():
            if '≥' not in line:
                continue
            match = HARDING_ROW.fullmatch(line)
            if not match:
                raise ValueError(f'unparsed Harding row on page {page}: {line!r}')
            row_id, series, model, *values = match.groups()
            fields = [('capacity', 'mAh'), ('voltage', 'V'), ('thickness', 'mm'),
                      ('width', 'mm'), ('length', 'mm'), ('mass', 'g')]
            rows.append({
                'row_id': int(row_id), 'model': model,
                'locator': {'page': page, 'section': f'Selection table, row {row_id}',
                            'quote': ' '.join(line.split())},
                'measurements': [measurement(q, v, u) for (q, u), v in zip(fields, values)],
            })
    ids = [r['row_id'] for r in rows]
    # The original document omits number 1351. Do not invent the missing row.
    if ids != [i for i in range(1, 1373) if i != 1351]:
        raise ValueError('Harding source row reconciliation failed')
    return rows


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            if self.table is not None:
                raise ValueError('nested table: source structure changed')
            self.table = []
        elif tag == 'tr' and self.table is not None:
            # HTML permits an omitted </tr>; this source uses it for headers.
            if self.row is not None:
                self.table.append(self.row)
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def lipol_rows(html):
    parser = Tables()
    parser.feed(html)
    header = ['model', 'capacity (mah)', 'voltage (v)', 'length (mm)',
              'width (mm)', 'thickness (mm)']
    rows = []
    if len(parser.tables) != 4:
        raise ValueError('expected four LiPol specification tables')
    for table_no, table in enumerate(parser.tables, 1):
        if [c.lower() for c in table[0]] != header:
            raise ValueError(f'LiPol table {table_no}: unexpected columns')
        for row_no, cells in enumerate(table[1:], 1):
            if len(cells) != 6 or not re.fullmatch(r'LP[A-Za-z0-9]+', cells[0]):
                raise ValueError(f'LiPol table {table_no} row {row_no}: {cells!r}')
            if not all(re.fullmatch(NUMBER + r'V?', v) for v in cells[1:]):
                raise ValueError(f'LiPol non-numeric specification: {cells!r}')
            fields = [('capacity', 'mAh'), ('voltage', 'V'), ('length', 'mm'),
                      ('width', 'mm'), ('thickness', 'mm')]
            rows.append({
                'row_id': f'{table_no}:{row_no}', 'model': cells[0],
                'locator': {'section': f'Specification table {table_no}, data row {row_no}',
                            'quote': ' '.join(cells)},
                'measurements': [measurement(q, v, u) for (q, u), v in zip(fields, cells[1:])],
            })
    if len(rows) != 452:
        raise ValueError(f'expected 452 LiPol source rows, found {len(rows)}')
    return rows


def normalize_model(model):
    return re.sub(r'[^a-z0-9]', '', model.lower())


def reconcile(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[normalize_model(row['model'])].append(row)
    candidates, excluded, duplicates = [], [], []
    for key, group in sorted(groups.items()):
        signatures = {json.dumps(r['measurements'], sort_keys=True) for r in group}
        if len(signatures) > 1:
            excluded.append({'model_key': key, 'reason': 'conflicting_specs_for_same_model',
                             'rows': group})
            continue
        representative = group[0]
        values = {m['quantity']: m['value'] for m in representative['measurements']}
        wh = values['capacity'] * values['voltage'] / 1000
        wh_per_l = wh * 1e6 / (values['thickness'] * values['width'] * values['length'])
        wh_per_kg = wh * 1000 / values['mass'] if 'mass' in values else 0
        if wh_per_l > 1500 or wh_per_kg > 500:
            excluded.append({'model_key': key, 'reason': 'energy_density_requires_source_clarification',
                             'rows': group})
            continue
        candidates.append(representative)
        if len(group) > 1:
            duplicates.append({'model_key': key, 'kept_row_id': representative['row_id'],
                               'duplicate_rows': group[1:]})
    return candidates, excluded, duplicates


def source_document(key, path, rows, retrieved):
    if key == 'harding-energy':
        manufacturer = 'Harding Energy'
        source = {
            'uid': 'src/harding-energy-lithium-polymer-selection-2019',
            'kind': 'datasheet', 'title': '2019 Lithium Polymer Cell Selection Guide',
            'url': 'https://www.hardingenergy.com/wp-content/uploads/2019/03/HEI-Lithium-Polymer-Cell-Selection-Guide-2019.pdf',
            'revision': '2019',
            'note': 'Historical manufacturer catalog; present availability is unverified. '
                    'Dimensions cover bare cells, excluding protection boards and assemblies, '
                    'and the manufacturer asks customers to verify dimensions. '
                    'The printed voltage is stored as voltage with any printed lower bound, '
                    'not as an operating cutoff. Capacity test conditions are absent.',
        }
    else:
        manufacturer = 'LiPol Battery Co., Ltd.'
        source = {
            'uid': 'src/lipol-battery-new-models-2013', 'kind': 'manufacturer_web',
            'title': 'LiPo batteries new models 2013',
            'url': 'https://www.lipolbattery.com/lipo%20batteries.html',
            'revision': 'Page heading: new models 2013; revision date unstated',
            'note': 'Historical manufacturer listing; present availability is unverified. '
                    'Only row-specific specifications are extracted. General marketing claims '
                    'about cycle life, charge voltage, and self-discharge are not assigned '
                    'to individual models. Capacity test conditions are absent.',
        }
    source.update(license='proprietary', redistributable=False,
                  sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    source['note'] += f' Retrieved {retrieved}. Row quotes normalize whitespace.'
    candidates, excluded, duplicates = reconcile(rows)
    return {
        'schema_version': 1, 'manufacturer_slug': key, 'manufacturer': manufacturer,
        'retrieved_at': retrieved, 'source': source,
        'reconciliation': {
            'source_row_count': len(rows), 'candidate_count': len(candidates),
            'excluded_model_count': len(excluded),
            'excluded_row_count': sum(len(x['rows']) for x in excluded),
            'duplicate_row_count': sum(len(x['duplicate_rows']) for x in duplicates),
        },
        'rows': candidates, 'excluded': excluded, 'duplicates': duplicates,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harding-pdf', type=Path, required=True)
    parser.add_argument('--lipol-html', type=Path, required=True)
    parser.add_argument('--retrieved-at', required=True)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    text = subprocess.run(['pdftotext', '-layout', str(args.harding_pdf), '-'],
                          check=True, capture_output=True, text=True).stdout
    sources = [('harding-energy', args.harding_pdf, harding_rows(text)),
               ('lipol-battery', args.lipol_html, lipol_rows(args.lipol_html.read_text()))]
    args.output.mkdir(parents=True, exist_ok=True)
    for key, path, rows in sources:
        doc = source_document(key, path, rows, args.retrieved_at)
        (args.output / f'{key}.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False)+'\n')
        print(key, json.dumps(doc['reconciliation']))


if __name__ == '__main__':
    main()
