#!/usr/bin/env python3
"""Offline, fail-closed extraction of the September 2026 LiPol review batch.

Only facts are committed. Supply the six downloaded HTML files and their
sources.json to --source-dir; source bodies remain outside the repository.
Repeated tables never count as independent products or independent testing.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import yaml

from check_duplicates import compact_identifier, normalize_manufacturer
from import_manufacturer_catalogs import Tables

ROOT = Path(__file__).resolve().parents[1]
BATCH = '2026-09-21-lipol-catalog-expansion'
MANUFACTURER = 'LiPol Battery Co., Ltd.'
IMPORT = ROOT / 'review/imports/2026-09-21-lipol-catalogs.json'
BATCH_FILE = ROOT / f'review/batches/{BATCH}.json'
NUMBER = r'\d+(?:\.\d+)?'
TWL = ['Model', 'Capacity', 'T(mm)', 'W(mm)', 'L(mm)']
LWT = ['Model', 'Capacity', 'L x W x T(mm)', 'Voltage']
SPLIT_LWT = ['Type', 'Capacity', 'L(mm)', 'W(mm)', 'T(mm)', 'Voltage']
BARE_TWL = ['Model', 'Capacity(mAh)', 'Thickness (mm)', 'Width (mm)', 'Length (mm)']
REQUIRED = {'capacity', 'voltage', 'length', 'width', 'thickness'}
CAPACITY_UNSTATED = ['rate_value', 'rate_unit', 'temperature_c', 'voltage_lower_v']

# Pin the observed layout as well as row counts/endpoints. A changed or
# truncated catalog must be inspected again, never silently imported.
SOURCES = {
    'lipol-1000-3000': {
        'path': '1000mah-to-3000mah-li-po-batteries/', 'primary': True,
        'title': '1000mAh to 3000mAh Li Po Batteries',
        'tables': [(TWL, 283, 'LP245367', 'LP504658'),
                   (LWT, 745, 'LP102050', 'LP504658'),
                   (LWT, 320, 'LP104343', 'LP983667'),
                   (LWT, 320, 'LP104343', 'LP983667')],
    },
    'lipol-3000-5000': {
        'path': '3000mah-to-5000mah-li-polymer-batteries/', 'primary': True,
        'title': '3000mAh to 5000mAh Li Polymer Batteries',
        'tables': [(LWT, 264, 'LP103773', 'LP496882'),
                   (LWT, 264, 'LP103773', 'LP496882'),
                   (LWT, 206, 'LP2884157', 'LP496884'),
                   (LWT, 206, 'LP2884157', 'LP496884')],
    },
    'lipol-5000-10000': {
        'path': '5000mah-to-10000mah-li-poly-batteries/', 'primary': True,
        'title': '5000mAh to 10000mAh Li Poly Batteries',
        'tables': [(TWL, 338, 'LP104373', 'LP8090100'),
                   (TWL, 327, 'LP2510115', 'LP9065126')],
    },
    'lipol-crosscheck-general': {
        'path': 'china-made-lithium-ion-polymer-battery/', 'primary': False,
        'title': 'China Made Lithium-ion Polymer Battery',
        'tables': [(BARE_TWL, 459, 'LP141921', 'LP124647')],
    },
    'lipol-crosscheck-1000': {
        'path': '1000mah-regular-lipo-battery-lp603450/', 'primary': False,
        'title': '1000mAh Regular LiPo Battery LP603450',
        'tables': [(['Battery type', 'Rechargeable LiPo Battery'], 12, 'Model', 'Expected Cycle Life'),
                   (SPLIT_LWT, 1234, 'LP102050', 'LP504658'),
                   (TWL, 267, 'LP353955', 'LP992365')],
        'assembly_model': 'LP603450',
    },
    'lipol-crosscheck-4800': {
        'path': 'li-polymer-batteries-lp105274-4800mah-with-pcm-and-wires-50mm-and-jst-phr-2/',
        'primary': False,
        'title': 'Li Polymer Batteries LP105274 4800mAh with PCM and wires 50mm and JST PHR-2',
        'tables': [(['Battery Type:', 'Rechargeable Li Polymer Batteries'], 17, 'Model:',
                    'Expected Cycle Life @(0.5C/0.5C)@23±5°C)'),
                   (SPLIT_LWT, 388, 'LP104273', 'LP476495')],
        'assembly_model': 'LP105274',
    },
}


def numeric(token, suffix=''):
    match = re.fullmatch(rf'({NUMBER})\s*{re.escape(suffix)}', token)
    if not match or float(match[1]) <= 0:
        raise ValueError(f'unsupported or non-positive value: {token!r}')
    value = float(match[1])
    return int(value) if value.is_integer() else value


def parse_row(key, table_no, row_no, header, cells):
    if len(cells) != len(header) or not re.fullmatch(r'LP[A-Za-z0-9]+', cells[0]):
        raise ValueError(f'{key} table {table_no} row {row_no}: unsupported row {cells!r}')
    values, errors = {}, []

    def add(quantity, token, suffix=''):
        # Blank voltage cells mean unstated, not a generic 3.7 V assumption.
        if not token:
            return
        try:
            values[quantity] = numeric(token, suffix)
        except ValueError as exc:
            errors.append(f'{quantity}: {exc}')

    add('capacity', cells[1], '' if header == BARE_TWL else 'mAh')
    if header in (TWL, BARE_TWL):
        for quantity, token in zip(('thickness', 'width', 'length'), cells[2:]):
            add(quantity, token)
    elif header == SPLIT_LWT:
        for quantity, token in zip(('length', 'width', 'thickness'), cells[2:5]):
            add(quantity, token)
        add('voltage', cells[5], 'V')
    elif header == LWT:
        dimensions = re.fullmatch(rf'({NUMBER})\s*[x×]\s*({NUMBER})\s*[x×]\s*({NUMBER})', cells[2])
        if dimensions:
            for quantity, token in zip(('length', 'width', 'thickness'), dimensions.groups()):
                add(quantity, token)
        else:
            errors.append('unsupported L x W x T dimensions')
        add('voltage', cells[3], 'V')
    else:
        raise ValueError(f'unsupported columns: {header!r}')
    return {
        'id': f'{key}:{table_no}:{row_no}', 'source_key': key,
        'primary': SOURCES[key]['primary'], 'table': table_no, 'data_row': row_no,
        'model': cells[0], 'cells': cells, 'values': values, 'parse_errors': errors,
    }


def extract(key, html):
    parser = Tables()
    parser.feed(html)
    expected = SOURCES[key]['tables']
    if len(parser.tables) != len(expected):
        raise ValueError(f'{key}: expected {len(expected)} tables, found {len(parser.tables)}')
    rows, assembly_tables = [], []
    for table_no, (table, (header, count, first, last)) in enumerate(zip(parser.tables, expected), 1):
        if (len(table) != count + 1 or table[0] != header
                or table[1][0] != first or table[-1][0] != last):
            raise ValueError(f'{key} table {table_no}: layout/row reconciliation failed')
        if len(header) == 2:
            # Individual protected assemblies have no explicit dimension axes.
            # Preserve their tables for review and hold those model identities;
            # do not merge assembly attributes into a catalog cell record.
            model = SOURCES[key]['assembly_model']
            if model not in table[1][1]:
                raise ValueError(f'{key}: unexpected assembly identity')
            assembly_tables.append({'source_key': key, 'table': table_no,
                                    'model': model, 'rows': table})
        else:
            rows.extend(parse_row(key, table_no, n, header, cells)
                        for n, cells in enumerate(table[1:], 1))
    return rows, assembly_tables


def existing_identities(root, own_uids):
    records = []
    counts = Counter()
    for folder in ('contrib/cells', 'contrib/components', 'review/candidates'):
        for path in sorted((root / folder).rglob('*.yaml')):
            contents = path.read_text()
            try:
                doc = json.loads(contents)
            except json.JSONDecodeError:
                doc = yaml.safe_load(contents)
            product = doc['product']
            if product['uid'] in own_uids:
                continue
            counts[folder] += 1
            if normalize_manufacturer(product['manufacturer']) != normalize_manufacturer(MANUFACTURER):
                continue
            records.append({'file': str(path.relative_to(root)),
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'product': product})
    return {'record_counts': dict(sorted(counts.items())), 'same_manufacturer_records': records}


def model_dimension_pattern_matches(model, values):
    """Screen for possible transcription errors, never derive dimensions.

    This is the pattern observed in this catalog, not a verified manufacturer
    naming rule. Exceptions need review; a match does not verify a dimension.
    """
    thickness = values['thickness']
    thickness_tokens = {f'{thickness * 10:02g}'}
    if thickness >= 10:
        thickness_tokens.add(f'{thickness:g}')
    return model.upper() in {
        f"LP{token}{values['width']:02g}{values['length']:02g}"
        for token in thickness_tokens
    }


def reconcile(rows, baseline, prior_holds, assembly_tables):
    existing = defaultdict(set)
    for record in baseline['same_manufacturer_records']:
        product = record['product']
        for name in [product['model_number'], *product.get('aliases', [])]:
            existing[compact_identifier(name)].add(product['uid'])
    assembly_holds = {compact_identifier(item['model']) for item in assembly_tables}
    groups = defaultdict(list)
    for row in rows:
        groups[compact_identifier(row['model'])].append(row)
    decisions = []
    for model, group in sorted(groups.items()):
        primary = [row for row in group if row['primary']]
        complete = [row for row in primary if REQUIRED <= row['values'].keys() and not row['parse_errors']]
        facts = defaultdict(set)
        for row in group:
            for quantity, value in row['values'].items():
                facts[quantity].add(value)
        conflicts = {q: sorted(v) for q, v in sorted(facts.items()) if len(v) > 1}
        decision = {'model_key': model, 'row_ids': [row['id'] for row in group],
                    'primary_row_count': len(primary), 'conflicts': conflicts}
        if not primary:
            status = 'crosscheck_only'
        elif model in existing:
            status = 'already_in_library_or_review'
            decision['existing_uids'] = sorted(existing[model])
        elif model in prior_holds:
            status = 'previous_unresolved_conflict'
        elif conflicts:
            status = 'conflicting_source_values'
        elif model in assembly_holds:
            status = 'protected_assembly_scope_requires_review'
        elif any(row['parse_errors'] for row in group):
            status = 'unsupported_source_value'
        elif not complete:
            status = 'missing_complete_primary_row'
        else:
            row = complete[0]
            v = row['values']
            # A review heuristic only. Printed voltage is NOT relabelled as
            # nominal, and this calculated proxy is NEVER a product observation.
            proxy = 1000 * v['capacity'] * v['voltage'] / (v['length'] * v['width'] * v['thickness'])
            if not 100 <= proxy <= 1000:
                status = 'dimension_capacity_sanity_check'
                decision['screening_proxy_wh_per_l'] = round(proxy, 3)
            elif not model_dimension_pattern_matches(row['model'], v):
                status = 'model_dimension_pattern_requires_review'
            else:
                status = 'pending_review'
                decision['representative_row_id'] = row['id']
                decision['uid'] = f'cell/lipol-battery/{model}'
        decision['disposition'] = status
        decisions.append(decision)
    return decisions


def document(row, metadata):
    key = row['source_key']
    locator = {'section': f"Specification table {row['table']}, data row {row['data_row']}",
               'quote': ' | '.join(row['cells'])}
    observations = []
    for quantity, unit in [('capacity', 'mAh'), ('voltage', 'V'),
                           ('length', 'mm'), ('width', 'mm'), ('thickness', 'mm')]:
        observation = {'quantity': quantity, 'value': row['values'][quantity],
                       'unit': unit, 'locator': deepcopy(locator)}
        if quantity == 'capacity':
            observation['conditions'] = {'unstated': CAPACITY_UNSTATED[:]}
        observations.append(observation)
    return {
        'schema_version': '1',
        'product': {'uid': f"cell/lipol-battery/{compact_identifier(row['model'])}",
                    'kind': 'cell', 'manufacturer': MANUFACTURER,
                    'model_number': row['model'], 'is_rechargeable': True},
        'source': {
            'uid': f'src/{key}-catalog-2026-09-21', 'kind': 'manufacturer_web',
            'title': SOURCES[key]['title'], 'url': metadata['url'],
            'retrieved_at': metadata['retrieved_at'], 'sha256': metadata['sha256'],
            'revision': 'Page revision and model availability date unstated',
            'license': 'proprietary', 'redistributable': False,
            'note': 'Pending manufacturer catalog transcription, not a laboratory measurement. '
                    'Only row-specific facts are extracted. The Voltage column is retained as '
                    'voltage; its statistic and operating limits are unstated. Capacity test '
                    'conditions, dimension tolerances, and bare-cell versus protected-assembly '
                    'dimension scope are unstated. PCM, connector, certification, cycle-life '
                    'and generic page claims are not assigned to this model. Availability is '
                    'unverified. Table numbers follow HTML document order; data rows exclude '
                    'the header. Row quotes normalize whitespace and insert column separators. '
                    'Repeated tables are deduplicated; cross-page conflicts are held separately.',
        },
        'chemistry': {'designation': 'Lithium polymer',
                      'locator': {'section': 'Catalog title / product-family heading',
                                  'quote': SOURCES[key]['title']}},
        'observations': observations,
    }


def make_batch(manifest):
    rows = {row['id']: row for row in manifest['rows']}
    metadata = {item['key']: item for item in manifest['sources']}
    candidates = []
    for decision in manifest['decisions']:
        if decision['disposition'] == 'pending_review':
            row = rows[decision['representative_row_id']]
            candidates.append({'document': document(row, metadata[row['source_key']])})
    return {'schema_version': 1, 'batch': BATCH,
            'origin': 'Offline manufacturer-table extraction; see review/imports/2026-09-21-lipol-catalogs.json. Pending review, no automatic acceptance.',
            'candidate_count': len(candidates), 'candidates': candidates}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-dir', type=Path, required=True)
    args = ap.parse_args()
    metadata = json.loads((args.source_dir / 'sources.json').read_text())
    if {m['key'] for m in metadata} != set(SOURCES) or len(metadata) != len(SOURCES):
        raise ValueError('exactly the six documented source downloads are required')
    rows, assemblies = [], []
    for meta in metadata:
        key = meta['key']
        expected_url = 'https://www.lipobattery.us/' + SOURCES[key]['path']
        body = (args.source_dir / f'{key}.html').read_bytes()
        if (meta['url'] != expected_url or meta['final_url'] != expected_url
                or meta['sha256'] != hashlib.sha256(body).hexdigest()
                or meta['bytes'] != len(body) or meta['retrieved_at'] != '2026-09-21'):
            raise ValueError(f'{key}: download provenance mismatch')
        extracted, details = extract(key, body.decode('utf-8'))
        rows.extend(extracted)
        assemblies.extend(details)
    own_uids = set()
    if BATCH_FILE.exists():
        own_uids = {item['document']['product']['uid'] for item in json.loads(BATCH_FILE.read_text())['candidates']}
    baseline = existing_identities(ROOT, own_uids)
    prior_path = ROOT / 'review/imports/2026-09-15-manufacturer-catalogs/lipol-battery.json'
    prior_holds = [item['model_key'] for item in json.loads(prior_path.read_text())['excluded']]
    decisions = reconcile(rows, baseline, prior_holds, assemblies)
    manifest = {
        'schema_version': 1, 'batch': BATCH, 'retrieved_at': '2026-09-21',
        'sources': metadata, 'baseline': baseline,
        'previous_exclusion_file': str(prior_path.relative_to(ROOT)),
        'previous_excluded_models': prior_holds,
        'individual_assembly_tables': assemblies,
        'reconciliation': {
            'source_catalog_row_count': len(rows),
            'primary_catalog_row_count': sum(row['primary'] for row in rows),
            'distinct_model_count': len(decisions),
            'primary_model_count': sum(item['primary_row_count'] > 0 for item in decisions),
            'model_dispositions': dict(sorted(Counter(d['disposition'] for d in decisions).items())),
        },
        'rows': rows, 'decisions': decisions,
    }
    batch = make_batch(manifest)
    if batch['candidate_count'] < 590:
        raise ValueError(f"only {batch['candidate_count']} eligible new candidates; do not weaken checks to meet target")
    for path, data in [(IMPORT, manifest), (BATCH_FILE, batch)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(manifest['reconciliation'], indent=2))
    print(f"Wrote {batch['candidate_count']} pending review declarations; accepted data unchanged.")


if __name__ == '__main__':
    main()
