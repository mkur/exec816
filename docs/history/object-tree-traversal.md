# Incremental AES object tree traversal

[Plan](../plans/gem4xe/object-tree-traversal-plan.md) ·
[AES contract](../reference/aes.md#application-object-trees-and-forms) ·
[Evidence](../development/object-tree-traversal.json) ·
[History](README.md)

`ExecAESDraw` carries absolute coordinates through preorder traversal instead
of finding every object's ancestors again. The current origin lives in the
caller-local paint record. Eight saved parent origins occupy 32 stack bytes;
indices are relative to the requested subtree. A root draw uses its own
coordinates directly, and a non-root draw resolves its ancestors once.
Empty damage and hidden starting subtrees need no coordinate lookup.

The existing border, damage, visibility, strip, display-grant and UPDATE paths
remain in place. Children can extend outside clipped parents. Hidden branches,
sibling/ascent transitions and relative depth limits retain their behavior.
The walker adds no allocation, persistent geometry cache or shared traversal
state. Public object records, bindings and the extracted donor are unchanged.

## Development checks

The extended optimized object fixture passes on both walkers: 1,315 C and four
native assertions per run, with intact guards and restored heap/ownership.
All 23 state/damage/borrow results, 22 work-area frame digests and the
two-caller full-frame digest match. Existing text, edit, border and strip checks
also pass. Its independent parent-based model supplies preorder and absolute
positions; the pinned donor supplies primitive pixels. The corpus covers 23
requests, including deep non-root starts, depth clamping, hidden branches,
negative coordinates, outward borders, empty damage, disjoint visibility and
empty visibility. A test-only borrow failure after descent checks error/busy
state, END and a subsequent successful draw. Two independently scheduled
callers draw different trees and retire normally.

Host checks pass: 665 tests run, 661 passed and four historical-source checks
skipped. The unchanged matched workload passes 511 assertions, 67 measured
operations and eleven full-frame checks; every frame digest matches the
original baseline.

```sh
python3 tools/test_aes_server.py --suite objects --output build/object-tree-traversal/after
python3 tools/measure_magic_aes.py --output build/object-tree-traversal/measurement
python3 -m unittest discover -s tests -p 'test_*.py'
```

The deep-ancestor requests characterize existing subtree behavior; they do
not expand the supported application contract. No full qualification matrix,
loaded-application performance run or demo refresh is part of this slice.

## Measurement and resource record

The matched optimized capture uses the unchanged workload and observer from
the [original baseline](../development/magic-aes-baseline.json). Only
`c/calypsi/aes-objects.c` differs among its 349 archived source inputs.
Compiler, runtime, ROM, emulator and machine pins match.

| Workload | Baseline caller CPU median | Incremental caller CPU median | CPU reduction |
| --- | ---: | ---: | ---: |
| Five objects | 44.524 ms | 43.712 ms | 1.8% |
| 33 objects / 32 siblings | 123.997 ms | 105.929 ms | 14.6% |
| Nine nested objects | 171.267 ms | 167.423 ms | 2.2% |

The wide-tree target of roughly 10% is met. Its elapsed median falls from
154.168 to 131.590 ms. Root coordinate lookups fall from 5/33/9 to zero for
the three trees. Display admissions, releases, strip borrows and submissions
retain their counts. A non-root start has one coordinate-lookup call site
before traversal; subsequent transitions use saved origins.

Counter CPU medians change by less than 0.5%, the move control by -1.1% and
the immediate timer by +0.1%. Exposure caller CPU rises 6.8% while elapsed
falls 6.6%. Its trace shows the reason to treat controls separately: baseline
UPDATE RPC counts are `[1,1,1]`, versus `[0,0,1]` after the change; presenter
turn counts are `[4,4,4]` versus `[3,3,4]`. Work shifts to local UPDATE in two
samples, increasing inclusive caller UPDATE CPU from 32.645 to 38.312 ms and
reducing presenter CPU from 29.109 to 14.841 ms. Delivered damage, display
counts and final pixels match. Changed admission phase is consistent with
earlier traversal finishing sooner; exposure contains no object traversal.
These control differences are not counted as optimization gains. The small
sample set does not establish tail latency.

The emitted local frame grows from 72 to 104 bytes; the eight bytes of saved
direct-page registers are unchanged. `ExecAESDraw` grows from 2,137 to 2,559
code bytes. Total executable C bytes grow by 427; initialized and zero-filled
C data sizes are unchanged.

Reserved bank-zero growth is **0 fixed/root/kernel bytes, 0 bytes per public
Task and 0 idle bytes**, including guards, alignment and unused capacity.
Complete budget, Task-pool, runtime and phase-reservation maps match the
baseline. Stack watermarks describe the exercised calls rather than a
worst-case bound.

The matched benchmark's root stack touches 742 of 1,536 bytes, leaving 538
above the 256-byte protected floor; the baseline touched 731. The broader
object regression touches 1,090 root bytes, leaving 190 above that floor.
Presenter, peer and kernel guards remain intact, and neither run touches the
kernel interrupt reserve. Detailed watermarks and artifact hashes are in the
evidence record; captures and frozen inputs remain under
`build/object-tree-traversal/`.
