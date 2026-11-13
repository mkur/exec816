# Terminal notification signal separation

[History](README.md) · [Plan](../plans/gem4xe/terminal-wake-plan.md) ·
[Wait audit](viewer-wait-audit.md) · [TW1 evidence](../development/terminal-wake-tw1.json)

## TW1 Signal ownership

Terminal now allocates a dedicated console-view notification signal after
creating its synchronous session reply port. Subscriptions and the external
AES wait use that notification mask. A pending RPC reply therefore cannot
trigger the next refresh through `MU_EXEC`.

Failure to allocate the extra bit deletes the new reply port and returns
failure with no retained port, bit or heap allocation. Close unbinds input and
unsubscribes views before clearing/freeing the notification signal, then
deletes the reply port. A zeroed/partially opened record and repeated Close
remain safe. The message-port implementation and the 100 ms timer are unchanged.

The private Terminal record grows from 5,846 to 5,847 upper-memory bytes. Its
new bit-number field is appended at offset 5,846; existing fields retain their
offsets. The emitted layout probe checks the reply pointer, notification mask
and bit number along with the existing cell/pixel fields. No public ABI changes.

[test_gem_terminal_wake.py](../../tools/test_gem_terminal_wake.py) compiles the
actual platform source with real Exec signal/port calls. Both raw and optimized
native runs pass **35 checks**, covering complete signal exhaustion, one free
bit, exact rollback, distinct masks, a reply queued before `WaitPort`, unrelated
signal preservation, teardown ordering, pending notification clearing, repeated
Close and three reopen cycles. Stack/domain guards, ownership and EXIT pass.
Console/AES endpoints in this small probe are stubs that check ordering and wait
parameters; they do not establish real timer, input or console-view behavior.

The host suite passes 710 tests with four existing historical-source skips.
The complete eight-Task probe `bank_zero_budget`, `task_pools` and
`runtime_reservations` match the frozen IC2 probe. Reserved bank-zero growth is
**zero bytes** for fixed services, root, kernel, idle and each public Task,
including guards, alignment and unused capacity. The extra signal uses one bit
of existing Task storage. Upper-memory and VRAM reservations are unchanged;
the private allocation grows by one byte before allocator rounding.

```sh
python3 tools/test_gem_terminal_wake.py --output build/terminal-wake/probe-opt --mode opt
python3 tools/test_gem_terminal_wake.py --output build/terminal-wake/probe-raw --mode raw
python3 -m unittest discover -s tests -p 'test_*.py'
```

## TW1b Loaded APP signal bindings

The first package link exposed a missing binding: `AllocSignal`, `FreeSignal`
and `SetSignal` existed in resident C code but not the loaded APP import table.
APP ABI 37 appends these three reusable public calls, preserving all 127 earlier
ordinals. The generated native constant and current contract are updated; all
apps must be rebuilt. The kernel API and calling conventions are unchanged.

The [existing loaded relocation probe](../../tools/test_c_program.py) now
allocates bit 31, posts/snapshots/consumes its full-width mask and frees it,
checking exact signal-allocation return. Both raw and optimized APPs pass
25 native checks/four completed executions on the identical optimized native
provider, with two private instances, repeated execution, relocation, heap
return, stack/domain guards and EXIT. Generated-definition checks and 710 host
tests pass (four existing skips). See [TW1b evidence](../development/terminal-wake-tw1b.json).

The upper binding table grows nine bytes within its existing reservation.
Complete eight-Task bank-zero maps still match IC2: zero growth for fixed
services, root, kernel, idle and each public Task, including guards, alignment
and unused capacity. Upper-memory and VRAM reservations are unchanged.

## TW2 Packaged measurements

[TW2 evidence](../development/terminal-wake-tw2.json) records the exact package,
source/observer hashes, comparisons and artifacts. Runtime sources match
`4ff5c3e6`; the before runtime is `067b2eff`. The additional APP bindings are
included in this delivered before/after comparison: all ten apps are rebuilt
for ABI 37. Compiled C objects outside Terminal are byte-identical, including
all viewer objects. Terminal's changed objects are main (the allocation size)
and platform. The resident C ELF and all executable/data segments are identical;
the appended serialized RAM desktop APP changes for the new import table.
The original 127 import ordinals are preserved. APP import thunks/relocation
metadata change, so the comparison is not a binary-identical viewer relink.

