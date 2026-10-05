# MyDOS and SpartaDOS write implementation

The [W0–W9 plan](../plans/filesystem-write-implementation-plan.md) is implemented.
The [write contract](../reference/filesystem-writes.md) describes current behavior;
[development evidence](../development/filesystem-write.json) records the selected
builds, source hashes, compiler/ROM/emulator pins, cases and measured memory.
This is development evidence, not release or physical-device qualification.

## Implemented behavior

Explicitly writable mounts support create/update/truncate, overwrite and append,
Flush, final Close, directory creation, deletion and same-parent rename on both
128- and 256-byte media. The shared worker stages verified sector writes, reserves
allocation before publishing references and removes reachability before freeing
sectors. It keeps the native incomplete flag until the last writer closes.

Independent readers, writers and locks conflict with an existing writer.
Inherited wrappers share its backing, cursor and lease; detached inheritance
wrappers participate in the same lifetime. Stop drains retained objects and
packets. A terminal failed Close consumes its handle and releases ownership;
Process and shell cleanup preserve the causal error and remain usable.

Mounting still reads one format header. It does not enumerate files, reconstruct
allocation ownership or recompute free counts. Local operations validate the
metadata and chain/map they touch, assuming consistent initial allocation.
The full allocation checker is a host development tool, with no resident code
or volume-sized ownership bitmap. The [mutation tables](../plans/filesystem-write-protocol.md)
record ordering and failure limits.

DOS ABI revision 5 and program ABI revision 9 add Flush, CreateDir, DeleteFile
and Rename providers. The mount descriptor grows from 44 to 46 bytes for access
policy. Commands and the demo are rebuilt against the current ABI.

## Executed development checks

The JSON record lists the exact selected runs; the following groups explain
what their assertions establish.

| Area | Executed scope |
| --- | --- |
| Host and generated contracts | 339 host tests; affected ABI/generator checks and documentation links. |
| Sector foundation | Raw/optimized verified 256-byte WRITE and block write-through; selected 128-byte STOCK810 and 256-byte Generic 57600 cases, cache fallback/warm replacement, immutable buffers, bank crossings and committed completion collection. |
| Physical serial failures | Optimized 256-byte WRITE against the pinned responder: absent drive, malformed data checksum, command NAK, terminal device error after mutation and unexpected protocol byte. Requests retire, buffers stop being referenced and the bus either recovers or stays offline as specified. |
| Public file/namespace API | Raw/optimized emitted cases across both formats and geometries, full persisted byte/ownership audits, overwrite suffixes, EOF append, truncate/reclaim, rename, directories, leases, stale enumeration and close/reopen. |
| Allocation boundaries | SDFS growth crosses 62/126 data pointers per map; MyDOS allocates above sector 1023 and across VTOC pages. Existing ten-bit MyDOS links retain ordinal encoding and stop at their address limit. |
| Rejection and directory growth | Protected/read-only/full media, unexplained incomplete entries, malformed selected chains/maps and sparse SDFS writers; rejected operations preserve the whole image. SDFS record straddles and directory growth, native empty forms, MyDOS's full 64-entry root and fragmented space without eight contiguous sectors. |
| Cancellation and ownership | BREAK before mutation, on the wire, between data units and during final Close; namespace operations complete after mutation starts. Stop/drain, parent-first/child-first inherited closes, detached last writers, Process cleanup and error precedence. |
| Metadata failures | Lost completion injected after actual writes at selected allocation, initialization, linkage, entry publication, split-record close and reclamation boundaries. Both formats disable the mount, collect requests, retire ownership and preserve unrelated files. The evidence records every selected write ordinal and host audit finding. |
| Native interoperability | MyDOS 4.50 and SpartaDOS X 4.50 read every Exec-written file, overwrite and append selected content, then Exec reopens and compares the native-modified image. All four format/geometry combinations pass. |
| Shell | Read-only SYS plus simultaneous writable MyDOS/SpartaDOS mounts: ECHO/CAT/CMP, pipeline output, destructive redirection on command failure and late final-Close errors followed by another usable prompt. |
| Packaged demo | Actual OF816 combined XEX, pinned ROM, rebuilt commands, read-only SYS and disposable writable WORK on D8. Five-second autoboot takes 249 PAL frames; the shell/prime walkthrough, saved output, copy/compare and pipeline persistence pass with guards and OS restoration. |

