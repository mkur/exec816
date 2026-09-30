#!/usr/bin/env python3
"""Publish passing slice reports with complete bank-zero accounting."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,sha256,require
from ports_budget import current


def publish(destination,paths):
    reports=[]
    for path in paths:
        path=path.resolve();report=json.loads(path.read_text())
        require(report['status']=='pass','Cannot publish failed/incomplete report: '+str(path))
        require(report.get('timing_verdict','pass')=='pass',
                'Functional success does not qualify failed serial timing: '+str(path))
        reports.append(dict(path=str(path.relative_to(ROOT)),sha256=sha256(path),report=report))
    record=dict(schema_version=1,status='pass',reports=reports,bank_zero=current(),
                limits=['Scope is the named cases in these reports; no eight-task serial or physical-hardware claim.'])
    destination.write_text(json.dumps(record,indent=2)+'\n')
    print('Published '+str(destination))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path);parser.add_argument('reports',type=Path,nargs='+')
    args=parser.parse_args();publish(args.destination,args.reports)
