#!/usr/bin/env python3
"""Build GitHub-readable manufacturer/model indexes from accepted battery records."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def build():
    groups=defaultdict(list)
    for path in sorted((ROOT/'contrib').rglob('*.yaml')):
        raw=path.read_text()
        try: doc=json.loads(raw)
        except json.JSONDecodeError: doc=yaml.safe_load(raw)
        p=doc['product']
        if p['kind']=='component': continue
        maker=p['uid'].split('/')[1]
        groups[maker].append((doc,path))
    output={}
    kinds=Counter(d['product']['kind'] for rows in groups.values() for d,_ in rows)
    total=sum(kinds.values())
    head=['# Battery datasheets and specifications — Lemonergy','',
          f'Browse **{total:,} accepted battery product records** by manufacturer. Each model links to the recorded specifications and its original source.','',
          '[About Lemonergy](../README.md#lemonergy) · [Component datasheets](../components/catalog.md) · [Patent research](../docs/08-patents.md)','',
          '## Find a model','',
          'Choose a manufacturer below, then use your browser’s **Find** command to search the model number. The linked YAML records are readable text; no database setup is needed.','',
          '| Manufacturer | Accepted products | Browse |','|---|---:|---|']
    for maker,rows in sorted(groups.items(),key=lambda item:item[1][0][0]['product']['manufacturer'].casefold()):
        name=rows[0][0]['product']['manufacturer']
        head.append(f'| {name} | {len(rows):,} | [Models and source documents](manufacturers/{maker}.md) |')
        page=[f'# {name} battery datasheets and specifications','',
              f'{len(rows):,} accepted product records in the **Lemonergy Battery Data** library.','',
              '[All manufacturers](../README.md) · [About Lemonergy](../../README.md#lemonergy)','',
              'The record contains the values, original units, qualifiers, test conditions and page/section evidence. Source documents may be historical; inclusion does not establish current availability or suitability for a design.','',
              '| Model | Product type | Record | Original source |','|---|---|---|---|']
        for doc,path in sorted(rows,key=lambda row:row[0]['product']['model_number'].casefold()):
            p,s=doc['product'],doc['source']
            label=p['model_number'].replace('|','\\|')
            source=f"[Source]({s['url']})" if s.get('url') else 'URL not supplied'
            page.append(f"| {label} | {p['kind'].replace('_',' ')} | [Specifications](../../{path.relative_to(ROOT).as_posix()}) | {source} |")
        page += ['', '---', '', 'Maintained by **Lemonergy** · [Use this data in your tools](../../docs/10-hosted-api.md) · The public library is free.']
        output[Path('catalog/manufacturers')/f'{maker}.md']='\n'.join(page)+'\n'
    head+=['','## Coverage and review','',
           ' | Product type | Count |','|---|---:|']
    head += [f"| {kind.replace('_',' ')} | {n:,} |" for kind,n in sorted(kinds.items())]
    head+=['','Pending candidates are listed separately in the [review queue](../review/index.json). Components and patent publications are excluded from these battery counts.','',
           'Most additions in the September 2026 expansion are historical lithium-polymer catalogs. Read the [review report](../docs/09-catalog-review-2026-09.md) for evidence limits and held records.','',
           'Maintained by **Lemonergy** · [Paid API for engineering workflows](../docs/10-hosted-api.md) · Free data on GitHub.','',
           'Generated from accepted contributions with `python tools/build_browse_catalog.py`.']
    output[Path('catalog/README.md')]='\n'.join(head)+'\n'
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    output=build()
    expected={ROOT/rel for rel in output}
    extras=set((ROOT/'catalog/manufacturers').glob('*.md'))-expected
    if extras: raise SystemExit('Stale manufacturer pages: '+', '.join(str(p) for p in sorted(extras)))
    for rel,text in output.items():
        path=ROOT/rel
        if args.check:
            if not path.exists() or path.read_text()!=text:raise SystemExit(f'{rel} is stale')
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    print(f'{len(output)-1} manufacturer indexes are current')


if __name__=='__main__':main()
