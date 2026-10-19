# QED on Exec816 gap analysis

[GEM plans](README.md) · [Implementation plans](../README.md) ·
[AES contract](../../reference/aes.md) · [VDI contract](../../reference/gem-vdi.md)

**Assessment, 2026-10-19:** QED is a feasible native application port, but
requires substantial GEM compatibility and application packaging work. Start
from the existing GEM4XE 65816 source port and rebuild it against Exec's native
Process, AES, VDI and DOS services. The SDX personality is not the proposed
execution path.

Status: source and contract analysis; QED has not been built or executed on
Exec816. The proposed sequence below is not an implemented or qualified port.

## Sources and scope

| Source | Inspected revision |
| --- | --- |
| Exec816 | `bb91f3dd827da60765d0a2d6247f11cc7d2fc367` |
| [QED GEM4XE port][qed-port] | `454beb35fccd72c15a8494431f6637cd0cb553c7` |
| [cflib][cflib] | `ce57817c3f68c7d346d1081768505e81acaee807` |

The QED port already provides a 65816 build and an upstream test for desktop
launch, opening, editing and saving through the file selector. Its source and
porting layer are reusable inputs; its GEM4XE executable, startup and service
bindings are not an Exec application ABI. The inspected cflib revision is a
source-study input, not a verified dependency pin for the donor build.

The resource counts below come from decoding the pinned English
`en/qed_en.rsc`. The donor image-size figure comes from its test documentation,
not a fresh build or an Exec measurement.

## Existing foundation and remaining work

Exec provides preemptive processes, private application data, loadable C
programs, window management, menus, keyboard and mouse events, editable
dialogs, file selection and filesystem operations. The main work is extending
and adapting the supported application interface.

| Area | QED requirement | Required work |
| --- | --- | --- |
| Application loading | A relatively large C application | Measure an Exec build and extend the bounded image profile as required. |
| Resources and menus | Larger trees and additional object features | Expand resource/object/menu support and adapt unsupported decorations. |
| Drawing | Font metrics, alignment, additional writing modes and scrolling | Extend the application VDI subset or patch specific drawing paths. |
| Events and dialogs | GEM button predicates and cflib dialog behavior | Adapt event handling and dialog ownership to Exec. |
| Files and C runtime | GEMDOS calls, stdio, paths, allocation and time functions | Provide a reusable compatibility layer over native Exec services. |
| Memory and lifecycle | Editor buffers, cflib state and deeper call chains | Audit upper-memory allocation, stack use and complete cleanup. |

No new scheduling model is indicated by this analysis. Reusable GEM and runtime
operations should use the existing public kernel services; QED-specific private
kernel operations are not part of the proposed approach.

## Resources and menus

The shipped English resource contains 33,014 bytes, 682 objects and 32 trees.
The main menu tree alone has 126 objects. It includes `G_IMAGE`, `G_BOXCHAR`,
extended flags and free-string resources.

