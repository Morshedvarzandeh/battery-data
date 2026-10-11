"""Shared date projections; document age, product release and roadmaps stay distinct."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re

import jsonschema
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
TIMELINE = Path('technology/milestones.json')


def date_value(value):
    """Preserve printed precision. Never manufacture a month or day."""
    if value is None or value == '':
        return {'status': 'not_recorded', 'date': None, 'precision': None}
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}(-\d{2}(-\d{2})?)?', value):
        raise ValueError(f'invalid date: {value!r}')
    precision = {4: 'year', 7: 'month', 10: 'day'}[len(value)]
    # Padding is exclusively for calendar validation, never for storage/export.
    date.fromisoformat(value + {'year': '-01-01', 'month': '-01', 'day': ''}[precision])
    return {'status': 'recorded', 'date': value, 'precision': precision}


def record_dates(doc):
    """Derived view of one record, with explicit unknowns for every product kind."""
    src, life = doc.get('source', {}), doc.get('lifecycle', {})
    return {
        'source_document': date_value(src.get('document_date')),
        'source_revision': src.get('revision'),
        'source_retrieved': date_value(src.get('retrieved_at')),
        'lifecycle_checked': date_value(life.get('checked_at')),
        'release': deepcopy(life.get('release', {
            'status': 'not_researched',
            'note': 'No structured release-date review is recorded for this product.'})),
        'market_status': life.get('market_status', 'unknown'),
        'events': deepcopy(life.get('events', [])),
    }


def release_label(doc):
    release = record_dates(doc)['release']
    if release['status'] == 'documented':
        e = release['event']
        return f"{e['date']} ({e['precision']}; {e['event_type'].replace('_', ' ')})"
    return {'not_researched': 'Not researched', 'not_found': 'Not found in checked sources',
            'conflicting': 'Conflicting dates'}[release['status']]


def load_timeline(root=ROOT):
    """Validate curated platform milestones separately from accepted product facts."""
    path = Path(root) / TIMELINE
    if not path.exists():
        return []  # A small fixture/export checkout can contain only contributions.
    payload = json.loads(path.read_text())
    contribution = json.loads((ROOT / 'json-schema/cell-contribution.schema.json').read_text())
    schema = json.loads((ROOT / 'json-schema/technology-timeline.schema.json').read_text())
    registry = Registry().with_resource(contribution['$id'], Resource.from_contents(contribution))
    try:
        jsonschema.Draft202012Validator(schema, registry=registry,
                                      format_checker=jsonschema.FormatChecker()).validate(payload)
    except jsonschema.ValidationError as error:
        raise ValueError(f'{path}: {error.message}') from error
    from validate_contrib import check_events
    seen = set()
    for entry in payload['milestones']:
        if entry['id'] in seen:
            raise ValueError(f"duplicate milestone: {entry['id']}")
        seen.add(entry['id'])
        checked = entry['checked_at']
        errors = check_events(entry['id'], [entry['event']], checked)
        if checked > payload['reviewed_at']:
            errors.append('milestone check cannot be after review')
        if entry.get('source_document_date'):
            value = date_value(entry['source_document_date'])['date']
            if value > checked[:len(value)]:
                errors.append('source document date cannot be after check')
        if errors:
            raise ValueError('\n'.join(errors))
    return deepcopy(payload['milestones'])
