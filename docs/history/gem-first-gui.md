# GEM-first GUI execution

[Design](../plans/gem4xe/gem-first-gui-design.md) ·
[Implementation plan](../plans/gem4xe/gem-first-gui-implementation-plan.md) ·
[Current AES contract](../reference/aes.md)

## GF0 — Native GUI and disk baseline

Status: GF0 passes at the development tier. The
[execution record](../development/gem-first-gf0.json) retains five complete
functional cohorts and separately scoped CPU observations. Production GUI
policy is unchanged.

The fixture loads two private copies of one APP through Program/Process. Its
startup wrapper selects positions; `examples/gem-counter/counter.c` is unchanged.
The disk cohort performs four complete 16 KiB read/write/Close passes against
a fresh SDFS disk through native DOS, the filesystem worker and SIO at the
pinned nominal 57.6k profile with accurate disk timing. A host filesystem audit
checks saved bytes and allocation independently of the guest.

Separate cases replace the second Counter with a small GEM I/O client. They
distinguish an application's own blocked event loop, deliberate UPDATE-held
I/O, and cooperative cancellation during an active wire transaction. They do
not replace the Counter body with a test implementation.

All four 16 KiB read/write passes finish with exact persisted bytes and valid
allocation. Both Counters continue painting during disk work. A synchronous
read leaves its own event-loop count fixed at two while its peer advances;
UPDATE-held I/O also blocks the peer's paint until ownership is released.
Explicit public Process BREAK cancels the active read with error 304, followed
by normal request/application retirement and restored ownership. The initial
fixture incorrectly used GEM Stop, which queues a close and lets the read finish;
that failed attempt remains in `cancel-close-only-failure/`.

The idle census has seven public Tasks: root/controller, filesystem, SIO, two
applications, heartbeat and console/presenter. Both Counter Tasks occupy
ordinary 1,312-byte pools. Two AES registrations and two GEM windows coexist.
The fixture's root and heartbeat use Yield loops; `idle` means no explicit
post-startup disk load, not a quiescent production desktop.

Captured digit pixels during disk work decode to A `2,4,6,8` and B `1,3,5,7`.
Counter A remains inactive. Pixel changes and model/paint counts establish
progress; Counter increments are not a wall clock. The idle capture separates
charged Task CPU, off-Task time and native interrupt time using the existing
passive context observer.

Instruction-history tracing of the complete disk job exceeded a 600-second
host timeout after about 64 seconds of guest execution. Preserve that failed
attempt under `build/gem-first-gui/gf0/disk-trace-timeout/`. The replacement
protocol separates a bounded CPU-observation prefix from the full functional
job. The prefix intentionally terminates its private emulator and claims no
filesystem completion, persistence or cleanup. The full run keeps four passes
and the 18,000-frame guest completion bound. Host observation cost is not a
guest latency failure or permission to relax existing latency limits.

The pointer control records completion of a paced eight-pixel diagonal gesture.
Its elapsed interval includes the scheduled physical movement, so it is not
per-transition input latency or a pass of the original IL3 protocol. Full
latency gates remain open. This is focused development evidence, separate from
hosted release and physical-hardware qualification.

Reproduce the functional cohorts with:

```sh
python3 tools/test_gem_first.py --output build/gem-first-gui/gf0
python3 tools/test_gem_first.py --output build/gem-first-gui/gf0 --reuse
```

The first command builds; `--reuse` checks the frozen executable, seed media
and fixture source inputs. Current production-source edits do not turn a
reused frozen image into a current build. Keep candidate builds in another
directory. For the separate timing prefix:

```sh
python3 tools/test_gem_first.py --output build/gem-first-gui/gf0 \
  --reuse --case disk --trace-prefix
```

The fixed twelve-Task pool, root/kernel/idle stacks, guards, alignment and unused
capacity match the current platform map: **0 added fixed/root/kernel,
0 per-public-Task and 0 idle reserved bank-zero bytes**. The test adds upper-RAM
fixture/application storage and occupies existing Task pools. Preserve the
frozen emitted-input files recorded in the evidence before implementing policy
changes. The narrowest observed public-pool margin is 163 bytes above its
protected floor; no pool enlargement was needed. Host checks run 687 tests:
683 pass and four historical checks skip.
