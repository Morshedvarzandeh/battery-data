#!/usr/bin/env python3
"""What the accepted library states, and what it does not.

Coverage is the honest measure of a specification library. A record is
trustworthy because its values travel with their units, conditions and
sources — but a *library* is only as useful as the questions it can answer
for a whole population, and that is a function of how many records state
each quantity. A comparison chart drawn over thirteen impedance figures is a
chart about nothing.

This prints that measure for the accepted library: one row per quantity,
how many cells state it, and the analyses each one gates. It is the source
of the numbers in docs/10-acquisition-list.md, so the document can be
checked rather than believed:

    python tools/coverage_report.py                     # from contrib/
    python tools/coverage_report.py --snapshot cat.json # from an export
    python tools/coverage_report.py --markdown           # the doc's tables

Cells and primary cells only. Packs, modules and systems are a different
population and are counted separately at the end.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

CELL_KINDS = ('cell', 'primary_cell')

# The analyses each quantity gates. This is the whole point of the report: a
# missing quantity is not an abstract gap, it is a named chart that cannot be
# drawn, which is what makes the list a plan rather than a lament.
GATES = {
    'capacity': 'every ranking and density figure',
    'nominal_voltage': 'energy in Wh, and every Wh-per-something',
    'voltage': 'energy in Wh where no nominal voltage is stated',
    'mass': 'specific energy (Wh/kg)',
    'length': 'the box envelope, volume and Wh/L',
    'width': 'the box envelope, volume and Wh/L',
    'thickness': 'the box envelope, the thickness cohort and Wh/L',
    'diameter': 'the cylinder envelope, volume and Wh/L',
    'height': 'the cylinder envelope, volume and Wh/L',
    'cycle_life': 'capacity retention against cycles; cost per kWh-cycle',
    'capacity_retention': 'a measured fade curve rather than a single endpoint',
    'internal_resistance_dc': 'pack sag under load, usable power, a Ragone plot',
    'internal_resistance_ac': 'impedance comparison between cells',
    'max_continuous_discharge_current': 'current capability against capacity; C-rate headroom',
    'max_pulse_discharge_current': 'peak-power sizing',
    'max_continuous_charge_current': 'charge-time estimates',
    'specific_power': 'the Ragone plot (specific power against specific energy)',
    'operating_temperature_min': 'the temperature window a design must respect',
    'operating_temperature_max': 'the temperature window a design must respect',
    'self_discharge_rate': 'shelf life and storage loss',
    'energy': 'a stated energy to cross-check the derived one against',
    'specific_energy': 'a stated Wh/kg to cross-check the derived one against',
    'energy_density': 'a stated Wh/L to cross-check the derived one against',
}


def load_snapshot(path: Path) -> dict:
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def build_snapshot(root: Path) -> dict:
    """The same export the hosted API is built from, so the numbers match it."""
    from export_catalog_snapshot import build, git_revision  # noqa: PLC0415
    try:
        revision = git_revision(root)
    except Exception:  # noqa: BLE001 — a tarball has no git; the counts do not need one
        revision = '0' * 40
    return build(root, revision)


def quantities(records: list[dict]) -> Counter:
    counts = Counter()
    for entry in records:
        for quantity in {o['quantity'] for o in entry['record']['observations']}:
            counts[quantity] += 1
    return counts


def envelopes(records: list[dict]) -> dict:
    box = cylinder = 0
    for entry in records:
        stated = {o['quantity'] for o in entry['record']['observations']}
        if {'diameter', 'height'} <= stated:
            cylinder += 1
        elif {'length', 'width', 'thickness'} <= stated:
            box += 1
    return {'box': box, 'cylinder': cylinder, 'none': len(records) - box - cylinder}


def report(snapshot: dict) -> dict:
    records = snapshot['records']
    cells = [e for e in records if e['record']['product']['kind'] in CELL_KINDS]
    counts = quantities(cells)
    # Every quantity the registry gates an analysis on, stated or not: a
    # quantity no record carries must appear as a zero, or the report would
    # only ever list what the library happens to have.
    names = sorted(set(counts) | set(GATES), key=lambda n: (-counts[n], n))
    return {
        'products': len(records),
        'cells': len(cells),
        'kinds': dict(Counter(e['record']['product']['kind'] for e in records).most_common()),
        'manufacturers': dict(Counter(e['record']['product']['manufacturer'] for e in cells).most_common()),
        'envelopes': envelopes(cells),
        'dated_sources': sum(1 for e in records if (e['record'].get('source') or {}).get('document_date')),
        'quantities': [
            {
                'quantity': name,
                'cells': counts[name],
                'share_pct': round(counts[name] / len(cells) * 100, 1) if cells else 0.0,
                'gates': GATES.get(name, ''),
            }
            for name in names
        ],
    }


def as_markdown(data: dict) -> str:
    lines = [f"Cells and primary cells: **{data['cells']:,}** of {data['products']:,} accepted products.", '']
    lines += ['| Quantity | Cells stating it | Share | What it gates |', '|---|---:|---:|---|']
    for row in data['quantities']:
        if not row['gates'] and row['cells'] == 0:
            continue
        stated = f"{row['cells']:,}" if row['cells'] else '**none**'
        lines.append(f"| `{row['quantity']}` | {stated} | {row['share_pct']}% | {row['gates']} |")
    lines += ['', '| Manufacturer | Cells | Share |', '|---|---:|---:|']
    for name, cells in data['manufacturers'].items():
        lines.append(f"| {name} | {cells:,} | {round(cells / data['cells'] * 100, 1)}% |")
    envelope = data['envelopes']
    lines += ['', f"Envelopes: {envelope['box']:,} box, {envelope['cylinder']:,} cylinder, "
                  f"{envelope['none']:,} publish no dimensions at all.",
              f"Sources carrying a document date: {data['dated_sources']:,} of {data['products']:,}."]
    return '\n'.join(lines)


def as_text(data: dict) -> str:
    lines = [f"{data['cells']:,} cells and primary cells of {data['products']:,} accepted products", '']
    for row in data['quantities']:
        mark = ' ' if row['cells'] else '!'
        lines.append(f"{mark} {row['cells']:>6,}  {row['share_pct']:>5.1f}%  {row['quantity']:<34}  {row['gates']}")
    lines.append('')
    for name, cells in data['manufacturers'].items():
        lines.append(f"  {cells:>6,}  {name}")
    envelope = data['envelopes']
    lines.append('')
    lines.append(f"  envelopes: {envelope['box']:,} box, {envelope['cylinder']:,} cylinder, {envelope['none']:,} none")
    lines.append(f"  sources with a document date: {data['dated_sources']:,} of {data['products']:,}")
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default=str(ROOT), help='repository root to read contrib/ from')
    parser.add_argument('--snapshot', help='read a catalog snapshot export instead of contrib/')
    parser.add_argument('--markdown', action='store_true', help='print the tables docs/10-acquisition-list.md carries')
    parser.add_argument('--json', action='store_true', help='print the whole measurement as JSON')
    args = parser.parse_args(argv)

    snapshot = load_snapshot(Path(args.snapshot)) if args.snapshot else build_snapshot(Path(args.root))
    data = report(snapshot)
    if args.json:
        print(json.dumps(data, indent=1, sort_keys=True))
    elif args.markdown:
        print(as_markdown(data))
    else:
        print(as_text(data))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