The pinned optimized release compiler, machine/ROM, font, document, geometry,
pointer placement and physical key workload are unchanged. The current sparse
observer resolves exactly the original 1,328 baseline PCs and decoded sites.
New captures also include the existing full drawing observer, reusing its
analyzer to check rendering work in the same run. Each scene measures four
alternating page and four line actions. Idle retains Terminal and desktop;
Counter/disk adds the same Counter and four-pass 64 KiB native I/O workload.

| Scene/action | Mean viewer CPU before → after, ms | Repaint median before → after, ms | Median reduction |
| --- | ---: | ---: | ---: |
| Idle page | 436.191 → 433.277 | 1063.645 → 808.645 | 24.0% |
| Idle line | 436.964 → 433.537 | 1007.523 → 832.666 | 17.4% |
| Counter/disk page | 478.235 → 476.339 | 1844.849 → 1426.533 | 22.7% |
| Counter/disk line | 471.917 → 477.958 | 1777.739 → 1566.368 | 11.9% |

Mean completion across all eight actions falls 21.8% in idle and 18.2% under
load. Mean viewer CPU falls 0.7% in idle and rises 0.4% under load. The latency
improvement accompanies less competition while the viewer is ready to run.
It does not require lower viewer CPU in every cohort. Four actions per operation
do not establish latency tails or a general worst-case guarantee.

| Mean time per repaint, ms | Idle before | Idle after | Loaded before | Loaded after |
| --- | ---: | ---: | ---: | ---: |
| Viewer CPU | 436.6 | 433.4 | 475.1 | 477.1 |
| IRQ while viewer selected | 95.2 | 94.5 | 155.5 | 152.0 |
| Viewer ready, off CPU | 437.5 | 222.3 | 975.0 | 631.9 |
| Viewer blocked, off CPU | 79.4 | 69.2 | 238.9 | 248.0 |
| Unclassified initial prefix | 1.6 | 1.6 | 3.2 | 2.6 |
| Total | 1050.2 | 821.1 | 1847.8 | 1511.5 |

While the viewer is ready, Terminal/root combined CPU falls from 299.7 to
134.9 ms in idle, and 403.9 to 184.1 ms under load. IRQ execution during those
peers' selected intervals falls from 64.6 to 29.0 ms and 129.1 to 63.6 ms,
respectively. CPU and IRQ are distinct costs. Inclusive source scopes overlap
and must not be summed. Scene/UPDATE admission still blocks; it is not removed
by this change, and the loaded blocked budget increases slightly.

### Wake verification

Live snapshots show reply mask `$00200000` and notification mask `$00400000`
in Terminal's Task; other Tasks have independent bit namespaces. In the timed
idle/loaded intervals, 38/63 fully contained event waits return `MU_TIMER` and
none returns `MU_EXEC`. Neither trace clears a reply bit through the external
event mask, and both contain zero complete feedback chains and zero controller
retry yields. The original idle audit had 97 `MU_EXEC` returns and 95 complete
feedback chains. Genuine console notifications and physical input remain
covered by the real Terminal integration scenario.

Root-to-Terminal reply posts within the measured intervals fall from 120 to 45
in idle and 172 to 70 under load. These are interval counts, not fixed-duration
rates. The 100 ms timer, ordinary refresh query, controller collection policy,
normal Task preemption and drawing limits are unchanged.

### Functional and package checks

The optimized real Terminal scenario uses the packaged native image/APPs and
an isolated writable SYS copy. Three exact viewport/exposure pixel checkpoints,
keyboard editing, new session, session switching, cancelled/confirmed close,
stack/domain guards, ownership and EXIT pass. The focused resource and loaded
APP probes above cover the new allocation failure/cleanup boundaries.

An additional integration pass with `--observe-wakes` records 207 completed
Terminal waits: 83 include `MU_EXEC` and 120 include `MU_TIMER`, with distinct
view/reply masks. The external mask contains only the view bit, so these are
genuine console notifications during keyboard/output/session work. This checks
the notification path directly rather than relying on the timer fallback.
Its three pixel checkpoints, guards, ownership and EXIT also pass.

Both observed viewer scenes pass whole-work-area pixels, boundary no-op, warmed
heap return, guards, ownership and EXIT. Counter progresses and persisted disk
bytes match. All thirteen rendering-work fields match the frozen baseline:
18 rows, 20 text calls, one bar, 21 physical grants, 23 launches, five generic
submissions and 31 fences, with unchanged records-per-list counts/staging work. Six paint
bands and seven BEGIN/END pairs remain. Repaint timing excludes scanout;
settled scanout pixels are checked separately.

