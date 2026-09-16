"""Build pending products from reconciled catalog facts, without networking."""
from copy import deepcopy
import json
from pathlib import Path

from import_manufacturer_catalogs import normalize_model

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / 'review/imports/2026-09-15-manufacturer-catalogs'


def documents():
    for path in sorted(IMPORTS.glob('*.json')):
        batch = json.loads(path.read_text())
        for row in batch['rows']:
            observations = []
            for value in row['measurements']:
                observation = deepcopy(value)
                observation['locator'] = deepcopy(row['locator'])
                if value['quantity'] == 'capacity':
                    observation['conditions'] = {'unstated': [
                        'rate_value', 'rate_unit', 'temperature_c', 'voltage_lower_v',
                    ]}
                observations.append(observation)
            yield {
                'schema_version': '1',
                'product': {
                    'uid': f"cell/{batch['manufacturer_slug']}/{normalize_model(row['model'])}",
                    'kind': 'cell', 'manufacturer': batch['manufacturer'],
                    'model_number': row['model'],
                    'is_rechargeable': True,
                },
                'source': deepcopy(batch['source']),
                'chemistry': {
                    'designation': 'Lithium polymer',
                    'locator': {'quote': batch['source']['title'],
                                'section': 'Catalog title / product-family heading'},
                },
                'observations': observations,
            }


def build(records, register):
    for document in documents():
        records.append(register(document))
