#!/usr/bin/env python3
"""Generate the catalog-wide date coverage report and scoped technology timeline."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import yaml
from catalog_dates import ROOT, load_timeline, record_dates


def load_records(root=ROOT):
    for path in sorted((root / 'contrib').rglob('*.y*ml')):
        raw = path.read_text()
        try:
            doc = json.loads(raw)
        except ValueError:
            doc = yaml.safe_load(raw)
        yield doc, path.relative_to(root).as_posix()


def render(root=ROOT):
    groups = defaultdict(list)
    records = list(load_records(root))
    for doc, path in records:
        p = doc['product']
        groups[p.get('component_type', p['kind'])].append(record_dates(doc))
    milestones = load_timeline(root)
    lines = ['# Dates and technology timeline', '',
        '[Battery models](README.md) · [Electrical components](../components/catalog.md) · [Date policy and data fields](../docs/18-technology-dates.md)', '',
        f'All **{len(records):,} accepted products** have a consistent date view. A missing date stays unknown; a recent source check does not make a product new.', '',
        '## Date coverage', '',
        'Counts reflect structured evidence in accepted records, not dates guessed from titles, filenames, source identifiers or Git commits. Not researched means no structured release review; not found means the checked sources supplied no release date. A dated launch does not establish first shipment.', '',
        '| Category | Products | Document date | Source retrieved | Lifecycle checked | Dated release / launch | Release not found | Release conflict | Release not researched |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for category, rows in sorted(groups.items()):
        count = lambda field: sum(r[field]['status'] == 'recorded' for r in rows)
        released = lambda state: sum(r['release']['status'] == state for r in rows)
        lines.append(f"| {category.replace('_', ' ')} | {len(rows):,} | {count('source_document'):,} | {count('source_retrieved'):,} | {count('lifecycle_checked'):,} | {released('documented'):,} | {released('not_found'):,} | {released('conflicting'):,} | {released('not_researched'):,} |")
    lines += ['', '## Technology milestones', '',
        f'**{len(milestones)} reviewed milestones.** These refer to the named manufacturer platform, family or product. They are not chemistry invention dates and are not copied onto unrelated catalog models. Plans remain plans until completion has its own evidence. This initial timeline is not exhaustive.', '',
        '| Event date / precision | Named subject and scope | Milestone | Source document date | Evidence checked | Evidence |',
        '|---|---|---|---|---|---|']
    # Exact precision is shown; lexical order is only navigation, not imputed days.
    for m in sorted(milestones, key=lambda m: (m['event'].get('date', ''), m['id']), reverse=True):
        e = m['event']
        display_date = e['date_text'] if e['event_type'] == 'planned_availability' else e.get('date', e['date_text'])
        lines.append(f"| {display_date} ({e['precision']}) | {m['manufacturer']} — {m['subject']} ({m['scope'].replace('_', ' ')}) | {e['event_type'].replace('_', ' ')} | {m.get('source_document_date', 'Not recorded')} | {m['checked_at']} | [Source]({e['evidence']['url']}) |")
    lines += ['', '### Scope and evidence limits', '']
    for m in milestones:
        lines.append(f"- **{m['manufacturer']} — {m['subject']}:** {m['scope_note']}")
    lines += ['', '## Product lifecycle evidence', '',
        'These events are derived from accepted product records. Unknown release dates remain visible in the manufacturer and component indexes. Document revisions and availability plans are shown with their event types.', '',
        '| Product | Release review | Event | Date / precision | Evidence |', '|---|---|---|---|---|']
    for doc, path in records:
        d = record_dates(doc)
        events = list(d['events'])
        if d['release'].get('event') and d['release']['event'] not in events:
            events.insert(0, d['release']['event'])
        for e in events:
            p = doc['product']
            lines.append(f"| [{p['manufacturer']} {p['model_number']}](../{path}) | {d['release']['status']} | {e['event_type'].replace('_', ' ')} | {e.get('date', e['date_text'])} ({e['precision']}) | [Source]({e['evidence']['url']}) |")
    lines += ['', '## Continue the date review', '',
        'Prioritise current sodium-ion, semi-solid, LG, EVE, CATL and CALB models, then BMS and the remaining electrical categories. Record a scoped lifecycle review with sourced events; never use a related platform launch as a model release. Historical catalog dates can be documented separately while current availability remains unknown.', '',
        'Patent priority, filing and publication dates stay in the [patent layer](../docs/08-patents.md); a patent publication does not establish a product launch.', '',
        'Generated with `python tools/build_date_catalog.py`. Source records and their accepted observation bytes are preserved.', '',
        'Maintained by **Lemonergy** · [Data tools](https://lemonergy.com/data/) · Free data on GitHub.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'catalog/dates.md'
    value = render()
    if args.check:
        if not path.exists() or path.read_text() != value:
            raise SystemExit('catalog/dates.md is stale')
    else:
        path.write_text(value)
    print('catalog date coverage and technology timeline are current')


if __name__ == '__main__':
    main()
