"""Compiler-generated DP layout used by package and runtime validators."""
import json
from pathlib import Path

SPEC = json.loads((Path(__file__).resolve().parents[1] / 'abi/native-dp.json').read_text())
DP = SPEC['direct_page']
FIELDS = {field['name']: field for field in DP['fields']}
POINTERS = tuple(alias['offset'] for alias in DP['scratch_aliases'])
