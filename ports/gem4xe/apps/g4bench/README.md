# G4BENCH for Exec816

Pinned donor inputs and adaptation sources for the loadable benchmark.
See the [implementation plan](../../../../docs/plans/gem4xe/g4bench-port-implementation-plan.md).

`tools/build_g4bench.py --output DIR` prepares inputs below `DIR/source` and
builds a normal private C image. The donor checkout is never modified.
The initial slice provides the window/event shell and a timer.device clock.

The donor application and its adaptations retain GPL-2.0-or-later and the
pinned `COPYING`, `COPYING.LIB` and `docs/licence.md` notices. The Exec MIT
interface/example grant does not relicense this application.
