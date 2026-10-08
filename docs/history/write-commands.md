# Commands for writable filesystems

[History](README.md) · [Command guide](../guides/toolbox.md) ·
[Implementation plan](../plans/write-commands-implementation-plan.md)

COPY, TEE, DELETE, RENAME and MAKEDIR are loadable commands using the existing
writable DOS interfaces. COPY and TEE support APPEND and preserve counted binary
bytes. Namespace operations retain the filesystem's current single-entry,
same-directory rules. Shared ReadArgsOrHelp provides templates and `?` help.
The [guide](../guides/toolbox.md#writable-files) documents exact destination names,
partial outputs, sharing, cancellation and unsupported operations.

No parser, resident provider, filesystem mount scan or ABI revision was needed.
The generated COMMAND constants now expose the existing DOS Seek offsets.
File ownership helpers were extracted unchanged from `command-common.inc` into
`command-files.inc`; mutation commands no longer carry unused text formatting.
The five optimized command files together occupy 13,989 bytes, saving 10,021
bytes against the first implementation that included all presentation helpers.

The [evidence record](../development/write-commands.json) records source hashes,
compiler and machine pins, selected result hashes, command sizes, memory costs
and the distributable archive. These are development checks, not release or
physical-device qualification:

| Scope | Selected checks |
| --- | --- |
| Host and generated bindings | 339 host tests; program generator check; local documentation links. |
| New command bodies | 74 cases in each of raw and optimized emitted code: binary/empty/over-64-KiB streams, short transfers, append/seek, open/read/write/close errors, committed-prefix error precedence, BREAK, validation, help and owned/borrowed cleanup. |
| Existing shared-helper users | CMP 14 and HEAD 22 cases in each mode. |
| Loaded commands | 69 command invocations through physical shell input, on writable 128-byte MyDOS and SpartaDOS media: append, pipes, same-file aliases, directory operations, collisions, read-only rejection, help and late Close failures. Independent host audits check persisted bytes, allocation and directory reclamation. |
| Packaged demo | OF816 five-second autoboot, standard shell/prime display, disk commands, all five write commands, APPEND, EXIT, guards, OS restoration and persisted WORK: contents. Archive entries and every checksum verified. |
| Storage | All fifteen commands and sample files fit both 720×128 formats: 15 free MyDOS sectors or 19 free SpartaDOS sectors. |

The loaded shell fixture uses the pinned paced emulator and ROM with physical
SIO, profile 1, and accurate-disk timing disabled. The packaged demo uses the
normal 57.6k profile with accurate-disk timing enabled. Filesystem final-Close
faults are injected after the selected underlying operation completes; they
check command ownership/error handling and a usable subsequent prompt. The
filesystem implementation's broader 256-byte/native-DOS coverage remains in
its [own record](filesystem-write-implementation.md). This command slice does
not repeat those filesystem checks.

The demo's entire memory layout matches the preceding filesystem-write demo.
Reserved bank-zero change is **0 fixed bytes and 0 bytes per Task**, including
guards, alignment and unused capacity. Task slots, DP ownership, stack pools,
boot reservations and provider capacity are unchanged. New command code and
private image globals reside in upper RAM:

| Command | Serialized o65 bytes | Executable text bytes | Image globals bytes |
| --- | ---: | ---: | ---: |
| COPY | 4,740 | 3,838 | 809 |
| TEE | 4,533 | 3,627 | 806 |
| DELETE | 1,428 | 1,017 | 291 |
| RENAME | 1,633 | 1,200 | 294 |
| MAKEDIR | 1,655 | 1,178 | 291 |

COPY and TEE each include a 512-byte transfer buffer in their globals. Serialized
sizes include imports, relocation and descriptors; executable sizes exclude
the compact descriptor trailer. Observed stack use and reserved capacity are
retained in the evidence record. Generic build reports still compare against
an older bank-zero baseline containing unrelated earlier stack enlargement;
this slice's zero delta compares the immediately preceding filesystem demo.

The distributable is `build/write-commands/demo/exec816-demo.zip`, with the OF816
boot XEX, system and work disks, pinned ROM, short guide, notices and checksums.
Build intermediates, source manifests and test output remain outside the ZIP.
Its source banner identifies the committed plan plus local implementation;
source and artifact hashes in the record identify the exact tested build.

## Directory destinations

The follow-up lets COPY retain the source filename when its destination is an
existing directory, volume root or directory assign. The exact destination `.`
selects the current directory. The [current guide](../guides/toolbox.md#writable-files)
describes these forms and their limits. Missing targets retain ordinary filename
creation; APPEND applies after choosing the filename.

Only the loadable command changes. It tries ordinary output Open first, then
uses existing Lock/Examine/UnLock and resident CSTRING routines when Open reports
a wrong type. Ordinary filename copies add no inspection calls; in particular,
they avoid an extra MyDOS file-length scan. The source stays open during
inspection and output admission, preserving self-copy rejection before
truncation. Inspection locks are released before output Open, and the first
inspection, transfer or cleanup error survives later cleanup. Filesystem policy,
resident providers, argument syntax and ABI remain unchanged.

The optimized COPY has 6,016 text bytes including literals and 17,226 BSS bytes.
Against the preceding 16 KiB-buffer COPY, that adds 2,177 text bytes and 517 BSS
bytes, including alignment. Its serialized o65 grows from 4,723 to 7,314 bytes.
The new storage is a 256-byte path and a 260-byte FileInfoBlock plus one padding
byte. It belongs to the loaded image and is released with it. The Main frame
grows from 30 to 32 bytes; CopyDestination has a 32-byte frame. These local frame
sizes are not whole-call-chain bounds. Reserved bank-zero change is **0 fixed
bytes and 0 bytes per Task**, including guards, alignment and unused capacity.

The optimized controlled fixture passes 48 COPY cases: exact files without
inspection, directories, `.` and APPEND, exact destination spelling, self-copy,
stream destinations, source/inspection/cleanup errors, short and partial
transfers, BREAK, help, and 16 KiB/bank-crossing buffer boundaries. Five focused
cases for TEE, DELETE, RENAME and MAKEDIR also pass after updating the shared
fixture's captured layout and excluding unrelated pane/timer providers.
The host suite passes 397 tests. One optimized physical-keyboard shell session
loads COPY from SYS:C and exercises roots, qualified/relative directories,
current-directory `.` targets, directory assigns, APPEND, replacement, CP,
missing sources, self-copy through aliases, NIL: and read-only rejection on
RAM, MyDOS and SpartaDOS. Independent audits check all saved disk bytes and
allocation, including unchanged pre-existing files. Exact console writes,
native stack/domain guards, OS restoration and final heap ownership pass.
The selected disk cases use 128-byte sectors, Generic 57.6k and fast media;
they establish functionality rather than disk timing.

The [follow-up evidence](../development/copy-directories.json) records the clean
compiler pin, host-binary hash, paced emulator/ROM inputs, selected development
checks and artifact hashes. The compiler host binary uses dev `opt-level=1` and
`debug=0`; compiler source and ABI have no override. No demo ZIP, release matrix
or physical-hardware qualification is included.

## Bounded wildcard operations

COPY sources and DELETE operands now accept LIST-style, case-insensitive `*`
and `?` in the final filename component. The [guide](../guides/toolbox.md#writable-files)
defines matching, limits and error behavior. COPY selects regular files into an
existing directory; DELETE includes empty-directory candidates. Neither recurses.

The shared `command-selection.inc` collects up to eight entries before mutation.
Each record borrows the immutable argument's path prefix and copies its 8.3 leaf
name; exact DELETE arguments are borrowed whole. All enumeration locks close
before execution, so same-volume writes/deletions cannot invalidate the command's
remaining ExNext calls. A ninth selection, unmatched pattern, enumeration error,
BREAK or source-path overflow leaves files unchanged. COPY also checks every
constructed destination's capacity before opening output. Cleanup retains the
original enumeration error. Execution uses ordinary DOS operations and stops
on the first failure; earlier changes remain. These are names, not retained
file identities or a transaction against concurrent namespace changes.

Ordinary exact COPY still tries output Open before directory inspection, avoiding
an extra MyDOS file scan. Its 16 KiB transfer buffer is unchanged. No filesystem,
resident provider, shell parser or ABI change is needed.

The selection storage occupies 418 upper-RAM BSS bytes: eight aligned 20-byte
records, a two-byte count and a 256-byte path buffer. DELETE additionally needs
a 260-byte FileInfoBlock and one alignment byte. Measured optimized costs are:

| Command | Serialized o65 bytes | Text including literals | BSS bytes | BSS increase |
| --- | ---: | ---: | ---: | ---: |
| COPY | 13,352 | 11,535 | 17,644 | 418 |
| DELETE | 6,877 | 5,919 | 998 | 679 |

Text grows by 5,519 bytes for COPY and 4,554 bytes for DELETE against the preceding
exact-name commands on the same compiler pin. Storage belongs to each loaded
image and is released with it. COPY's Main frame remains 32 bytes; DELETE's Main
frame is 30 bytes. Individual selection helpers have frames of at most 20 bytes;
these are local frame sizes, not whole-call-chain bounds. Reserved bank-zero
change is **0 fixed bytes and 0 bytes per Task**, including guards, alignment
and unused reserved capacity.

Development checks pass: 64 optimized controlled COPY cases and 27 DELETE cases,
covering eight/nine entries, exact-plus-pattern bounds, no matches, case folding,
directory filtering, path overflow, invalid parent/target patterns, APPEND,
enumeration/cleanup errors, BREAK and failure stops alongside existing transfer
regressions. A physical-keyboard session loads both commands from SYS:C on RAM,
128-byte MyDOS and SpartaDOS, checks same-volume mutations, assigns, destination
`.`, invalid destinations and no-change overflow/no-match behavior.
Independent disk audits verify every saved byte and allocation, including
unchanged pre-existing files. Native stack/domain guards, OS restoration, exact
console output and final heap ownership pass. The physical cases use Generic
57.6k with fast media for functionality, not disk timing. The host suite passes
397 tests; four focused TEE/RENAME/MAKEDIR cases check the shared fixture.

The [evidence record](../development/wildcard-commands.json) pins the clean
compiler source/ABI, host binary, ROM, paced emulator, generated command profiles
and selected results. It uses the same dev `opt-level=1`, `debug=0` compiler host
binary as the directory-destination slice. No demo rebuild or release/physical
hardware qualification is included.
