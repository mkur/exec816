# Device I O and GUI latency implementation plan

[Plans index](README.md) · [Device API](../reference/device-io.md)

Reduce the remaining observation/submission overhead, then measure visible GUI
latency against the original HY4 limits. The
[caller-dispatch baseline](../development/caller-device-dispatch.json) records
0.703 ms CheckIO, 0.394 ms DoIO and 1.115 ms SendIO median charged CPU. Each
slice below is executable and committed after its selected checks.

## IL1 Observe completion in the caller

Move CheckIO to a checked caller-side helper. Read the byte-wide completion
type once and return NULL while pending or the original full pointer otherwise.
Preserve Task-only entry checks and the observation-only contract: no collection,
signal clearing or ownership transfer. Completion fields precede terminal
publication, so the read may legitimately observe either side of a concurrent
completion. Remove the obsolete kernel selector/path and update generated
bindings and timing markers together. Public signatures and layouts stay fixed.

Validate pending, quick, replied and already-collected requests, repeated checks
without dequeue, far-pointer results and native register/stack context in small
raw/optimized probes. Run optimized timer binding/expiry/cancel checks, host
checks and an idle desktop I/O measurement against the retained baseline.

## IL2 Remove redundant timer polling

Add passive timing boundaries for native timer entry, snapshot, exit and Poll.
Measure the IL1 image before changing the exit protocol. Audit every Leave
caller and the native-work path through Permit, including nested Forbid.

Prefer retaining the pending hint and releasing the edit gate, then using the
existing following Permit as the service opportunity. Adopt this only when
emitted tests prove no lost expiry across queue publication, VBI during editing,
gate release and nested exclusion. Keep the forced hint needed when the first
request becomes due during insertion; do not require another VBI to recover it.
Preserve completion budgets, cancellation ordering and raw-VBI restrictions.
No new timer-specific kernel operation or scheduler policy is introduced.

Run targeted interrupt-boundary regression, queue saturation/FIFO expiry,
concurrent cancellation, clock-snapshot and C API cases. Repeat I/O timing with
the same observer, separating actual exit work from work moved into Permit.

## IL3 Rerun visible GUI latency

Build current native controls, registered-idle AES clients and continuously
active AES clients for both the panel and AS0 raw-pointer fixture. Run the
original panel protocol (10 gestures per idle/scroll/disk load with intermediate
pixel observation) and pointer protocol (30 moves and 30 buttons, quiet panel).
Apply the frozen AS0 allowances and matched native-control comparisons; retain
all failures. Record completed GEM traffic, disk/console progress, ownership,
guards, input-consumption, button-pixel and scanout timing. Add bounded current
idle/disk/scroll call windows to connect API costs with GUI results.

Report whether HY4 passes its existing gates; a completed measurement slice may
retain a failed latency gate. Keep continuous workload and gesture definitions
unchanged. This is development validation, not release qualification or a demo
refresh. OF816 packaging remains unchanged.

## Memory and records

Each slice targets zero additional reserved bank-zero bytes, fixed, per public
Task and idle, including guards, alignment and unused capacity. Preserve stack
and upper-memory reservations. Record source/image hashes, compiler/ROM/emulator
pins, actual test scope and timing limitations in development evidence and the
AES execution history. Update current contracts as behavior changes.

## Status

IL1 is complete; [development evidence](../development/io-latency-il1.json)
records caller-local observation and selected checks. IL2 is complete; its
[development evidence](../development/io-latency-il2.json) records the native
boundary tests and before/after timer measurements. IL3 is pending.
