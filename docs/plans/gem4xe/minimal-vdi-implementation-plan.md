# Implementation plan for a minimal hosted GEM VDI subset

[Implementation plans](../README.md) · [GEM assessment](exec816-integration-assessment.md) · [Larger Task stacks](../larger-task-stacks-implementation-plan.md)

Status: proposed on 2026-10-01. This plan turns the assessment's first memory,
C and display milestones into a bounded executable: one GEM rendering service,
one client drawing a test scene, and a computing peer under Exec preemption.
The display backend is VBXE only. Success means correct drawing, measured memory
and stack use, concurrent disk I/O, and a clean return to text presentation.
It does not require AES, a desktop or a GEM application loader.

The prerequisite is the implemented mixed eight-Task layout, currently in the
working tree above Exec816 `d8dbea4`. Its
[development record](../../development/larger-task-stacks.json) proves the
larger pools with bounded Action! and C fixtures, not with GEM. Freeze the actual
implementation revision and source hashes at the start of this work. Upstream
source analysis here uses GEM4XE 0.9.4 at
`e413c39d2f8e1bec8fe16596f610b923de4a0ae9`; do not silently replace it with HEAD.

## Deliverable and supported calls

Build a separately selected hosted XEX containing the Exec kernel, adapted GEM
VDI code, VBXE adapter and rebuilt client. The scene clears the screen, draws
clipped lines and solid rectangles, and prints fixed-font text. It repeats with
different attributes while another Task computes and the supervisor reads a
known disk file. It then closes the graphics session, restores text output and
exits through Exec's existing OS restoration path.

Use a fixed 640 by 240, 16-colour mode and the linked 8 by 8 system font for this
milestone. These are deliberate limits, not runtime mode negotiation. The
upstream [device interface][vdidev] and [VBXE implementation][dev-vbxe] provide
the starting rendering boundary. Expose the following subset through rebuilt
client helpers; publish the exact supported counts and values in a generated
operation manifest before coding the dispatcher.

| Area | Initial support |
| --- | --- |
| Session | `v_opnwk`, `v_clswk`; one client and one physical workstation at a time. |
| Completion | `v_clrwk`, `v_updwk`; successful replies mean drawing has finished. |
| Geometry | `v_pline` with 2–16 points and solid one-pixel lines; `v_bar` with two corners; `vs_clip` on/off with inclusive pixel bounds. |
| Text | `v_gtext`, at most 64 glyphs per operation, linked system face, default orientation and metrics. |
| Attributes | `vsl_color`, `vst_color`, `vsf_color`, solid `vsf_interior`, and `vswr_mode` restricted initially to replace mode. |
| Inquiry | The supported workstation output fields from open; report actual geometry and available features. |

Reject unsupported opcodes, GDP subfunctions, handles, counts and attribute
values before changing renderer state. Do not silently route them to a no-op.
Classic void-return helpers must expose transport/validation failure through a
documented client status accessor; do not invent successful VDI output fields.
The [upstream dispatcher][vdi] is the reference for operation numbers and
parameter conventions, but its complete opcode table is outside this subset.
Upstream treats physical `v_clswk` as a no-op; the hosted binding deliberately
uses it to close the session and release display ownership.

Defer virtual workstations, raster copies, polygon/contour fill, external fonts,
cursor and physical input, AES objects/windows/events, resources, GEMDOS, G4A,
o65 C commands, callbacks and dynamic loading. The drawing client has a scripted
end; it needs no mouse or keyboard while graphics owns presentation. A later
input milestone should start with injected events before sharing POKEY hardware.

## Ownership and execution choices

One ordinary Exec Task owns renderer globals, workstation state, VBXE command
lists and the mapped aperture. Clients send bounded requests through public
Exec message ports. This follows classic Exec message lifetime; serializing the
non-reentrant GEM renderer in a service is the documented adaptation from a
library executing on every caller's stack. There is no GEM-specific kernel gate.

Keep Exec's Task S and D throughout every call. Exclude upstream machine startup,
COP dispatch, cooperative stack parking, destructive RAM probing, OS shadowing,
Rapidus initialization and exit code. Rendering runs with normal preemption;
neither Forbid nor IRQ masking is held across drawing, memory copies, blitter
waits or replies. Exec retains its COP `$50`, OS COP `$00`, IRQ/NMI vectors and
ANTIC VBI scheduling. The first display adapter enables no VBXE interrupt source.

