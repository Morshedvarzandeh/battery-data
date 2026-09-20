#!/usr/bin/env python3
"""Build the source-reviewed sodium, semi-solid and lithium cell batch offline.

The manifest contains factual transcriptions, not source bodies. --source-dir
checks original-byte hashes against locally held evidence; image-only tables
were visually inspected, not inferred from model codes or calculated values.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
NAME = '2026-09-21-sodium-semisolid-lithium-cells'
MANIFEST = ROOT / f'review/imports/{NAME}.json'
BATCH = ROOT / f'review/batches/{NAME}.json'
REGISTRY = json.loads((ROOT / 'json-schema/quantity-registry.json').read_text())


def slug(value):
    return re.sub(r'[^a-z0-9._-]+', '-', value.lower()).strip('-')


def observation(quantity, value, unit, locator, *, statistic=None, conditions=None, **extra):
    cond = deepcopy(conditions or {})
    absent = list(cond.pop('unstated', []))
    absent += [k for k in REGISTRY[quantity] if k not in cond and k not in absent]
    if absent:
        cond['unstated'] = absent
    result = {'quantity': quantity, 'value': value, 'unit': unit, 'locator': locator, **extra}
    if statistic:
        result['statistic'] = statistic
    if cond:
        result['conditions'] = cond
    return result


def source(meta):
    return {k: deepcopy(v) for k, v in meta.items()
            if k not in {'file', 'bytes', 'resolved_url', 'role'}}


def loc(row, section, quote):
    result = {'section': section, 'quote': quote}
    if row.get('page'):
        result['page'] = row['page']
    return result


def base(row, sources, observations, chemistry=None):
    product = {'uid': f"cell/{row['maker_slug']}/{slug(row['model'])}", 'kind': 'cell',
               'manufacturer': row['manufacturer'], 'model_number': row['model'],
               'is_rechargeable': True}
    for field in ('form_factor', 'aliases'):
        if row.get(field):
            product[field] = deepcopy(row[field])
    src = source(sources[row['source_key']])
    if row.get('note'):
        src['note'] += ' ' + row['note']
    result = {'schema_version': '1', 'product': product, 'source': src, 'observations': observations}
    if chemistry:
        result['chemistry'] = chemistry
    return result


def welion(row, sources):
    section = row['model']
    def add(q, v, unit, heading, quote, **kw):
        return observation(q, v, unit, loc(row, section + ' / ' + heading, quote), **kw)
    obs = [add('capacity', row['capacity_ah'], 'Ah', 'Capacity / Voltages',
               f"Typical {row['capacity_ah']} Ah", statistic='typical'),
           add('energy', row['energy_wh'], 'Wh', 'Capacity / Voltages',
               f"Typical {row['energy_wh']} Wh", statistic='typical'),
           add('nominal_voltage', row['voltage_v'], 'V', 'Capacity / Voltages',
               f"Voltages Nominal {row['voltage_v']} V", statistic='nominal')]
    # Standard/ultrafast rates are not identified as capacity test conditions,
    # nor as continuous maximum currents. Do not silently use them that way.
    for q, key, unit, label in [('specific_energy', 'specific_energy_wh_kg', 'Wh/kg', 'Gravimetric'),
                              ('energy_density', 'energy_density_wh_l', 'Wh/L', 'Volumetric')]:
        obs.append(add(q, row[key], unit, 'Energy Density', f'{label} {row[key]} {unit}'))
    for q, key, unit, axis in [('thickness', 'thickness_mm', 'mm', 'A Thickness'),
                              ('width', 'width_mm', 'mm', 'B Width'),
                              ('length', 'length_mm', 'mm', 'C Length'),
                              ('mass', 'mass_g', 'g', 'Weight')]:
        value, tolerance = row[key]
        obs.append(add(q, value, unit, 'Dimensions', f'{axis} {value} ± {tolerance} {unit}',
                       tol_plus=tolerance, tol_minus=tolerance))
    for direction in ('charge', 'discharge'):
        low, high = row[direction + '_temperature_c']
        for bound, value in [('min', low), ('max', high)]:
            obs.append(add('operating_temperature_' + bound, value, '°C', 'Temperatures',
                           f'{direction.title()} {low} to {high} °C',
                           statistic='minimum' if bound == 'min' else 'maximum',
                           conditions={'direction': direction}))
    chemistry = {'designation': 'NMC+', 'cathode_text': 'NMC+',
                 'electrolyte_text': 'Semi-Solid-State',
                 'locator': loc(row, section + ' / header', row['model'] + ' — NMC+; Semi-Solid-State')}
    return base(row, sources, obs, chemistry)


def lg(row, sources):
    model = row['model']
    def add(q, v, unit, heading, quote, **kw):
        return observation(q, v, unit, loc(row, model + ' column / ' + heading, quote), **kw)
    cond = {'temperature_c': 25, 'rate_value': row['capacity_rate_c'], 'rate_unit': 'C',
            'unstated': ['voltage_lower_v']}
    if row.get('capacity_reference_only'):
        cond['extra'] = {'reference_value_only': True}
    obs = [add('capacity', row['capacity_ah'], 'Ah', 'Capacity (Min, 25°C, 0.3C)',
               row['capacity_quote'], statistic=row['capacity_statistic'], conditions=cond)]
    if row.get('voltage_v') is not None:
        obs.append(add('nominal_voltage', row['voltage_v'], 'V', 'Nominal Voltage',
                       f"{model}: Nominal Voltage {row['voltage_v']} Vdc", statistic='nominal'))
    obs.append(add('energy', row['energy_wh'], 'Wh', 'Energy', row['energy_quote'],
                   statistic=row.get('energy_statistic')))
    for q, key, unit in [('specific_energy', 'specific_energy_wh_kg', 'Wh/kg'),
                          ('energy_density', 'energy_density_wh_l', 'Wh/L')]:
        stat = row['density_statistic']
        obs.append(add(q, row[key], unit, 'Energy Density (Min)',
                       f"{model}: {row[key]} {unit}" + (' (nom)' if stat == 'nominal' else ' (Min header)'),
                       statistic=stat))
    obs.append(add('mass', row['mass_g'], 'g', 'Weight', row['mass_quote'],
                   statistic=row.get('mass_statistic')))
    # Explicitly ordered dimensions only. JH4's reversed axes are held.
    for dim, value in row.get('dimensions_mm', {}).items():
        obs.append(add(dim, value, 'mm', 'Dimension', row['dimension_quote'],
                       statistic=row.get('dimension_statistic'),
                       conditions={'extra': {'dimension_basis': row['dimension_quote']}}))
    chemistry = {'designation': row['cathode'], 'cathode_text': row['cathode'],
                 'anode_text': row['anode'],
                 'locator': loc(row, model + ' column / Chemistry',
                                f"{model}: {row['cathode']}/{row['anode']}")}
    return base(row, sources, obs, chemistry)


def hina(row, sources):
    def add(q, v, unit, quote, **kw):
        return observation(q, v, unit, loc(row, row['model'] + ' specification image', quote), **kw)
    obs = [add('capacity', row['capacity_ah'], 'Ah', f"标称容量 {row['capacity_ah']}Ah", statistic='nominal'),
           add('nominal_voltage', row['voltage_v'], 'V', f"标称电压 {row['voltage_v']:.1f}V", statistic='nominal'),
           add('specific_energy', row['specific_energy_wh_kg'], 'Wh/kg',
               f"能量密度 >{row['specific_energy_wh_kg']}Wh/kg", statistic='minimum', is_lower_bound=True,
               conditions={'extra': {'source_comparator': '>'}}),
           add('cycle_life', row['cycles'], 'cycles', row['cycle_quote'],
               statistic='minimum', is_lower_bound=True,
               conditions={'rate_value': row['cycle_rate'], 'rate_unit': row['cycle_rate_unit'],
                           'extra': {'source_comparator': '>', 'end_of_life_criterion': 'not stated',
                                     'rate_direction': 'not stated'}})]
    # A general working temperature is not a charging temperature guarantee.
    for bound, value in [('min', -40), ('max', 60)]:
        obs.append(add('operating_temperature_' + bound, value, '°C', '工作温度 -40°C~60°C',
                       statistic='minimum' if bound == 'min' else 'maximum'))
    return base(row, sources, obs, {'designation': 'Sodium-ion',
                'locator': loc(row, 'Na-labelled cell / model identity',
                               row['model'] + ' — ' + row['aliases'][0] + ' — Na')})


def catl(row, sources):
    section = row['model'] + ' / basic parameters (printed pages 15–16)'
    capacity = row['capacity_ah']
    obs = [observation('capacity', capacity, 'Ah', loc(row, section, f'额定容量[Ah] {capacity}'), statistic='rated'),
           observation('mass', row['mass_kg'], 'kg', loc(row, section, f"电芯重量[kg] {row['mass_kg']}")),
           observation('cycle_life', row['cycles'], 'cycles',
                       loc(row, section, f"循环寿命[次] [25°C, 0.5P/0.5P, 70%SOH] ≥{row['cycles']}"),
                       statistic='minimum', is_lower_bound=True,
                       conditions={'temperature_c': 25, 'rate_value': 0.5, 'rate_unit': 'P',
                                   'direction': 'symmetric', 'unstated': ['dod_pct'],
                                   'extra': {'end_of_life_soh_pct': 70, 'soh_definition': 'not stated'}})]
    return base(row, sources, obs, {'designation': 'LFP', 'cathode_text': 'LFP',
                'locator': loc(row, section, f'{capacity}Ah LFP')})


def eve(row, sources):
    def add(q, v, unit, heading, quote, **kw):
        return observation(q, v, unit, loc(row, row['model'] + ' / ' + heading, quote), **kw)
    obs = [add('capacity', row['capacity_ah'], 'Ah', 'Specifications / nominal capacity',
               f"{row['model']}: nominal capacity {row['capacity_ah']}Ah", statistic='nominal')]
    if row.get('voltage_v'):
        obs.append(add('nominal_voltage', row['voltage_v'], 'V', 'Specifications / nominal voltage',
                       f"{row['model']}: nominal voltage {row['voltage_v']}V", statistic='nominal'))
    value, tolerance = row['mass_g']
    obs.append(add('mass', value, 'g', 'Specifications / weight' if row['model'] != 'MB30' else 'Weight',
                   f"{row['model']}: {value}g ± {tolerance}g", tol_plus=tolerance, tol_minus=tolerance))
    cycle_cond = {'extra': {'end_of_life_criterion': 'not stated'}}
    if row['model'] == 'LF206':
        cycle_cond.update(temperature_c=25, rate_value=0.5, rate_unit='C', direction='discharge',
                          extra={'charge_rate_value': 1, 'charge_rate_unit': 'C',
                                 'end_of_life_soh_pct': 80, 'soh_definition': 'not stated'})
    # LF235L's life graphic calls itself LF356L; do not inherit its SOH or
    # test temperature. MB30's headline rates are not a stated life protocol.
    obs.append(add('cycle_life', row['cycles'], 'cycles', row['cycle_section'], row['cycle_quote'],
                   statistic='nominal', conditions=cycle_cond))
    for direction in ('charge', 'discharge'):
        if direction + '_temperature_c' not in row:
            continue
        low, high = row[direction + '_temperature_c']
        for bound, value in [('min', low), ('max', high)]:
            obs.append(add('operating_temperature_' + bound, value, '°C', 'Specifications',
                           f'{direction.title()} temperature {low} to {high} °C',
                           statistic='minimum' if bound == 'min' else 'maximum',
                           conditions={'direction': direction}))
    if row.get('specific_energy_wh_kg'):
        obs.append(add('specific_energy', row['specific_energy_wh_kg'], 'Wh/kg', 'Comparison introduction',
                       f"MB30 ({row['specific_energy_wh_kg']}Wh/kg)"))
    if row.get('dimensions_mm'):
        for dim, value in row['dimensions_mm'].items():
            obs.append(add(dim, value, 'mm', 'Specifications / dimensions', row['dimension_quote']))
    return base(row, sources, obs, {'designation': 'LFP', 'cathode_text': 'Lithium iron phosphate',
                'locator': loc(row, 'Product title / chemistry', row['chemistry_quote'])})


def calb(row, sources):
    section = row['section']
    obs = [observation('capacity', row['capacity_ah'], 'Ah', loc(row, section, row['capacity_quote']),
                       statistic='nominal' if row['model'] == 'L173F314' else None)]
    if row.get('voltage_v'):
        obs.append(observation('nominal_voltage', row['voltage_v'], 'V', loc(row, section, row['voltage_quote']), statistic='nominal'))
    if row.get('cycles'):
        obs.append(observation('cycle_life', row['cycles'], 'cycles', loc(row, section, '15000次循环寿命'),
                               conditions={'extra': {'claim_scope': 'manufacturer launch announcement',
                                                      'end_of_life_criterion': 'not stated'}}))
        obs.append(observation('calendar_life', 25, 'year', loc(row, section, '产品核心参数达到15000次循环寿命、25年日历寿命'),
                               conditions={'extra': {'end_of_life_criterion': 'not stated'}}))
    if row.get('energy_density_wh_l'):
        obs.append(observation('energy_density', row['energy_density_wh_l'], 'Wh/L',
                               loc(row, section, '≥440Wh/L 能量密度'), statistic='minimum', is_lower_bound=True))
    chemistry = None
    if row.get('chemistry_quote'):
        chemistry = {'designation': 'LFP', 'cathode_text': 'Lithium iron phosphate (LFP)',
                     'locator': loc(row, section, row['chemistry_quote'])}
    return base(row, sources, obs, chemistry)


BUILDERS = {'welion': welion, 'lg': lg, 'hina': hina, 'catl': catl, 'eve': eve, 'calb': calb}


def build(manifest):
    docs = [BUILDERS[r['family']](r, manifest['sources']) for r in manifest['rows']]
    docs.sort(key=lambda d: d['product']['uid'])
    if len({d['product']['uid'] for d in docs}) != len(docs):
        raise ValueError('Repeated cell identity in manifest')
    return {'schema_version': 1, 'batch': NAME,
            'origin': 'Visually inspected manufacturer specifications and public primary evidence; see review/imports/' + NAME + '.md',
            'candidate_count': len(docs), 'candidates': [{'document': d} for d in docs]}


def verify_sources(manifest, directory):
    for key, meta in manifest['sources'].items():
        raw = (directory / meta['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta['sha256']:
            raise ValueError(f'{key}: evidence bytes changed; inspect before updating facts')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--source-dir', type=Path)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    if args.source_dir:
        verify_sources(manifest, args.source_dir)
        print(f"Verified {len(manifest['sources'])} original source hashes")
    batch = build(manifest)
    rendered = json.dumps(batch, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if BATCH.read_text() != rendered:
            raise SystemExit('Batch is stale; run tools/import_chemistry_cells.py')
    else:
        BATCH.write_text(rendered)
    count = sum(len(e['document']['observations']) for e in batch['candidates'])
    print(f"{batch['candidate_count']} cells / {count} observations; pending review")


if __name__ == '__main__':
    main()
