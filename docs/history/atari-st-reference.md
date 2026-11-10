# Shared-source Exec and MagiC investigation

[Setup guide](../guides/atari-st-reference.md) ·
[Evidence](../development/atari-st-reference.json) ·
[Native drawing profile](aes-drawing-profile.md) ·
[GEM plans](../plans/gem4xe/README.md)

Hatari 2.6.1 is installed on the development Mac. A pinned ST configuration
runs one optimized 68000 executable under bundled EmuTOS 1.4 and the author's
4 November 2026 MagiC release. Both complete all thirty object-drawing calls.
MagiC's runtime cookie confirms the kernel booted. Screenshots of the final
nested tree were inspected on both systems.

## What is shared

The builder extracts `work`, `draw_objects` and `object_tree` verbatim from
`tests/programs/magic_aes_baseline.c`. The complete native fixture is byte-identical
to the archived EC2 observer input. The extracted functions have SHA-256
`3d9bd46a359857466fbd9bfc72c62b14d823e57958064519bb25bafd2f40e5c6`.
They use conventional GEM calls for UPDATE entry/exit, work and visible
rectangles, VDI clipping and `objc_draw`. The three `G_BOX` trees contain five
objects, 33 objects with 32 siblings, and nine nested objects.

The ST harness supplies process/window startup, independent SDK bindings,
clock observation and reporting. It initializes the work rectangle before
generating each tree. It starts in MagiC's desktop slot because Hatari's host
folder drive lacks the extended file API needed by MagxDesk. Kernel and graphics
drivers come unchanged from the localized release. The final sample stays in a
timer wait for inspection; this run does not test application retirement or
Counter's event loop.

## Observations

Each OS runs two warmups and eight measured calls per tree. The ST timer is
`_hz_200`, read through supervisor mode before and after the complete drawing
operation; report file I/O stays outside that interval. One tick is 5 ms.
Fractional medians arise from averaging the middle two observations, without
increasing the timer's resolution. Final screenshots and framebuffers are
retained. Decoding the monochrome framebuffers and aligning the canvas by each
window's work origin gives **zero differences across 40,960 pixels** in the
final nested tree. This checks that final canvas only; earlier trees were not
captured separately and native Exec uses a different colour format.

Elapsed medians in milliseconds:

| System | Five objects | 33 objects | Nine nested |
| --- | ---: | ---: | ---: |
| EmuTOS, ST monochrome | 42.5 | 115 | 135 |
| MagiC, ST monochrome | 12.5 | 40 | 40 |
| Exec EC2, previous frozen native capture | 55.553 | 130.366 | 205.672 |

EmuTOS and MagiC use the same Hatari settings, executable and monochrome
framebuffer. Their different window furniture changes the canvas origin by
four vertical pixels; the complete 320×128 tree canvas fits on both.

The Exec row reuses the verified EC2 capture; Exec was not rerun for this setup.
It uses an accelerated 65816 at about 14.18 MHz, AltirraOS and a 640×240,
16-colour VBXE display. Its operation elapsed time includes scheduling and
presentation effects observed by the native runner. These differences prevent
a direct compiler, kernel or AES speedup claim against the ST rows. Native
charged CPU and exclusive drawing buckets remain in the linked profile.

## What MagiC suggests for Exec

The inspected `AESOBJ.S` comes from the same pinned upstream revision as the
release. In `objc_draw`/`_objc_draw`, MagiC establishes clipping, hides the mouse
and initializes coordinate arrays for the traversal. `draw_obj_tree` carries
parent coordinates while following head/next/tail links and invokes
`__objc_draw` for each visited object. That routine unpacks the object, checks
its bounds and dispatches drawing. The walker handles depth and hidden trees,
then restores the mouse. This source path draws objects inside AES without an
Exec-style grant callback for each strip.

Exec already carries parent coordinates in its incremental walker. The
remaining structural difference is below traversal: `ExecAESDraw` divides
drawing into bounded strips, obtains a `GemDrawingBorrow` grant for each and
invokes the object callback while it owns shared GSX state. The native profile
observes 12/40/56 grants and 16/46/90 device submissions for these trees. Nine
nested objects therefore trigger 56 object callbacks. Callback/object setup
accounts for about 25–30% of public object-drawing CPU in the measured cases.

This supports investigating preparation once per object, followed by painting
the prepared description within the existing strip grants. It does not yet
establish how much setup is movable, a speedup estimate or permission to move
shared GSX writes outside ownership. Longer grants or submission batching need
separate measurements of input latency and preemption bounds. MagiC's direct
path is a useful reference for repeated work; its architecture alone does not
justify changing Exec's coordination policy.

## Development gate and limits

The optimized emitted ST program completes 30/30 calls per OS, with one
visible rectangle and valid work bounds. The runner rejects stale reports,
missing/reordered/failed samples, unexpected display format and an incorrect
MagiC boot identity. Host checks cover those failure paths and exact shared
source extraction, including CRLF normalization. The full host suite passes
676 tests with four historical skips.

The attempted MagiC extended 640×240 colour configuration rendered incorrectly
and is excluded. Attempts to use a real ACSI disk or TT colour configuration
did not establish a working MagiC reference. The accepted setup is classic ST
monochrome with the resource-free sample as desktop. Multiple clients, window
interaction, text/icons, normal retirement and physical hardware are untested.
This is development evidence; hosted Exec release qualification is unchanged.

Fixed/root/kernel/idle and per-Task reserved bank-zero deltas are **0 bytes**,
including guards, alignment and unused reserved capacity. No target code,
compiler pin or demo package changes in this slice.

Primary source:
[MagiC object implementation at the pinned revision](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESOBJ.S).
