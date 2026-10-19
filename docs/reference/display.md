# Display ownership

[Reference index](README.md) · [Platform](platform.md)

`DISPLAY` is an ordinary native library, shared by the console and the VBXE
adapter. It allocates no kernel selector. This follows Exec resource ownership:
one retained Task owns display lifetime until it has stopped hardware and restored
presentation. That owner can delegate serialized drawing units to other Tasks.
Physical display acquisition never waits for another lifetime owner.

The caller supplies a zeroed, address-stable 20-byte `DISPLAY.Lease` in writable
upper RAM. Keep it alive until release. Its address, generation and retained Task
identity are checked; copying a lease does not confer ownership. Fields are opaque
to callers. The layout and errors are generated from [display.json](../../abi/display.json).

`Acquire(lease,kind)` reserves TEXT or VBXE ownership in ACQUIRING state.
`Activate(lease)` publishes ACTIVE after initialization. `BeginRelease(lease)`
publishes RELEASING; `Release(lease)` is legal only after the adapter has restored
its state. `Check(lease)` checks the current owner. `State()` and `Kind()` are
observations, not permission to touch hardware. `Fault(lease)` permanently marks
FAULTED and retains the Task. Generations never wrap or repeat. Recursion returns
BUSY. Errors are OK, BUSY, UNSUPPORTED, NO_MEMORY, INVALID_OWNER, DEVICE_FAULT and
BAD_ARGUMENT. Caller memory validity is a shared-address-space obligation.

The text console holds a TEXT lease from before its first display mutation until
input production and presentation have stopped and its snapshot is restored.
The optional [bitmap console](console.md) instead holds a VBXE lease through
its shared drawing library; its existing worker owns lifetime and asynchronous
DMA retirement. These are mutually exclusive startup selections. The 80×30 bitmap preview
does not promise atomic scanout or the design's unachieved responsiveness targets.

Starting the text console while another Task owns graphics returns
`IOERR_UNITBUSY`, mapped by DOS to `ERROR_OBJECT_IN_USE` for an attempted open.
Close all console handles, call `DOS.ReleaseContext()`,
then wait for `CONSOLEDRIVER.Stop()` before acquiring graphics. Stop already
provides a signal-based retirement acknowledgment without polling Task records;
it refuses live endpoints. Reopen by calling `CONSOLEDRIVER.Start()` after graphics
release. A lease is never stolen from a live worker.

The C bridge exposes the same library through ordinary native calls.
The lease bridge validates huge pointers before narrowing and aligns the native call frame
without changing the caller's D. `VbxeOpen`, `VbxeFence`, VRAM transfer, blit and
presentation operations, and `VbxeClose` belong to the AltirraOS adapter. They
check the lease and fence before reading/reusing VRAM or releasing ownership.
The [C declarations](../../c/include/hardware/vbxe.h) include `VbxeBlit`: one
completed rectangular operation, 1–512 bytes wide, 1–256 rows, nonnegative
signed-13-bit row steps (0–4095), and modes 0–6. Complete VRAM extents are
validated before writes. `VbxePalette` installs 16 RGB entries in overlay palette
1; `VbxeShow` enables fixed 640×240 presentation without replacing that palette.
`VbxePresent` is the grayscale test-pattern convenience operation.

`VbxeSubmit(display,records,count)` synchronously submits 0–64 packed 21-byte
CPU records. The caller retains unchanged records until return. All records
are checked before mapping: dimensions, complete positive-step VRAM extents,
X steps of one, modes 0–6, zero pattern/zoom/collision and chain bits, and a
maximum estimated work of 8,192 bus accesses (two per copied byte, three for
other modes). The driver inserts chain bits while uploading into its own arena;
clients cannot provide a hardware list address. Invalid lists execute no prefix.
A zero count is a no-op after owner validation. CPU buffers may not overlap the
MEMAC aperture or exceed the CPU address space.

