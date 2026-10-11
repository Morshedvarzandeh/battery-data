#!/usr/bin/env python3
"""Generate a BMS comparison from the ordinary component records."""
import argparse
from collections import Counter
from pathlib import Path
from build_component_catalog import entries

ROOT = Path(__file__).resolve().parents[1]
LABELS = {'manufacturer_listed': 'Manufacturer-listed', 'announced': 'Announced; not released',
          'legacy_support_only': 'Legacy support only', 'discontinued': 'Discontinued', 'unknown': 'Unknown'}


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def release_text(life):
    release = life['release']
    if release['status'] != 'documented':
        return 'Conflicting dates' if release['status'] == 'conflicting' else 'Not established'
    event = release['event']
    basis = 'launch announcement' if event['event_type'] == 'launch_announcement' else 'release'
    return f"[{event['date']}]({event['evidence']['url']}) ({basis}; {event['precision']} precision)"


def limit(doc, code):
    rows = [o for o in doc['observations'] if o['quantity'] == code]
    if not rows:
        return '—'
    return '; '.join(f"{o['value']:g} {o['unit'] if o['unit'] != '1' else ''}".strip()
                     + (f" ({o['conditions']['extra']['scope']})" if o['conditions']['extra']['scope'] != 'whole system' else '')
                     for o in rows)


def render(root=ROOT):
    rows = [(d, p, s) for d, p, s in entries(root) if d['product']['component_type'] == 'bms']
    counts = Counter(d['lifecycle']['market_status'] for d, _, _ in rows)
    lines = ['# BMS market comparison', '',
             f"**{len(rows)} records from {len({d['product']['manufacturer'] for d, _, _ in rows})} manufacturers/brands.** "
             f"{counts['manufacturer_listed']} manufacturer-listed, {counts['announced']} announced and "
             f"{counts['legacy_support_only']} legacy-support records.", '',
             'This is a growing, non-exhaustive market inventory. Records may describe a family, controller or explicit configuration; they are not all orderable SKUs. '
             'A manufacturer listing does not establish stock or suitability. BMS records do not count as batteries.', '',
             'Release dates retain their original precision and evidence. An announcement, planned availability, first shipment and datasheet revision are different events. '
             '“Not established” means no original release was verified; it is never replaced by the retrieval date. '
             'Open a product record for event history, scope, evidence and omitted/conflicting fields.', '',
             '## Products and release evidence', '',
             '| Manufacturer / product | Record scope / review state | Market status | Release evidence | Specifications |',
             '|---|---|---|---|---|']
    for doc, path, state in rows:
        p, b, life = doc['product'], doc['bms'], doc['lifecycle']
        lines.append('| ' + ' | '.join(map(cell, [f"[{p['manufacturer']} {p['model_number']}](../{path})",
            f"{b['identity_scope'].replace('_', ' ')} / {state}", LABELS[life['market_status']], release_text(life),
            f"[{'Datasheet' if doc['source']['kind'] == 'datasheet' else 'Product page'}]({doc['source']['url']})"])) + ' |')
    lines += ['', '## Supported limits and architecture', '',
              'A dash means unrecorded. Limits below retain their scope; a per-controller count must not be combined with an expanded-system voltage as if they describe one configuration. '
              'Cell-bank counts are available in the Elithion records and are not converted to cell counts.', '',
              '| Product | Architecture | Series channels: min → max | Pack voltage maximum | Balancing | Interfaces |',
              '|---|---|---|---|---|---|']
    for doc, path, _ in rows:
        b = doc['bms']
        lines.append('| ' + ' | '.join(map(cell, [f"[{doc['product']['manufacturer']} {doc['product']['model_number']}](../{path})",
            b['architecture'], limit(doc, 'bms_series_cells_min')+' → '+limit(doc, 'bms_series_cells_max'),
            limit(doc, 'bms_pack_voltage_max'), b['balancing'], ', '.join(b['interfaces']) or 'Not recorded']))+' |')
    lines += ['', '## Research coverage', '',
              '[Coverage gaps and next manufacturers](bms-coverage.json) · [Review and evidence notes](../docs/17-bms-market-and-release-dates.md) · '
              '[All electrical components](catalog.md)', '',
              'Generated with `python3 tools/build_bms_catalog.py`. Maintained by **Lemonergy** · '
              '[Data tools](https://lemonergy.com/data/) · [Free source library](../README.md)', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'components/bms.md'
    text = render()
    if args.check:
        if not path.exists() or path.read_text() != text:
            raise SystemExit('components/bms.md is stale')
    else:
        path.write_text(text)
    print('BMS catalog is current')


if __name__ == '__main__':
    main()
