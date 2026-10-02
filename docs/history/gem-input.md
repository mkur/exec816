# Hosted GEM input and events

[History](README.md) · [Plan](../plans/gem4xe/input-and-events-implementation-plan.md) ·
[Design](../plans/gem4xe/input-and-events-design.md) · [Current VDI contract](../reference/gem-vdi.md)

## I0 Media recovery and shutdown

[I0 evidence](../development/gem-input-i0.json) records 18 combined graphics/media
cases and ten service cases in each compiler mode, plus replay of the exact
optimized production image. All 277 host tests passed, with four historical
source audits skipped. These are development checks, not hosted qualification.

The service reserves STOP's reply port and packet before publishing readiness.
Startup failures unwind both; shutdown allocates nothing, including under real
heap exhaustion. Queued and active drawing retains its separate exact-reply
collection obligation. Steady service/client heap use is now 2,656 rounded bytes:
the existing 192-byte STOP reserve moves earlier in the lifetime, without raising
peak heap use. The emitted server record is 84 bytes, four bytes larger in upper
RAM. Fixed, each public Task and private-idle bank-zero deltas are all zero,
including guards, alignment and unused capacity.

The launcher preserves the first file error, collects rendering and retires the
service before returning to text. Wrong, short and corrupt files display the
matching disk name and return normally after a 250-tick text hold. A missing
drive produces an uncertain SIO timeout under the existing device contract.
It restores text and retires GEM/console, displays the reset requirement, then
retains the offline bus at `$FF93`. I0 corrects the plan's original blanket
normal-return requirement; it does not weaken SIO's late-traffic protection.

The runner checks retained text and physical screen bytes, scene pixels, C
contexts, guards, stack headroom, presentation restoration and ownership. Its
offline-state observer uses the descriptor offset from the SIO ABI because
`SD_OFFLINE` is not exported in the native label map. No target change was needed
for that observer correction. The permanently busy blitter case still retains
the pending graphics request and its resources for reset.

The optional ZIP now pairs `gem-vdi/Exec-gem-vdi.xex` with the distinct
`gem-vdi/graphics.atr`. It was rebuilt through `build_demo.py --gem-vdi` with
OF816, the standard five-second autoboot, root disk, pinned ROM and notices.
Exact production pixels, text, archive membership and every shipped checksum
passed. The unchanged OF816 shell routes retain their G6 evidence; I0 does not
claim a new shell qualification. See the [run guide](../guides/gem-vdi.md).

## I1 Input records and C bridge

[I1 evidence](../development/gem-input-i1.json) records raw/optimized emitted
layout and value probes for the 32-byte lease, 16-byte configuration and 24-byte
event. The machine-readable manifest generates Action!, C and assembly fields
and constants plus the Calypsi offset/size probe. Runtime admission deliberately
returns UNSUPPORTED in this slice; no successful hardware stub is exposed.

C arguments retain their full huge-pointer values until validation rejects bank
zero, odd addresses, absent/read-only memory, bank crossings and values beyond
24 bits. The ordinary module accepts image-writable storage or public heap
storage. Emitted probes cover valid records ending exactly at a bank boundary,
crossing records, invalid configuration fields, all lease fields, signed event
coordinates and a full 32-bit route argument. Unsupported calls leave their
output storage unchanged. The bridge uses a Task-local stack packet and the
existing caller-clobbered DP area.

Both modes passed 60 C assertions plus native value/layout checks, interrupted
C computation, callee-preserved DP, kernel DP, stack/domain guards, ownership
and display/aperture preservation. The host suite passed 281 tests with four
historical audits skipped; the generator's freshness check passed. Root stack
use and all emitted extents are in the evidence. This is ABI development evidence,
not keyboard or hosted qualification.

The bridge table uses 24 upper-RAM bytes. Records are caller-owned; no input Task
or live capture storage is added yet. The existing two C banks remain reserved
at 131,072 bytes. Fixed, each public Task and private-idle bank-zero increments
remain zero, including guards, alignment and unused capacity. Task packet profile
6 is unchanged; I2 migrates producer callers before advancing it.

