#!/usr/bin/env python3
"""Audit the current production link and delivery scope without publishing it."""
import argparse
import json
from pathlib import Path
from qed_delivery import inventory

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--production', type=Path, required=True)
    p.add_argument('--provider', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = inventory(a.production.resolve(), a.provider.resolve())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print('QED link inventory:', len(result['link_units']), 'units; delivery questions:', result['unresolved'])
