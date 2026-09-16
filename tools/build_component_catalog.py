#!/usr/bin/env python3
"""Build a browsable component index from accepted files and the review queue."""
import argparse
from collections import Counter
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def entries(root=ROOT):
    rows = []
    for path in sorted((root / 'contrib').rglob('*.yaml')):
        raw = path.read_text()
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            doc = yaml.safe_load(raw)
        if doc['product']['kind'] == 'component':
            rows.append((doc, path.relative_to(root).as_posix(), 'accepted'))
    index = json.loads((root / 'review/index.json').read_text())
    for row in index['candidates']:
        if row['kind'] == 'component' and row['state'] == 'pending_review':
            rows.append((json.loads((root / row['candidate_file']).read_text()),
                         row['candidate_file'], 'pending review'))
    uids = [doc['product']['uid'] for doc, _, _ in rows]
    if len(uids) != len(set(uids)):
        raise ValueError('A component appears more than once across accepted and pending records')
    return sorted(rows, key=lambda row: row[0]['product']['uid'])


def render(root=ROOT):
    categories = json.loads((root / 'components/categories.json').read_text())['categories']
    rows = entries(root)
    counts = Counter(state for _, _, state in rows)
    lines = ['# Electrical component catalog', '',
             'Generated from the accepted library and review queue. Run `python tools/build_component_catalog.py` to refresh.', '',
             f"**{counts['accepted']} accepted; {counts['pending review']} pending review.** Component records are separate from the battery count.", '',
             'The record link contains every value, unit, condition and page/section locator. Datasheets are linked; proprietary PDFs are not redistributed.', '']
    for category, label in categories.items():
        lines += [f'## {label}', '', '| Manufacturer / model | State | Specifications | Source |', '|---|---|---:|---|']
        for doc, path, state in rows:
            p, s = doc['product'], doc['source']
            if p['component_type'] != category:
                continue
            lines.append(f"| [{p['manufacturer']} {p['model_number']}](../{path}) | {state} | {len(doc['observations'])} | [Datasheet]({s['url']}) |")
        lines.append('')
    lines += ['---', '', 'Maintained by **Lemonergy** · [Battery library](../catalog/README.md) · [API access for accepted records](https://lemonergy.com/#measure)', '', 'The public library is free. Manufacturer datasheets remain attributed to their original publishers.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'components/catalog.md'
    value = render()
    if args.check:
        if not path.exists() or path.read_text() != value:
            raise SystemExit('components/catalog.md is stale')
    else:
        path.write_text(value)
    print('component catalog is current')


if __name__ == '__main__':
    main()