## I2 Shared producer admission

[I2 evidence](../development/gem-input-i2.json) records the profile-7 producer
migration. Serial and keyboard now use source-qualified Bind, Release and Drain.
Admission validates the complete CARD source, native pointer and 32-bit mask,
a live retained target, and its allocated signals. Both recipient and controller
remain protected until publication stops and queued wakes retire. Active Drain
keeps the binding; wrong-controller retirement faults before mutation. Console's
private admission selectors and its obsolete adapter module are removed.

Each compiler mode passed 19 source/lifetime cases, five Task lifetime cases,
six SIO lifetime cases, two creation/profile cases, console rollback/restart,
two physical keyboard/SIO acquisition orders, an NMI posting control and the C
gateway/context control. Invalid sources include values with nonzero high bytes;
mask checks cover both words. The previous profile is rejected through an
otherwise valid emitted packet. Each keyboard posting control observed 84 real
NMI checkpoints, with hardware state restored. All 283 host tests passed, with
four historical source audits skipped; generated definitions are current.

The larger instrumented console image initially exceeded the native code region
by 100 bytes. Sharing its test-only VBI wait removed repeated instructions and
kept the existing reservation; the extra two-byte return frame exists only in
probe builds. BootConfig.Init is excluded from public Task entry admission as a
boot helper, keeping the existing sixteen-entry capacity. These changes do not
alter production producer semantics or expand reservations.

Two existing 12-byte upper-RAM binding records provide the source state. Fixed,
each public Task and private-idle bank-zero deltas are zero, including guards,
alignment and unused capacity; native code reservation growth is also zero.
These are focused development checks. Reusable acquisition and console capture
migration remain I3, and no interactive GEM, mouse, AES or new hosted
qualification is claimed by I2.

## I3 Reusable keyboard capture

[I3 evidence](../development/gem-input-i3.json) records the shared input library
and console migration. Keyboard hardware ownership, the 64-slot raw ring and
native/emulation entry paths now live in `input.s`, independently of console
presentation. Serial retains first service at shared IRQ entry. No input Task,
second keyboard producer or private kernel service is introduced.

Acquire copies configuration before activating the source and retains the
consumer's signal and address-stable Task lease. Every operation checks that
original lease and acquisition; copied/stale leases fail. Consumption and release
belong to the consumer, while bounded route operations may run on another Task's
stack under Forbid. Sixteen generic tags retain captured identity, cancellation
and loss independently. Generations refuse wrap, and release purges the old
acquisition before reusing storage. IRQ code never resolves console units or
foreground pointers. Filtered cancellation has one durable mailbox delivery,
without a duplicate ordinary key; mailbox events do not invent timestamps.

Console policy still owns Caps, translation, typeahead and foreground scopes.
It maps retained generic tags to its own records, preserves cancellation through
CLEAR and drops retired scope delivery. Input remaining after a bounded pump
keeps the worker runnable even after its wake signal has been consumed. The
quota regression deliberately consumes that notification in worker context and
checks that the remaining queue drains without another key press.

Both compiler modes passed 217 standalone checks, including physical native
keys, modifiers, Escape/BREAK, copied leases, cross-Task permissions, route
capacity, acquisition/route exhaustion, raw counter wrap, cancellation/loss
priority, per-route discard and two acquisitions. The C bridge passed 71 checks
per mode, including successful admission, route operations and release, full
pointer/scalar marshalling, unchanged empty outputs, interrupted computation,
DP preservation and hardware restoration. Console controls cover focus,
foreground BREAK without Read, rollback/restart, both physical SIO acquisition
orders and emulation capture. Split-publication probes retain a real NMI between
route words while excluding IRQ observation. Full raw-ring and hardware-overrun
controls check explicit loss. All 284 host tests passed, with four historical
source audits skipped; these remain development checks, not qualification.

