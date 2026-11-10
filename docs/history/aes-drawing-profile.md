# AES object drawing profile

[GEM plans](../plans/gem4xe/README.md) ·
[Diagnostics](../guides/aes-latency-diagnostics.md) ·
[Evidence](../development/aes-drawing-profile.json) ·
[EC2 baseline](update-cache-completion.md#ec2-matched-development-gate) ·
[Display ownership](../reference/display.md#delegated-renderer-access)

This slice profiles the drawing pipeline with the exact optimized EC2
executable. It adds host observers and accounting checks. Guest instructions,
object workloads, renderer policy and compiler inputs are unchanged.

## Method and scope

The capture observes 72 linked C functions and five native display functions.
C entries, checked JSL successors and actual RTL instructions identify calls
using the full Task direct page and stack frame, including indirect callbacks,
tail calls and shared epilogues. The existing interrupt/context markers
separate caller CPU, other Tasks and native interrupts.

Each object case has two warmups followed by eight measured calls. The full
unchanged corpus retains its 67 measured operations, 16 warmups and eleven
frame checks. Only the three object cohorts receive the detailed drawing
breakdown. These are box trees; the available text and icon boundaries do
not establish text/icon performance.

Exclusive CPU buckets charge an interval once, with nested ownership,
polling, upload and submission work removed from their inclusive parents.
The bucket means reconcile to the mean CPU of public `objc_draw` for every
cohort. Individual routine costs remain inclusive. Add means across exclusive
buckets; medians from different buckets are not additive.

Graphics-state calls cover observed attribute/colour setters. The callback
setup remainder includes object decoding, geometry/clip helpers, the inline
copy of shared clip state and callback dispatch. Primitive rendering excludes
separately observed command construction, submission, upload and polling.
Unobserved or inlined helpers stay in their observed parent scope.

Each physical unit records the Enter-entry to Leave-return envelope, the
Enter-return to Leave-entry core and its callback. The core is a lower bound
on actual ownership. CPU, interrupts and off-Task time remain separate;
software polling time is not exact hardware BUSY duration.

Detailed C spans end at an observed RTL when available, immediately before
that instruction executes. The existing corpus comparison retains its original
caller-successor boundaries. That convention accounts for the roughly
0.000423 ms difference at a final RTL; it is not a guest timing change.

## Results

The capture passes 505 fixture assertions and eleven exact full-frame checks.
All nine original caller, elapsed and presenter medians reproduce EC2 exactly;
all original call-count distributions, settled cache/repair and pending damage
records, and exposure delivery match. The executable SHA-256 is identical.

Exclusive **mean caller CPU per object draw**, in milliseconds:

| Observed scope | Five objects | 33 siblings | Nine nested |
| --- | ---: | ---: | ---: |
| AES preparation/traversal/journal remainder | 3.124 | 14.937 | 5.879 |
| Borrow glue | 0.754 | 2.443 | 3.230 |
| Callback/object setup remainder | 8.194 | 27.544 | 38.536 |
| Graphics-state calls | 0.031 | 0.105 | 0.148 |
| Primitive wrappers/clipping | 0.997 | 3.138 | 4.474 |
| Fill/mask/glyph command construction | 2.417 | 7.864 | 22.287 |
| Submission/fence/transfer bookkeeping | 3.415 | 10.101 | 19.028 |
| Upload | 0.949 | 2.367 | 9.991 |
| Completion polling | 2.525 | 3.609 | 14.805 |
| Cursor/overlay remainder | 1.666 | 3.079 | 12.698 |
| Display Enter/Leave | 4.811 | 16.044 | 21.812 |
| **Total drawing CPU** | **28.883** | **91.232** | **152.887** |

Rounding applies. The cursor/overlay remainder includes its own setup and
record construction after separately classified submission/upload/polling.
Likewise, the primitive row is the observed wrapper cost after removing its
nested command and device work; it is not total pixel-rendering cost.

There are 12/40/56 borrows and 16/46/90 submissions per call. Across the eight
measured calls per case, all 96/320/448 units have successful ownership and
exactly one observed object callback. Native display Enter and Leave counts
match the borrows. Native `DISPLAY.Check`, `Valid` and `Delegated` have zero
calls within these object draws, consistent with the trusted owner paths.

| Known-held core observation | Five objects | 33 siblings | Nine nested |
| --- | ---: | ---: | ---: |
| Mean caller CPU per unit | 1.699 ms | 1.460 ms | 2.190 ms |
| Largest observed unit CPU | 3.262 ms | 2.820 ms | 3.854 ms |
| Largest observed unit elapsed | 8.049 ms | 7.876 ms | 7.935 ms |

These maxima describe the exercised stationary-input workloads. They do not
qualify pointer-motion latency, arbitrary application trees or hardware tails.

## Interpretation and next design candidate

Callback/object setup is the largest individual bucket: 28–30% of drawing CPU
for the small/wide cases and 25% for the nested case. The nested tree invokes
the callback and `App_just_draw` 56 times for nine objects. That makes a
caller-local prepared object description worth investigating: establish which
decoding/layout work can be done once per object while keeping current strip
clips and all shared GSX writes under the display grant. The entire remainder
is not removable; this record supplies a budget, not a predicted speedup.

The next cost to inspect is command-record construction. The nested case
calls `solid_record` 160 times; its inclusive mean is 15.424 ms within the
22.287 ms command bucket. Ownership and submission remain substantial too.
The measured attribute setters alone offer only 0.148 ms in the nested case;
their cost does not justify making shared-state caching the first change.

No rendering optimization, larger batch, longer ownership interval, new
synchronization or kernel/compiler change is implemented by this slice.

## Validation and resources

Seven focused accounting tests cover nested uploads/polls, exclusion of peer
CPU and interrupts, retained parent scopes, failed/truncated grants, callback
ownership and separate adjacent units. The host suite runs 675 tests:
671 pass and four expected historical-source audits are skipped.

All 863 production inputs match EC2. Frozen production and observer inputs,
raw traces and evidence hashes are retained. The same executable means zero
code/data growth and **0 fixed/root/kernel, 0 per public Task and 0 idle
reserved bank-zero bytes added**, including guards, alignment and unused
capacity. Upper-RAM, VRAM and stack reservations are unchanged.

The root watermark remains 750 of 1,536 bytes, with 530 bytes above the
256-byte protected floor. Kernel touched bytes remain 285 and its interrupt
reserve is untouched. Guards, exact application heap equality and bank
ownership restoration pass. This is development measurement; no full hosted
qualification, hardware qualification or demo refresh is made.

## Reproduction

Build and capture the unchanged guest workload:

```sh
python3 tools/measure_aes_drawing.py --output build/aes-drawing-profile/new
```

The recorded run reuses the frozen EC2 image:

```sh
python3 tools/measure_aes_drawing.py \
  --from-build build/update-cache-completion/ec2-build \
  --output build/aes-drawing-profile/capture
python3 tools/measure_aes_drawing.py --analyze-only \
  --output build/aes-drawing-profile/capture
```

Raw traces, per-call and per-unit observations, frozen sources and observer
inputs remain under `build/aes-drawing-profile/`.