The command arena is the full 4 KiB at `$38000–$38FFF`; raster sources and
destinations cannot intersect it. Both list count and work limit apply, despite
physical space for 195 records. The hosted renderer reserves one 4 KiB upper-RAM
construction buffer, separate from its existing clipped-pixel staging page.
`VbxeBlit` and `VbxeFill` validate the whole operation, then split it into lists
of at most sixteen rows, reduced further by the work limit. An error after an
earlier chunk leaves that prefix drawn and follows normal device recovery.
These limits bound work; they are not a measured two-millisecond guarantee.

The adapter detects VBXE at `$D600` or `$D700` by reading CORE_VERSION (`$10`
for FX, `$11` for GTIA emulation). It reports the page, raw identity/revision
and decoded BCD revision, including the `a/r` flag. It requires the FX core
type for drawing, but does not require revision 1.26 or reject the `r` variant.
The driver and native IRQ/timer paths use the same detected page. Detection
does not write VBXE registers or change Antonia II configuration.

The cold-boot inactive full FX core, private 512 KiB VRAM and interrupts off
remain launch requirements. The launcher's private boot authorization
is required in addition to identity reads. Standard text launchers do not
authorize graphics. Unknown previous graphics state is UNSUPPORTED; identity
reads alone never authorize resetting hardware. The adapter tracks subsequent
write-only control values. The baseline is inactive, not a promise to preserve
unused VRAM contents or inactive overlay palette entries.

Hardware absence, wrong core type, baseline contradictions and console-start
failure are reported through the OS text screen, even with boot tracing off.
The pinned qualification evidence uses FX 1.26 at `$D600`; accepting a detected
revision is not a qualification claim for every FPGA core or physical board.

All hardware waits use unsigned 16-bit Exec tick subtraction, with deadlines
of sixteen ticks (strictly below half the range), while VBI remains enabled.
This permits two rotations of the eight-Task scheduler during a hardware wait. This
assumes normal interrupt delivery and ordinary Task context. Timeout stops the
engine and waits another bounded interval for idle. Once idle is established,
disable XDL and mappings, restore changed OS state, and release the lease with
DEVICE_FAULT. If idle cannot be established, keep FAULTED ownership and storage
and enter the platform's interrupt-disabled reset-required park (`$FF93`). This
does not acknowledge normal completion or return hardware/storage to the OS.

## Delegated renderer access

The lifetime owner installs its allocated wake mask with `OwnerWake(mask)`.
`Delegate(grant)` admits a zeroed, address-stable 32-byte upper-memory grant:
the borrower supplies its Task and an allocated nonzero signal mask. Admission
retains that Task and records the current display generation. At most eight
grants exist; exhaustion returns NO_MEMORY. This uses ordinary Exec signals and
Task leases, with no kernel selector or additional Task.

The admitted borrower calls `Enter(grant)` with its own live grant before using
the shared renderer and `Leave(grant)` after its final fence. Correct caller
identity is an API obligation: drawing entry does not repeat `FindTask(NULL)`.
Grant state, generation, revocation and device-fault checks remain in the
arbitration path. Enter waits in a bounded FIFO behind the
current unit; borrower access is not recursive. Ownership is published before signaling; the caller rechecks its
state around Wait. A signal is a hint, and a coalesced or early signal cannot
lose admission. IRQ/NMI code does not inspect the access queue. Short Forbid
sections protect Task-side state; drawing and synchronous fences retain normal
Task preemption and interrupt delivery.
When no grants exist, owner entry/exit need no queue guard: only the lifetime
owner can publish a new grant. Correct grant pointers are an admission/caller
obligation rather than a repeated bridge validation on each drawing unit.

Only the retained lifetime owner calls `OwnerEnter()`/`OwnerEnd()`/`OwnerDrop()`;
owner drawing entry likewise does not repeat a current-Task identity lookup.
The owner uses nonblocking `OwnerEnter()`, which returns BUSY and reserves one
queue position when a borrower owns access. Nested owner calls share the current
reservation. `OwnerEnd(dma)` retires one nesting level and records whether DMA
still pins access. The native `OwnerDrop()` retires a nesting level without changing that DMA
pin. Correct matching calls and live grant storage are caller obligations. Each
renderer unit reserves access through its callback, scratch use and final fence;
CPU-only presenter message/input work holds no reservation. BUSY preserves pending
paint for retry through the existing owner wake. Queued borrowers precede the
next native unit. Widget continuations fence and clear redirection before release;
their private VRAM strip survives between units. An asynchronous native operation keeps
physical access until the presenter polls and retires its hardware completion.