The migration also refreshed affected test assumptions: scope allocation follows
its current generated size; the publication probe selects an active rollover
route after admission's initial zero publication; ring fullness uses the modular
head/tail distance; synthetic focus timestamps avoid coinciding with later real
keys. Console teardown stops input before freeing its records and does not
republish a route through a released lease.

The existing 560-byte capture reservation is reused. Generic state consumes 128
bytes of previously unused upper Task-arena space at offset `$A60`, including
configuration, tags, mailbox reasons and lease identity. Console adds 78 bytes
of static upper-image lease/config/event scratch. There is no additional Task
or reserved upper arena. Fixed, every public Task and private-idle bank-zero
deltas remain zero, including guards, alignment and unused capacity. The optional
interactive application, cursor and responsiveness evidence remain I4–I6.

## I4 Interactive keyboard application

[I4 evidence](../development/gem-input-i4.json) records the new application in
large slot 6 and its renderer in large slot 7. Root remains the disk supervisor.
The application is the renderer's sole owner/client and holds input; the G5
computing-peer fixture remains a separate workload. Generated Action!/C probes
verify the 32-byte control message and 48-byte boot descriptor.

Four preallocated messages and four embedded ports provide startup, coalesced
progress, disk completion and exit. The ports share one allocated notification
bit per participant. A durable exit flag stops new reads after the current DOS
call settles. Root closes its file/context and collects its own replies before
releasing the application's creation lease and acknowledging EXIT. The
application settles input and rendering, collects that acknowledgment and uses
the retained release/notify/remove protocol. Root keeps storage until retirement.
STOP acknowledges admission and then follows this same handshake.

The scene has a 24-character field, a counter/color button, Exit and disk status.
Tab changes focus, printable keys and Backspace edit, Return activates, and
Escape/BREAK exits. A completed disk read leaves the scene interactive. Turns
bound input/control drains and collect one render completion. Four-command,
eight-glyph packets copy a tile into owned request storage; dirty UI state can
change while the submitted packet remains immutable. Empty nonblocking collection
preserves pending ownership and sequence state, and an unexpected reply remains
queued for diagnosis rather than authorizing disposal.

Each compiler mode passed fourteen GUI scenarios: keyboard state and exact pixels,
early/late Escape, BREAK, root stop, occupied input/display, real client/renderer
allocation exhaustion, third-large-Task refusal and four media errors. Both
keyboard runs consumed five input records while a render reply was outstanding,
then produced the same independently checked scanout. All accepted render packets
were collected. Ordinary exits restored OS/keyboard/display state, aperture RAM
and heap ownership; the missing-drive case retired the GUI but retained the
uncertain offline SIO bus at `$FF93`. The service protocol regression passed 353
checks per mode, including empty and unexpected nonblocking replies. The host
suite passed 284 tests, with four historical source audits skipped.

The C bridge now compares stored addresses through `ExecSameAddress`, also used
by `IsListEmpty`. Calypsi 5.18's implicit far24/static-symbol comparison emitted
an incorrect bank relocation; emitted probes now check matching addresses,
different banks and invalid fourth bytes at the shared boundary. Static control
messages explicitly request even alignment. The scene builder constructs fixed
commands and payload directly in final request storage; the initial temporary
array builder produced malformed coordinates under Calypsi. No Action! compiler
or kernel semantics were changed, and final checks use ordinary `-O0`/`-O2`
without a compiler override.

Both images reserve the existing two C banks and use 6,105 zero-filled C bytes,
as recorded in their maps. Embedded ports use 108 bytes and the four messages
128 bytes, with placement/alignment included within those existing banks.
Maximum observed root/application/renderer/kernel stack use was
408/228/472/280 bytes across the cases. Fixed, each public Task and private-idle
bank-zero reservation deltas remain zero, including guards and unused capacity.
These are focused development checks; cursor/pointer semantics, measured latency,
deeper failure closure and the optional packaged artifact remain I5–I7.