The supervisor runs on root and hosts the scripted C client through the existing
foreign-call boundary. The renderer requests 2,560 bytes. A second worker
requests 2,560 bytes and computes without cooperative yields, exercising both
large pools. Admit both before smaller service workers can consume those pools;
use Forbid only around creation and pointer-dependent setup. Handle partial
admission failure and publish readiness only after initialization succeeds.

| Participant | Public Tasks at peak |
| --- | ---: |
| Root supervisor and client | 1 |
| GEM renderer | 1 |
| Computing peer | 1 |
| Existing filesystem and SIO workers during disk checks | 2 |
| Console during text phases | At most 1; quiesced before graphics claim |
| Budget | At most 6 of 8; private idle and kernel context are additional |

The display lease itself adds no worker. Do not compose this harness with the
standard demo's five Tasks and a pipeline. Keep one current Task API and shared
admission rules; neither stack is permanently reserved for GEM.

## Memory and compiler gate

Target **zero additional fixed bank-zero bytes and zero additional bytes per
Task** beyond the larger-stack baseline. Reuse the two existing guarded pools
and the reserved `$8000–$8FFF` aperture. The baseline runtime reservation is
56,128 bytes including OS ranges, leaving 9,408 bytes at `$5B40–$7FFF`. That
free range is not a heap. Do not reclaim it implicitly for GEM near data.

Each large stack has 2,304 bytes above its 256-byte interrupt reserve, before
native frames and bridge nesting. Report observed peak and remaining headroom
for renderer, peer, root, idle and kernel. Calypsi still lacks automatic function
entry checks; tests record observed use for the exercised calls, not a general
worst-case bound. If the adapted call chain does not fit, reduce retained stack
objects or explicitly revisit the design; do not quietly enlarge a pool or the
kernel stack.

Use Calypsi 5.18 large-code/huge-data as the first hosted target, with the pinned
[actionc inputs](../../../toolchain/actionc.json) for native bridges. Audit the
[upstream dialect][portab], ordinary pointer arithmetic, object addresses,
`NEAR`, `TINY`, `ZWIN`, and memory-copy helpers. Put renderer globals, request
storage, fonts, tables and driver state in validated upper RAM. Initially map
upstream tiny scratch to ordinary upper data; preserve Calypsi's existing
20-byte runtime workspace inside the caller's lower 128 DP bytes. Reject stray
bank-zero sections and reserved-DP use at link/package time. Changing compiler
flags alone is not the port.

The current [C linker layout](../../../c/calypsi/layout.scm) and
[ELF reader](../../../tools/calypsi_image.py) accept code in bank `$0C`, data in
`$0D`, and fixed virtual metadata. First measure whether the selected subset
fits. If it needs more banks, implement checked multi-bank placement using an
explicit image layout: validate every code/data/BSS extent, entry, overlap and
bank ownership before loading. Update emulator RAM, usable-bank map and heap
availability together. Do not relax the reader to accept arbitrary ELF segments.
Upper RAM expansion is allowed; its actual requirement is unresolved until link.

VBXE VRAM is separate from CPU RAM. Retain and validate the selected upstream
VRAM regions for screen, XDL, blit lists, font expansion and scratch, including
unused reserved capacity. A 640 by 240 4bpp screen uses 76,800 bytes; that is not
the total VRAM reservation. Do not turn optional VRAM regions into new bank-zero
buffers. Report all three memory classes separately.

## Request and display contracts

### Messages and lifetime

Define a versioned service protocol with open, submit, close and supervisor stop.
Use an aligned Exec Message followed by explicit-width header fields: version,
total bytes, operation, session generation, sequence, command count, result and
completed-command count. Generate layouts from a machine-readable service ABI;
verify target-emitted sizes and offsets. This is a message ABI, not a COP selector.
Keep GEM headers and Exec record definitions in separate translation units where
their types or pointer representations differ.

Start with one outstanding request per client, at most 16 commands and 2,048
payload bytes per submission. Allocate messages and payload in upper RAM;
encode offsets within that allocation rather than passing arbitrary nested
pointers. Check every count, multiplication, offset and full extent before
calling GEM, including 24-bit representability and bank boundaries. Keep VDI
parameter arrays service-owned; clients never write renderer globals.

