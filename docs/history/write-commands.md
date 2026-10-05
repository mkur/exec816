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
