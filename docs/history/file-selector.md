# Standard GEM file selector development record

[Design](../plans/gem4xe/file-selector-design.md) ·
[Plan](../plans/gem4xe/file-selector-implementation-plan.md) ·
[Evidence](../development/file-selector.json)

## FSEL1 Directory and viewport helpers

Files now uses the private `file-list` helpers for bounded enumeration, path
joining/parent navigation and viewport/selection clamping. Enumeration exposes
one entry per step so the upcoming selector can service input between DOS calls.
Open/examine failure preserves the previous view; a later read error clears the
overwritten snapshot. No directory lock survives a completed or abandoned scan.

The same source provides a 256-WORD filtered index, ASCII-insensitive GEM 8.3
wildcards and selector path/leaf handling. Directories pass every filter and
`*.*` includes extensionless files. The matcher follows the hash-pinned GEM4XE
routine; Files retains its unfiltered list and existing event loop.

The focused emitted helper fixture passes 53 checks in raw and optimized C,
covering the 0/1/256/257-entry boundaries, DOS failures, lock return, filtering,
viewport and path bounds. Both modes check a digit-first leaf separately from an overlong stem. The host suite passes 423 tests with
four historical skips. An initial fixture combined two compile-time size
assertions into an expression that the C compiler folded to failure; separate
size assertions pass in both modes. That failed trial is not acceptance evidence.

The exact OF816 ZIP passes the Files-only desktop walkthrough: Path/New
Folder/Rename, scrolling/resizing and pixel repair, native/GEM child launching,
Stop/collection, relaunch, heap return and final EXIT. The minimum ordinary-pool
margin is 277 bytes, above the 128-byte target. Idle retains 121 bytes and is
reported separately from that ordinary-pool gate.

Reserved bank-zero delta is **0 fixed, 0 per public Task and 0 private idle**,
including guards, alignment and spare capacity. Files' live upper state grows
from 3,054 to 3,074 bytes; its existing 28,672-byte entry allocation is unchanged.
The loadable Files artifact grows from 19,565 to 21,089 bytes; its image span
grows from 69,497 to 69,527 bytes. The filtered index is not allocated by Files.
Stack/DP pools and VRAM reservations are unchanged. These are development checks,
not real-hardware qualification or closure of HY4/PI4.

## FSEL2 Private hosted selector

The private selector uses a compiled 31-object tree, caller-owned form lifetime,
editable path/filename fields, a filtered viewport and DOS scans stepped between
ready-event passes. Loading leaves Cancel active. Scanning retains input interest
without creating a timer, clearing signals or waiting for fresh input with a
live directory lock. Existing blocking AES event behavior is preserved.

The optimized fixture passes **195 target checks**, plus physical keyboard/mouse
interaction and four independent pixel comparisons (220,928 compared pixels).
Cases include two callers, compact 208×128 work space, scrolling/truncation,
filter changes without directory reads, navigation, edited Cancel, temporary
move/close, cancellation while loading, held-entry/outside-release/input-loss
handling, and borrowed move/close interruption with exact message/repair order.
Allocation/retirement faults, retry, full window capacity and a full receive
queue return their resources. Caller-owned DOS handles and locks survive.
An injected late read failure clears the partial snapshot. The separate blocking
event regression passes 371 checks while its CPU peer continues progressing.
Raw/optimized emitted layout probes agree; the host suite passes 423 tests with
four existing skips.

The final warmed heap baseline is **2,661,056 bytes before and after** the
exercise. The first real access allocates 73,624 bytes of persistent filesystem
mount/cache storage; it is measured separately from selector/context ownership.
Minimum ordinary stack margin is **302 bytes**; idle is 192 bytes, reported
separately. No stack increase is required.

Initial pixel trials exposed a status field that overlapped Cancel's border.
It now leaves space above the buttons. Row updates also exclude hidden rows
to avoid unnecessary draw calls. Earlier failed/diagnostic runs are excluded
from acceptance. The fixture also now releases an old host's held mouse gesture
before waiting for a new UPDATE, observes final system completion directly, and
measures ownership after warming the filesystem. The event fixture excludes two
never-spawned setup helpers from its existing Task-entry table; its reservation
is unchanged.

Reserved bank-zero delta is **0 fixed, 0 per public Task and 0 private idle**,
including guards, alignment and unused capacity. The form grows from 315 to 319
live upper bytes but still reserves 320. A selector adds 3,248 reserved state
bytes (including its 512-byte filtered index) and the 28,672-byte snapshot:
32,240 bytes together with the form, before existing host/workstation resources.
The optimized selector object contains 11,918 code bytes and 180 constant bytes.
The private fixture still uses C code banks $0C/$0E/$10, data $0D and lookup bank
$0F; exact fixture extents are in the evidence. No VRAM reservation changes.
Public bindings and the loadable consumer remain FSEL3/FSEL4 work at this slice.

## FSEL3 Standard bindings

The named `fsel_input`/`fsel_exinput` calls and AESPB opcodes 90/91 now share the
selector implementation. The dispatcher saves its input pointers before nested
calls reuse the context arrays. C component ABI 10 adds the two exports; GEMSYS
and applications must be rebuilt together. No AES server wire operation changed.

The optimized fixture passes **215 target checks**, including named/AESPB calls,
context-array reuse, default/custom/truncated captions, empty/default paths,
127-character path and 12-character filename boundaries with buffer canaries,
unsupported path syntax, malformed counts and unchanged failure outputs. It
retains the physical interaction, allocation/retirement failures and ownership
checks from FSEL2. Five independent pixel comparisons cover 285,696 pixels.
Raw/optimized emitted binding/layout probes agree. The ABI generator is current;
the host suite passes 423 tests with four existing skips. The initial host run
caught an old ABI-9 expected package header, updated with the ABI itself.

The warmed heap returns exactly to **2,661,056 bytes**. Minimum ordinary stack
margin is **188 bytes** (idle 192); no stack change is needed. Reserved bank-zero
delta remains **0 fixed, 0 per public Task and 0 private idle**, including guards,
alignment and unused capacity. Heap and VRAM reservations are unchanged. The
production optimized selector object is 12,435 code / 188 constant bytes, an
increase of 517 / 8 from the private implementation. The expanded fixture still
occupies code banks $0C/$0E/$10, data $0D and lookup bank $0F; its exact extents
are recorded separately from production. The packaged consumer and complete
desktop walkthrough remain FSEL4 work. These are development checks only.
