#!/usr/bin/env python3
"""Run the unchanged production workload beside Counter or a shell checksum."""
import argparse
from pathlib import Path

from native_program import ROOT
from qed_coexist_load import Loads
from test_qed_coexist import Coexistence, LOAD, check


class LoadedCoexistence(Coexistence):
    inputs = (Path(__file__), ROOT/'tools/qed_coexist_load.py', ROOT/'tools/qed_coexist_warm.py')

    def exercise(self, session):
        if self.cohort == 'peer':
            from qed_coexist_warm import warm
            warmed = warm(session)
        result = super().exercise(session)
        if self.cohort == 'peer':
            self.report['desktop_warmup'] = warmed
        return result

    def start_load(self, session, menus, click, editor, report):
        self.load = Loads(session, menus, click, editor, self.cohort, LOAD, report)
        self.load.start()

    def input_sample(self, name):
        self.load.sample(name)

    def held_form(self, editor):
        self.load.held_form()

    def expose(self, lines):
        self.load.expose(lines)

    def finish_load(self):
        self.load.finish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cohort', choices=['peer', 'checksum'], required=True)
    parser.add_argument('--bundle', type=Path, default=ROOT/'build/qed-delivery/separate-disk')
    parser.add_argument('--production', type=Path, default=ROOT/'build/qed-delivery/separate-disk/qed-production')
    parser.add_argument('--layout-from', type=Path, default=ROOT/'build/qed-separate-disk/layout-fixture')
    a = parser.parse_args()
    check(a.output.resolve(), a.bundle.resolve(), a.production.resolve(), a.layout_from.resolve(),
          a.cohort, factory=LoadedCoexistence)
    print('QED loaded coexistence passed:', a.cohort)