Both untraced companions pass. All timing edges, inter-action gaps, relevant
runtime counters and pixels match exactly, with zero clock-origin offset in
both scenes. All four runs cold-boot the extracted package and retain the
250-frame/five-second OF816 autoboot.

Two loaded line samples observe five `paints` increments at completion. The
linked viewer code stores `dirty=0` at TextRun offset `$1808`, before storing
the incremented counter at `$1840`. IRQ sampling can therefore see completed
drawing before that bookkeeping store. The source and emitted viewer objects
are unchanged; all drawing fields and seven physical BEGIN/END pairs still
match, proving six bands. Replay reproduces the same counter lag. The evidence
records these two samples and the checked instruction sequences. The completion
criterion remains the original IRQ-observed dirty clear after physical fences
and END_UPDATE; neither guest code nor timing criteria were changed.

The package audit passes 30 ZIP checksums, all 69 SYS file identities and nine
disk APP identities. The tenth APP is the serialized RAM desktop. OF816,
matching dedicated AltirraOS ROM, PAL/8×/63-high-bank/VBXE FX 1.26 configuration,
five-second standard shell/prime autoboot, writable SYS and MD5/ARC/EDX with
overlays/notices are retained. ZIP SHA-256:
`84ae2ab3e36bf831f0f99bb0ed7263f02af85506746f3721a1ab841bc22e6a01`.

The checker now requires the standard SDX `WORK/EDIT.TXT`; `WORK/SAMPLE.TXT`
is required only for a selected QED package, matching the builder's existing
conditional seed. This corrects the audit, without changing package contents.
An initial capture stopped before timing because a host observer reused a field
variable name. The corrected observer passes a new host regression for retaining
Process identity while reading port/view masks. The host suite passes **711
tests**, with four existing historical-source skips. Generated APP definitions
pass their freshness check.

### Memory and delivery

Complete before/after demo budgets, pools and runtime reservations match.
Reserved bank-zero growth is **zero bytes** for fixed services, root, kernel,
idle and each public Task, including guards, alignment and unused capacity.
Upper-memory and VRAM reservations also grow by zero. Terminal uses one extra
existing signal bit; its private allocation grows one byte before rounding.
The binding table adds nine payload bytes inside its existing reservation.

Terminal's executable C segment grows from 19,423 to 19,618 bytes; its APP file
grows from 22,445 to 22,680 bytes, including added import/fixup metadata. Its
64 KiB-separated image span remains 66,473 bytes. Observed Terminal stack use
grows 821→830 bytes in idle and 887→901 under load in the same 1,312-byte pool.
The loaded observation leaves 155 untouched bytes above the 256-byte interrupt
reserve; guards pass. Watermarks are lower bounds on depth, not worst-case proof.

```sh
python3 tools/build_demo.py --output build/terminal-wake/demo --gem-desktop --release-compiler
python3 tools/trace_viewer_waits.py --bundle build/terminal-wake/demo --output build/wake-idle --count 4 --observe --drawing
python3 tools/trace_viewer_waits.py --bundle build/terminal-wake/demo --output build/wake-idle-replay --count 4
python3 tools/trace_viewer_waits.py --bundle build/terminal-wake/demo --output build/wake-loaded --count 4 --load build/gui-baseline/load --observe --drawing
python3 tools/trace_viewer_waits.py --bundle build/terminal-wake/demo --output build/wake-loaded-replay --count 4 --load build/gui-baseline/load
python3 tools/audit_gem_demo.py --bundle build/terminal-wake/demo --output build/wake-package-audit.json
python3 tools/test_gem_terminal.py --build build/terminal-wake/integration-build --output build/wake-terminal --observe-wakes
```

Use fresh output directories. The current launcher is
`build/terminal-wake/demo/launch-altirra.command`; distribute
`build/terminal-wake/demo/exec816-demo.zip`. The retained integration fixture
links `program` to the package root and `apps`, `selected` and `c-image.json`
to its bitmap-console directory, with a writable copy of `exec816.atr` named
`system.atr`. These are focused development
results. QED, the separate missing-Terminal startup scenario, full release and
hosted-system/hardware qualification remain outside this slice.