The eight-Task lifetime suites run both raw and optimized emitted code. Selected
format/geometry API and edge cases use four Tasks. Functional filesystem suites
disable emulated rotational delay to keep larger tests bounded; SIO patch and
burst I/O remain disabled. These runs establish functional serial behavior, not
interrupt latency. The packaged demo uses Generic 57600 with accurate disk
timing enabled. Native DOS interoperability uses the original DOS environment
and its recorded acceleration settings, independently of Exec transport tests.
The existing STOCK810 demo smoke also passes with both 128-byte mount profiles
overridden together; this is a selected emulator smoke case, not a broader
physical-drive qualification.

The lost-completion observer returns a failure after the real sector reply;
it does not emulate torn sectors or every peripheral failure. Host audits find
both consistent images and incomplete entries, lost allocations or count
mismatches after interrupted metadata sequences. A passed failure case means
the specified error, ownership and mount-offline behavior occurred, not that
the failed operation rolled back or left a safely writable volume.

For the malformed WRITE checksum case, the physical trace verifies the altered
checksum byte. This pinned peripheral model sends ACK and then no completion;
the required outcome is timeout, an offline bus and unchanged disk bytes. It
does not establish data-checksum NAK recovery on other drives. A separate invalid
sector case exercises actual command NAK and subsequent bus reuse. Terminal
device-error injection changes the real completion byte after the sector was
written, so its persisted outcome is deliberately different.

## Memory and code costs

The same optimized `dos_files.act` fixture was compiled at foundation commit
`b35ae64` and after the writer implementation, using the same pinned compiler,
eight-Task layout, checked stacks and deferred console. The baseline compilation
is a size comparison, not a new execution claim.

| Measurement | Before | After | Change |
| --- | ---: | ---: | ---: |
| Emitted routine bytes | 402,949 | 470,590 | +67,641 |
| Emitted global data bytes | 5,668 | 5,795 | +127 |
| Native payload segment bytes | 421,176 | 488,946 | +67,770 |
| Fixed bank-zero reservation | 10,528 | 10,528 | 0 |
| Total runtime bank zero, excluding OS | 25,408 | 25,408 | 0 |
| Total runtime bank zero, including OS | 56,128 | 56,128 | 0 |

Every per-Task reservation is unchanged, including DPs, guards, alignment and
unused capacity. The older generic budget helper still reports the preexisting
3,072-byte cost of two larger stacks against its compaction baseline; that is
not a cost of this milestone. Upper-RAM fixed reservations are also unchanged
in the fixture comparison.

| Upper-RAM object | Requested bytes, before → after | Heap allocation effect |
| --- | --- | --- |
| Shared mutation workspace | absent → 878 | +880, only if a configured mount requests writes |
| Service | 452 → 460 | 456 → 464 |
| Mount | 66 → 78 | 72 → 80 per mount |
| File backing | 112 → 114 | 112 → 120 per independent open |
| File wrapper | 20 → 24 | unchanged 24 |
| Lock base | 98 → 102 | 0 or 8 extra after rounding the base plus two-byte length, path and NUL |
| Common volume record | 10 → 16 | unchanged 16 |

The workspace contains three 256-byte buffers, one 23-byte row, ten bounded
sector reservations and scalar/entry state. It is shared by the worker, with
no per-file sector buffer. Eight mount descriptors use 368 bytes instead of
352 within the existing reservation. Enumeration uses 22 of the existing 32
private FIB bytes. The demo's 40 providers use 1,352 of 1,664 reserved bytes,
leaving 312; the previous 36 providers used 1,218 bytes.

In the selected eight-Task lifetime runs, the filesystem worker peaks at 594
bytes raw and 546 optimized on its unchanged 1,024-byte stack. This leaves
174 and 222 bytes above the separate 256-byte interrupt reserve. The packaged
demo's Task/idle peaks are 522, 227, 138, 546, 302, 353, 331, 18 and 56 bytes;
stack/domain guards remain intact. These are observed peaks for the recorded
workloads, not a proof over every volume shape.

## Distribution and remaining limits

`tools/build_demo.py` produces `build/filesystem-write/demo-final/exec816-demo.zip`.
The archive contains only the combined boot XEX, matching system/work disks,
pinned ROM, short guide, license notices and checksums. Development manifests,
images used for destructive testing and reports remain outside the archive.
No release was published by this implementation task.

The [current limits](../reference/filesystem-writes.md#format-limits) remain:
no formatting, repair, journaling, cross-directory moves, sparse writes, seek
past EOF or atomic replacement. A lightweight mount cannot establish recovery
after uncertain writes; restore or externally check the medium before writable
remount. Maximum-volume reclamation latency, exhaustive failure/interrupt timing
matrices, alternate configurations and physical drives need separate qualification.
