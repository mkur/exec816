# Display ownership

[Reference index](README.md) · [Platform](platform.md)

`DISPLAY` is an ordinary native library, shared by the console and the VBXE
adapter. It allocates no kernel selector. This follows Exec resource ownership:
one retained Task has exclusive access until it has stopped hardware and restored
presentation. Display acquisition never waits for another owner.

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

The console holds a TEXT lease from before its first display mutation until
input production and presentation have stopped and its snapshot is restored.
An open while graphics owns the display returns `IOERR_UNITBUSY`, mapped by DOS
to `ERROR_OBJECT_IN_USE`. Close all text handles, call `DOS.ReleaseContext()`,
then wait for `CONSOLEDRIVER.Stop()` before acquiring graphics. Stop already
provides a signal-based retirement acknowledgment without polling Task records;
it refuses live endpoints. Reopen by calling `CONSOLEDRIVER.Start()` after graphics
release. A lease is never stolen from a live worker.

The checked C bridge exposes the same library through ordinary native calls.
It validates huge pointers before narrowing and aligns the native call frame
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

Only the cold-boot inactive full FX 1.26 core at `$D600`, private 512 KiB VRAM,
with VBXE interrupts off is supported. The launcher's private boot authorization
is required in addition to exact identity reads. Standard text launchers do not
authorize graphics. Unknown previous graphics state is UNSUPPORTED; identity
reads alone never authorize resetting hardware. The adapter tracks subsequent
write-only control values. The baseline is inactive, not a promise to preserve
unused VRAM contents or inactive overlay palette entries.

All hardware waits use unsigned 16-bit Exec tick subtraction, with deadlines
of sixteen ticks (strictly below half the range), while VBI remains enabled.
This permits two rotations of the eight-Task scheduler during a hardware wait. This
assumes normal interrupt delivery and ordinary Task context. Timeout stops the
engine and waits another bounded interval for idle. Once idle is established,
disable XDL and mappings, restore changed OS state, and release the lease with
DEVICE_FAULT. If idle cannot be established, keep FAULTED ownership and storage
and enter the platform's interrupt-disabled reset-required park (`$FF93`). This
does not acknowledge normal completion or return hardware/storage to the OS.

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