Validate the entire batch first. Invalid input makes no drawing/state change.
An execution or hardware failure may leave a completed prefix and partial pixels
from the failing command; report the completed count and retire the session
after a device fault. Successful completion includes a hardware fence. A close
drains accepted work and invalidates the session before
acknowledgement; stale session generations never address a newly opened one.

Provide submit/collect steps below the synchronous VDI helpers. The integration
supervisor submits a batch, starts a real Exec DOS read while that request is
still outstanding, then collects its reply. This proves overlap without adding
C file bindings or another client Task. Request storage survives the return from
the C submit call; no borrowed stack activation may end while its request is live.
The test must observe renderer progress during an active physical SIO interval;
an uncollected reply alone does not prove overlap. Use a fixture-only start
rendezvous if needed, and force a cache miss for the measured read.

The sender keeps the request, payload and reply port alive until the exact reply
is removed with GetMsg. While the request is in flight, the sender must not
change its header or payload; the service writes only the defined reply fields
and Exec manages the message linkage. The service stops touching a record as
ReplyMsg publishes it. RemPort only withdraws discovery; it does not revoke
borrowed pointers. Use
the existing [Task leases](../../reference/resident-drivers.md#task-admission-and-lifetime)
to prevent removal of participants with live work, and explicit close/stop
rendezvous to release them. No unilateral client removal or timeout-based freeing
is supported. Cancellation is initially orderly stop at a bounded operation
boundary; it does not roll back pixels or detach live requests.

Add the missing generated C bindings for the public lifetime operations actually
used. Keep the renderer ordinary for this supervised first milestone; root
explicitly stops it before returning. Resident registration and last-application
shutdown integration are later work unless this lifecycle needs them.

### Display acquisition and release

Introduce a reusable platform display lease shared by native console and VBXE
presentation. Implement policy in a display/driver module using public Task
retention and synchronization. Expose ordinary checked calls through the hosted
C/Action! boundary; do not add private GEM kernel operations. Before coding,
write the lease's public ownership/error contract and the assembly transition
protocol. If a kernel operation proves necessary, it must be reusable by other
Tasks and drivers, with a generated public ABI and focused tests.

The initial policy is exclusive acquisition only when the prior owner has fully
released presentation. A live console causes a busy result. The supervisor
closes its text handles, releases its DOS context and waits for console shutdown
acknowledgement before requesting graphics; merely hiding a window is insufficient.
Console startup must participate in the same ownership rule and fail cleanly
during a graphics lease. Add the bounded shutdown acknowledgement if the current
console API cannot express it; do not poll private Task records.

The adapter owns the snapshot and restore of the display state it changes,
including OS video shadows and write-only VBXE register shadows. Support a known
inactive VBXE state at boot first; an unknown pre-existing graphics owner is an
explicit acquisition failure. Do not claim arbitrary register readback restores
write-only state. After release, reopening CON: must work; preserving a live
terminal session while it is suspended is a later capability.

Only the lease owner maps VRAM or submits blits. IRQ/NMI, SIO, ROM entry and all
other Tasks must leave MEMAC and renderer state alone; audit that invariant.
Preemption of the owner is allowed because nobody else accesses the aperture.
Keep software mapping shadows coherent through entry, failure and release;
inject NMI between mapping-register writes to test the chosen protocol.

Upstream [VBXE flush][dev-vbxe] starts a blit asynchronously, and its
[low-level waits and shutdown][vbxe] are not the completion contract above.
Add a bounded, preemptible fence before reply, scratch reuse, readback and release.
Apply the deadline to internal busy/VCOUNT waits too; a final fence cannot bound
an earlier infinite wait. Use wrap-safe Exec ticks while VBI remains enabled.
Keep ordinary IRQ/NMI service active. On timeout, stop/reset and verify the
engine is quiescent before releasing hardware/storage. If that cannot be proven,
retain ownership and enter the controlled platform fault path; never report a
clean OS return while DMA may still be active. A CPU watchdog in the host test
does not replace a bounded target-side wait.

## Executable slices

All slices below are pending. Complete their development gates in order. Keep
builds, source downloads, maps and logs under `build/gem-vdi/`. Paths named as
new tools or modules below are proposed deliverables, not commands that exist.

| Slice | Deliverable and acceptance gate |
| --- | --- |
| G0 Freeze inputs and interfaces | Pin upstream source, compiler/runtime, Exec baseline, ROM and actual VBXE emulator configuration. Record the operation/lease contracts and selected source closure. Exit with reproducible inputs and an explicit unsupported list. |
| G1 Extract and link the hosted subset | Rebuild selected VDI routines and dependencies with hosted pointer/storage rules. Run C entry/layout probes on an ordinary large Task with a computing peer. Exit with a checked combined map and no legacy startup or hidden hardware side effects. |
| G2 Run the message service | Exercise open/submit/close/stop, bounded inline payloads, retention and failure rollback using a fixture-only dispatcher. Exit with raw/optimized IPC and lifetime cases, without claiming graphics execution. |
| G3 Acquire and release VBXE safely | Implement shared display ownership, a pinned VBXE backend, bounded blit completion and recovery. Draw an adapter test pattern. Exit with readback, NMI/IRQ coexistence and repeatable text restoration. |
| G4 Execute real GEM drawing | Connect accepted requests to the selected VDI routines. Render the fixed scene and operation corpus. Exit with exact pixel/attribute results and measured GEM call-chain headroom in both compiler modes. |
| G5 Prove concurrent operation and failure cleanup | Combine drawing, the computing peer and one physical SDFS read workload. Exercise orderly stop and injected admission/allocation/device failures. Exit with bounded completion, retained ownership and clean recovery where supported. |
| G6 Integrate documentation and artifacts | Publish exact scope, measured inputs/costs and a reproducible optional graphics artifact. Run affected standard OF816 demo checks. Mark complete only when G0–G5 evidence and documentation agree. |

G0 must inspect the actual VBXE device/core and register base exposed by the
chosen emulator, not assume that the existing shell pin enables it. Add a
separate platform pin and explicit configuration-aware checks in
[os_boundary.py](../../../tools/os_boundary.py) and
[native_program.py](../../../tools/native_program.py); current verification
expects add-ons off. Preserve that default for existing tests. Record emulator
binary/source hashes, FX core version, register base, VRAM, CPU speed, PAL mode,
upper banks, ROM and physical disk profile. Require a negative no-VBXE case that
returns unsupported without switching hardware or choosing another renderer.

G1 starts from [vdi.c][vdi], [vdidev.h][vdidev], [dev_vbxe.c][dev-vbxe],
[vbxe.c][vbxe], the linked font and the exact tables needed by the allowlist.
Split selected dispatch and initialization from unrelated dependencies; a full
function-pointer table can keep unwanted code linked even when clients cannot
call it. In particular, remove hosted keyboard initialization, legacy context
ownership, printer references and CIO font loading from the selected closure.
The current [font module][font] includes disk-loading paths and the
[pointer module][pointer] accesses platform input hardware; neither should be
imported wholesale as a way to satisfy symbols. Keep algorithm changes separate
from platform adaptations and maintain a reproducible patch series against the
pinned source. Do not satisfy omitted services with success-returning stubs.

Proposed implementation locations are `ports/gem4xe/` for the selected source
manifest, patches and hosted adapters, `lib/display/` plus
`platform/altirraos/` for generic display integration, and `abi/gem-vdi.json`
for the service protocol. Extend shared C emission/packaging helpers used by
[build_calypsi.py](../../../tools/build_calypsi.py); add a dedicated
`tools/build_gem_vdi.py` entry point and `tools/test_gem_vdi.py` runner. Keep
existing C examples as controls rather than turning their builder into a second
kernel implementation. Preserve upstream source/font notices and COPYING files;
imported code does not inherit the MIT declaration for Exec-authored C bindings.

G3 tests the CPU/VRAM distinction explicitly: seed the underlying reserved RAM
before mapping, compare VRAM while mapped, then unmap and verify the original
RAM sentinel and adjacent reservations. Use driver readback or an independently
validated emulator VRAM observer, and flush before reading. Screenshots supplement
pixel checks. Never test mapped VRAM against an unmapped-RAM sentinel.

G4 reuses selected upstream primitive expectations and adds small independently
computed pixel cases: clipping on every edge, reversed rectangle corners,
off-screen and extreme signed coordinates, horizontal/vertical/diagonal lines,
empty and maximal text, glyphs at odd/even x, and drawing across 4 KiB VRAM
windows. Check CPU payload extents near 64 KiB boundaries, including explicit
rejection of crossings the selected transport does not support. Keep scene hashes,
changed-pixel bounds, palette and source font hash together. Include a visible
screenshot, but do not accept a screenshot alone as the rendering oracle.

## Validation and completion evidence

Use the [development tier](../../contributing/testing.md). Run host packaging,
ABI generation and affected emitted-code checks after each coherent slice.
Run raw Action! NIR with Calypsi `-O0`, and optimized NIR with Calypsi `-O2`;
record the full flags and runtime hashes. A cross-mode matrix is only needed
to investigate a failure. Retain the existing four-Task C context probe as a
control after shared bridge/ELF-reader changes.

| Case group | Required observations |
| --- | --- |
| Memory and ABI | Complete code/data/BSS/DP/stack/VRAM maps; no overlaps or unexpected near storage; full-width pointer rejection; emitted record layouts; registered C Task entries; clean allocation failure. |
| Protocol | Malformed length/offset/count, unsupported opcode/value, bad handle, stale generation, busy second client, ordered batches, exact reply identity and no partial mutation on validation failure. |
| Lifecycle | Failure after each acquired resource; repeated open/close; stop with queued/active work; no early request free, duplicate reply, dangling public port or retained Task lease. |
| Context and stack | Actual VBI interruption in GEM C code, peer progress, full S/D and register restoration, lower DP preservation, all guards, and peaks/headroom without refilling live stacks. |
| Display | Busy console/graphics conflict, missing/unsupported VBXE, mapping transitions, pixel/VRAM checks, blitter timeout recovery, text reopen, final OS state restoration. |
| Device coexistence | Nonzero physical SIO IRQs with the pinned profile, exact file bytes, continuous renderer/peer progress and bounded shutdown while display is owned. |

Check service progress between bounded commands; batch completion need not meet
a guessed frame rate. Measure elapsed cycles/frames, message crossings, stack
peaks and artifact size for a fixed corpus before deciding whether batching or
further device optimization is needed. Keep device queue and cancellation policy
out of the kernel. Compiler defects belong in actionc or a focused Calypsi
regression, not GEM-specific exceptions to Exec's context validator.

Every slice reports actual reservation changes, including guards, padding and
unused capacity. The planned bank-zero increment is **fixed 0; per Task 0** for
G0–G6. Display state, protocol buffers and renderer objects must be accounted
for in upper RAM even when the bank-zero delta is zero. If this target is missed,
revise the recorded placement and budget before claiming the slice complete.
Do not reuse the earlier generic C peak as a GEM measurement.

Record completed cases in a new `docs/development/gem-vdi.json`, including
baseline/final revisions and patches, input hashes, chosen machine configuration,
compiler modes, maps, per-pool/fixed costs, pixel expectations, actual interrupt
observations, lifetime outcomes, stack peaks, timing and artifact hashes. Do not
create a passing record before execution or rewrite older qualification files.
Current supported calls and ownership contracts then belong in reference/guides;
completed design discussion belongs in history, with indexes updated.

The normal distribution remains the OF816 shell/prime demo with five-second
autoboot. When shared platform/build code changes, refresh it through
[build_demo.py](../../../tools/build_demo.py) and run the affected
[OF816 checks](../../../tools/test_of816.py). Keep the optional graphics XEX and
its configuration/guide separate. If packaged as a demo, include OF816, the
matching system disk, pinned ROM and upstream notices through that same packaging
path; do not replace standard autoboot with GEM. Distribution archives contain
only boot files, guide, licences and checksums; build maps and evidence stay out.

Completion establishes a hosted drawing subset on the measured platform. AES
event waits, multiple independent GUI clients, live console suspension, native
pointer/keyboard ownership, GEMDOS and a desktop remain subsequent plans.

## Plan preparation checks

This document was prepared by inspecting the current Exec contracts and tools,
the completed larger-stack record, and the pinned upstream source files linked
above. Preparation checks local links, anchors, source identities and budget
arithmetic. It runs no new GEM executable or platform qualification. This
documentation change reserves **0 fixed bank-zero bytes and 0 bytes per Task**.

[vdidev]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/vdidev.h
[vdi]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/vdi.c
[dev-vbxe]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/dev_vbxe.c
[vbxe]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vbxe/vbxe.c
[portab]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/portab.h
[font]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/font.c
[pointer]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/pointer.c
