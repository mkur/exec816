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