The lifetime owner's `Blocked()` readiness check also arms a release wake hint
before rechecking a busy borrower. This prevents the presenter from sleeping
indefinitely when it defers paint before calling `OwnerEnter()`. The hint does
not reserve access or join the FIFO. Borrower release signals the existing owner
mask only when a hint is pending; a queued owner handoff supplies that wake
itself. The owner must not clear this signal between the readiness check and
Wait. IRQ/NMI never inspect the hint, and uncontended checks make no kernel call.

Every shared GEM drawing entry, including pointer, caret, outline, staging and
snapshot work, uses this arbiter. The adapter's trusted `GemDrawingBorrow` helper
runs one synchronous callback over an admitted rectangle of at most 32 rows,
restores intersecting overlays, fences and releases. It is an internal renderer
callback, not an application callback API. A borrower must not issue AES RPC,
wait for an event or retain caller buffers within the unit. The [application VDI layer](gem-vdi.md#resident-application-workstations)
uses this helper with private workstation state and the published visible work
region. The helper grants no permission to draw arbitrary desktop pixels.
Physical ownership remains held if the drawing Task is preempted; other
renderers wait or return BUSY until it resumes and releases access. The helper
preserves the caller's Forbid nesting without adding scheduling exclusion around
drawing. IRQ/NMI delivery continues through its synchronous fences.
Caller-local AES objects whose complete extent, including outward borders, is
at most 32 rows use one callback per visible intersection. Larger objects retain
16-row strips, even for short exposed portions. Internal command lists retain
their 64-record/8,192-access limits and may drain within a callback. Native
presenter batches and the offscreen widget buffer remain limited to 16 rows.

The private `GemDrawingSolidBorrow` entry admits only a solid replacement fill,
using the same grant, overlay, fence and release lifecycle. Its VDI caller bounds
each rectangle by the 8,192-access fill budget before entry; unlike arbitrary
callbacks, it can cover more than 32 rows. The trusted `GemSolidFill` encoder
also appends uniform widget fills inside existing batches, preserving scratch
redirection and ordering. It reserves capacity for the entire fill fragment,
then writes one complete-byte record and up to two AND/OR edge pairs. It drains
only at the existing count/work limits or a caller's completion boundary.

`Revoke(grant)` belongs to the lifetime owner. It removes a queued grant and wakes
its Task, or revokes an idle grant; an active borrower returns BUSY unchanged.
The borrower acknowledges with `GrantClose`, which releases the retained Task.
Collection signals the owner's wake mask so a refused teardown can retry.
Voluntary close of an idle grant follows the same collection path. Owner release
and physical close refuse all live grants, including revoked ones not yet
collected. Storage and its signal remain live until collection succeeds.

A quiescent hardware timeout closes borrower admission, revokes idle/queued
grants and wakes their Tasks. An active borrower retains access until its final
return/release. The owner remains eligible for admission to finish cleanup after
all grants are collected; hardware restoration never runs as the borrowing Task.
With no grants the original immediate owner recovery applies. An unquiesced
timeout retains ownership and grants and enters reset-required park. No normal
completion, collection or restoration is claimed in that state.

## Software pointer

The shared GEM/desktop software pointer uses the existing synchronous list
submission path. A warmed visible move has four ordered records: restore the
old saved background, save the new one, AND the mask and OR the image. Show
needs three records, hide one, and an unchanged valid pointer needs none.
The maximum list is 84 bytes and 1,440 work units, using the existing command
arena, saved background and parity masks. The complete list is validated before
launch; new save geometry is adopted after completion. Faults use the same
quiescent/reset-required policy as other drawing. This does not add a hardware
queue or asynchronous cursor lifetime; pending scroll work retains the arena.

## Bitmap rectangle copies

`VbxeCopyRect(display, copy)` is an ordinary synchronous C driver operation.
The generated [descriptor](../../abi/bitmap.json) contains two 10-byte surfaces
and six 16-bit coordinates/dimensions (32 bytes total). Surface offsets and row
pitches are VRAM bytes; coordinates, widths and heights are pixels. Rows contain
packed 4-bit pixels. Pitches are 1–4095 bytes, widths at most twice the pitch,
and the complete surface must fit VRAM without touching the command arena.

Copy X coordinates and width must be even, with width at most 1024 pixels.
All bounds are half-open; a valid empty rectangle succeeds without mutation.
The complete descriptor and both extents are checked before copying. Distinct
nonoverlapping surfaces may have different pitches. Overlapping address extents
require equal pitches; descending row and byte order preserves the source when
the destination is higher in memory. Ambiguous overlapping views with different
pitches are rejected. Unsupported geometry can be redrawn by the console.
The caller retains the immutable descriptor until return. The checked operation
constructs private stack records for each chunk and uses the same internal
launch/fence routine as public list submission; it does not repeat validation
of caller geometry for every chunk. This is driver implementation, with no
additional kernel entry or weaker public-list checks.

Public `Vbxe*` drawing operations validate lease and Task identity once at entry.
Nested transfer, drawing and fence work uses private driver helpers within that
synchronous invocation. Public list records still receive complete validation
before any of that list executes. A later public call validates again; lifecycle
and fault transitions retain their own checks.

Copies use opaque mode zero, including zero-valued source pixels. Each chunk
is at most sixteen rows and 8,192 estimated bus accesses; errors may leave a
completed prefix of chunks, so callers must invalidate presentation after a
fault. There is no new kernel selector or advertised VDI opcode. Signed list
steps support X ±1 and Y −4096…4095; validation checks both address extremes
and rejects VRAM wrap and command-arena overlap before submission.

## Asynchronous rectangle copies

`VbxeCopyStart(display,copy,idOut)` accepts an even-X/even-width typed copy of
at most 640×240 pixels (76,800 copied bytes). It uses the same complete surface
and extent checks as CopyRect. Equal-pitch overlapping views copy in the safe
direction; different pitches require disjoint extents. Zero pixel bytes are
copied normally. Empty or identical geometry returns OK with `*idOut=0`, without
consuming an identity or submitting hardware. Invalid arguments leave the output
unchanged. Accepted descriptors are copied before returning.

A nonzero ID means one list was launched, not that DMA finished. Copies and
scrolls share **one** active operation, ID sequence, command arena, completion
signal, deadline and recovery path. Use `VbxePoll`, `VbxeCompletionMask` and Fence
as described below. Either start returns BUSY without changing its output or the
pending operation. There is no second queue or per-copy allocation. Retain both
surfaces until completion or proven quiescence. Drawing into arbitrary offscreen
surfaces remains outside the desktop contract; this is a typed transfer API.

## Asynchronous screen scrolling

`VbxeScrollStart(display, copy, value, id)` submits an upward screen copy
and exposed-strip fill in one hardware launch. Both surfaces must describe the
640×240 screen at offset zero and pitch 320; X and width are even, source and
destination X agree, and source Y minus destination Y is a positive multiple
of eight pixels. This delta is the exposed fill height; the fill begins after
the copied destination rows. The copy and fill must both fit the screen.
A zero copy height submits only the exposed-strip fill.
`value` is the packed hardware byte, including both pixel nibbles.

OK means accepted, with an operation ID written to `id`; the call may return
while hardware is busy. Descriptor fields and records are copied before return.
Only one list can be pending. Another start returns BUSY without replacing the
operation, changing the output ID or touching its command storage.
`VbxePoll(display, id)` checks once and returns BUSY, completed OK or a
terminal error. A stale/zero ID returns BAD_ARGUMENT. IDs are not reused across
close/reopen, and exhaustion rejects new starts. Both entries validate the owner
on every invocation; an ID never grants access to another Task.

The display record, command arena and raster storage must remain live until
completion or confirmed quiescence. MEMAC is closed when start returns. Existing
synchronous drawing/transfer operations and Fence finish pending work before
dependent access. Close likewise drains before release. Poll uses the original
launch deadline, with wrap-safe subtraction and the existing STOP/reset-required
recovery. It never restarts the deadline on a later poll. After recovery releases
the lease, further calls must reacquire ownership; an unquiesced fault retains
ownership and storage. Completion is not an atomic or tear-free screen update.

`VbxeCompletionMask(display)` returns the owning Task's nonzero completion mask
while the display is open, or zero for an invalid/foreign owner. The driver
allocates, binds and frees this signal; callers may Wait on it but must not free
it. Signals can coalesce: the matching operation ID and durable driver result
are authoritative. A stale wake after a Fence or earlier operation is harmless.

The native backend owns IRQ_CONTROL and arms the retained `VBXE_BLITTER`
producer before starting the list. Native and emulation IRQ routes acknowledge
completion, record DONE and signal the owner without executing C or switching
a live OS activation. The shared timer independently records EXPIRED and posts
the same signal after sixteen VBI ticks. It compares the wrapping tick counter,
without polling BUSY at every timer edge. The owner checks final idle state and
performs any STOP/recovery in Task context. This permits Wait even without disk,
pointer or keyboard activity. Notification does not free the command arena or
authorize another drawing operation until completion is consumed.

Close first proves DMA quiescent, then disables/acknowledges the source, cancels
its timer demand, releases and drains the binding, frees the signal and restores
owned vectors/resources. Generic producer Release alone does not quiesce DMA.
Failure to stop hardware retains ownership/storage in reset-required park.

This combined operation permits the complete rectangle's hardware work. Public
arbitrary-list and synchronous chunk limits remain unchanged. Synchronous
launches keep VBXE IRQs disabled. No additional renderer Task is created.

## Mapping transition protocol

The owner publishes pending BANK_SEL and CONTROL in its upper-RAM state. The
assembly leaf disables MEMAC A, writes BANK_SEL, writes CONTROL, then copies the
pending pair to the committed shadow. It stays on the caller's stack and DP, restores S and flags on return, and
touches only caller-clobbered registers and the caller's upper DP scratch. NMI/IRQ may
occur between every store. No interrupt handler, SIO worker, ROM call or other
Task accesses MEMAC, VRAM or either shadow. The reserved CPU aperture contains
no stacks, vectors, kernel state or program bytes. Only the owning Task resumes
the transition, so preemption needs no new kernel critical section or SEI.

`$8000–$8FFF` is a CPU window onto a selected 4 KiB VRAM page. When disabled it
shows underlying CPU RAM. Mapping neither allocates CPU RAM nor makes VRAM part
of the Exec heap. Driver and lease state stay in upper CPU RAM. The slice adds
zero reserved bank-zero bytes, fixed or per Task; the full existing 4 KiB window,
stack guards, alignment and unused stack capacity remain reserved.

### Shell backing destination

The private console renderer reserves `$41000–$4AFFF` for one 512×160 packed
Shell bitmap (pitch 256, 40,960 bytes). Both shared AES snapshots remain intact.
Production VRAM reservations total 416,256 bytes; 108,032 remain unassigned
(108,000 after the existing diagnostic exclusion). No CPU aperture, bank-zero
or per-Task reservation grows.

Private console protocol version 13 adds backing text/fill operations without
changing its 78-byte packet. The native text uploader's private record is 28
bytes, with destination pitch at offset 26; screen text continues to use pitch
320. Every emitted destination record uses that pitch, including background
and trailing fills. The uploader uses call-clobbered DP bytes through `$A9`
within the existing reservation. Targets are explicit on each call.

Desktop Shell dirty spans describe pending model-to-backing work. Layers damage
separately describes screen repair. Completed backing scrolls use the ordinary
asynchronous copy engine, clear the newly exposed rows, then render final dirty
spans before publishing the new generation. This works while partly or fully
covered. Batch cancellation and view retirement retain the existing DMA lifetime
rules. Caret and pointer pixels are screen overlays, never backing contents.

The desktop binding names the sole Shell backing owner. Binding another console
invalidates that ownership and rebuilds all 64×20 cells before copying the new
image. Ownership, fixed geometry and the view’s presented model generation must
all match before reuse. Hidden consoles retain their own dirty cells and never
paint into the selected console’s bitmap. Session switching adds no backing
VRAM; it uses the same 40,960-byte reservation.