At the inspected Exec baseline, the resource loader accepts 256 objects and
eight trees, with at most 32 objects per ordinary tree. Application menus have
a separate 33-object limit. QED also calls `rsrc_gaddr(R_FRSTR, ...)` for its
alert strings; Exec implements only `R_TREE` lookup.
[Resource implementation](../../../c/calypsi/aes-resource.c),
[object declarations](../../../c/include/gem/objects.h),
[menu contract](../../reference/aes.md#resources-and-popup-menus).

Increasing one limit is insufficient. The port needs larger resource and menu
trees, free-string lookup, and either support or deliberate conversion for
unsupported object types and flags. Preserve resource IDs when adapting the
resource so the editor's references remain valid. Raising tree limits also
requires checking the corresponding traversal and per-form storage.

Menu geometry needs adaptation: Exec reserves 432 pixels for application menu
headings between its focused-window caption and Windows menu. QED's original
menu includes eight headings. Reflow or reduce that menu for the initial scope,
or define a reusable desktop policy for wider application menus.

## VDI drawing and workstations

QED uses text extent and font queries, top-aligned text, text effects,
transparent drawing, XOR cursor drawing and `vro_cpyfm` scrolling. Exec's
current application interface provides fixed-font replacement text and solid
bars, with a much smaller attribute/query surface.
[Application VDI contract](../../reference/gem-vdi.md#resident-application-workstations).

Fixed-font metrics can report the actual 8 by 8 font without introducing a
font loader. Other gaps need rendering work. An initial adaptation could
replace XOR cursor toggling with repainting the affected cell and replace
raster scrolling with redraws. Those choices reduce initial implementation
work, but scrolling and selection latency must be measured. Any later raster
copy operation must preserve clipping and overlapping-window correctness.

There is also a workstation mismatch: cflib initialization opens a virtual
workstation, and QED's `init_global()` opens another. Exec currently permits
one per application. Either deliberately consolidate their state in the
adapter or implement multiple private workstations; silently returning the
same handle would not preserve independent attributes and lifetime.

## Events, windows and dialogs

Matching function names does not establish compatible behavior. QED's event
loop uses this button predicate:

```c
evnt_multi(..., 0x102, 3, 0, ...);
```

Exec rejects that combination. Its current button interface supports only a
narrower set of left-button predicates. QED also requests horizontal
scrollbars, which Exec does not provide.
[Event and window contract](../../reference/aes.md), [QED event loop][qed-events].

Adapt the predicate and press/release handling explicitly, or extend the
general AES interface with the required semantics. Verify keyboard modifiers,
double-clicks and selection dragging against the actual Exec input stream.

cflib's dialog loops need particular care: some retain mouse-control ownership
while waiting for input. Adapt them to Exec's dialog/event model so a QED
dialog does not prevent interaction with other applications. Preserve window
messages and keep UPDATE ownership limited to painting. QED's document-window
count must also respect the shared desktop window capacity.

## Filesystem and C runtime adaptation

QED uses both GEMDOS file operations and standard C file functions. The adapter
needs to provide:

- `Fopen`, `Fread`, `Fwrite`, `Fseek`, close, create, delete and rename, with
  file-handle, return-value and error translation;
- GEMDOS path handling versus Exec's `SYS:` and `RAM:` prefixes, directory
  enumeration and file metadata;
- configuration files, resource discovery and command-line arguments;
- allocation, time functions, stdio hooks and application exit through the
  ordinary Process lifecycle.

These cannot be simple function aliases. Exec's `Seek` returns the old
position, and `Rename` operates within one parent without replacing an existing
destination. The adapter must implement the semantics its callers expect.
[DOS contract](../../reference/dos.md),
[C application startup](../../reference/c-program-loading.md#storage-and-entry-bridge).

Saving requires focused failure tests. QED's existing backup path ignores some
rename results, and its save routine does not check the close result. Adapt
those paths before trusting the port with documents. Cover short/failed writes,
failed close, full disks, backup collisions and recovery; do not imply atomic
replacement when the filesystem does not provide it.
[QED file implementation][qed-files].

## Memory, ABI and application lifetime

The donor test documentation describes an approximately 355 KB image. Exec's
current C image profile limits memory span to 192 KiB and file size to 256 KiB.
The Exec build may differ substantially, so obtain its link map before choosing
new limits. Changes must cover the linker layout, packer, loader and relocation
checks together, retaining the current single application ABI.
[Donor size description][qed-test],
[machine-readable image limits](../../../abi/c-program.json).

QED's text allocator uses roughly 52 KB blocks, fitting Exec's bank-contained
upper-memory allocation model. Documents, resources and application globals
can remain in upper RAM. Allocation failure, fragmentation and repeated
open/close cycles still need tests. Explicitly reclaim allocator arenas and
application-owned blocks on exit; Process cleanup is not general heap ownership
tracking. [Memory contract](../../reference/memory.md).

Bank zero is principally a stack and ABI issue. The donor reserves a 4 KiB
stack and contains explicit near-data workarounds. Exec's ordinary stacks are
smaller, and its C ABI uses huge data rather than the donor's large-data model.
Audit those workarounds and pointer arithmetic against the pinned toolchain;
do not import the donor's entire near-memory reservation. Measure complete
call-chain stack use, including adapter and interrupt headroom, before deciding
whether stack reservations must grow.
[Donor build][qed-build],
[C ABI](../../reference/c-program-loading.md),
[bank-zero budget](../../reference/platform.md#bank-zero-memory-budget).

This documentation change adds **0 reserved bank-zero bytes**, fixed or
per-Task, including guards, alignment and unused reserved capacity. A future
implementation's stack cost remains unresolved and must be accounted for in
its own slice.

## Proposed first scope and sequence

Start with one document window supporting open, edit, selection, internal
copy/paste, undo, find, save and an unsaved-changes prompt. Defer printing/GDOS,
external fonts, AV/MiNT integration and desktop-wide clipboard exchange.

1. **Build and memory:** pin QED/cflib inputs, compile against Exec's ABI and
   establish image size and stack requirements.
2. **Startup and resources:** load the resource, install a suitably sized menu
   and open an empty editor window.
3. **Editing:** implement the necessary VDI/event behavior; verify cursor,
   selection, scrolling and redraw under overlapping windows.
4. **Files:** implement open/save/configuration paths and test failed writes,
   failed closes, full disks and backup recovery.
5. **Coexistence:** run QED beside another GEM application and MD5/ARC; verify
   responsiveness, repeated launch/exit and resource reclamation.

Use focused development checks and emitted-code tests for each implementation
slice, with the pinned AltirraOS ROM/emulator configuration. The present analysis
provides no executable compatibility or hosted-system qualification claim.

[qed-port]: https://github.com/slaapliedje/qed-gem4xe/tree/454beb35fccd72c15a8494431f6637cd0cb553c7/gem4xe
[cflib]: https://github.com/freemint/cflib/tree/ce57817c3f68c7d346d1081768505e81acaee807
[qed-events]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/src/event.c
[qed-files]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/src/file.c
[qed-test]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/gem4xe/tools/ci_gem4xe.py
[qed-build]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/gem4xe/Makefile
