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
