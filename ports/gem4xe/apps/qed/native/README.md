# Native QED runtime

[Source preparation](../README.md) · [Feasibility design](../../../../../docs/plans/gem4xe/qed-native-feasibility-design.md)

This is private application code built against the current public Exec/GEM
headers. The QED/cflib patches preserve their upstream notices. It contains no
donor startup, COP bridge, board allocator or forced Task termination.

QED uses the [shared C runtime](../../../../../docs/reference/c-runtime.md).
Its main receives common argc/argv and rejects extra document names. Allocation,
FILE/descriptor ownership, errno, library reset and termination are common;
Malloc/Mfree and GEMDOS file names are thin port adapters. No private startup,
heap sweep, FILE list or board-exit fallback remains. Relative paths use the
Process's inherited directory. Capture/restore the first native cause across
later editor I/O when returning a failure.

`document.c` prepares a detached donor LINE ring with a 4 KiB read buffer and a
1,024-byte line buffer in private upper memory. One poll reads at most 4 KiB;
positive short reads continue, EOF is distinct from error, and terminal Close
is checked before readiness. LF/CRLF must be uniform, including a CR/LF pair
split across buffers. NUL, CR-only, mixed endings and lines beyond 1,023 bytes
fail without conversion. Empty and unterminated text keep their exact logical
representation. Reading never creates or writes a file.

The command controller owns preparation, cancellation and the modified decision.
Only a complete accepted candidate transfers into the existing TEXT/window;
Undo/selection/viewport reset and the private clipboard remains. Cancel/failure
frees the candidate and preserves the old state. Native causes survive buffer,
ring and descriptor cleanup. Dates remain unknown; Save will establish its own
write metadata. File selection uses native path[128]/leaf[13] capacities.

The common sixteen owned slots retain complete native BPTRs. Standard input
borrows Input(); output/error share Output(). The wrappers preserve native
ownership. See the common runtime for byte-preserving modes, pending transfer
errors, EOF, consumed Close, buffering and the pinned integer formatter. QED's
GEMDOS-shaped calls retain LONG transfer counts and the translation below.

| Native error | C errno | GEMDOS result |
| --- | --- | --- |
| OBJECT_NOT_FOUND, DIR_NOT_FOUND | ENOENT | -33 |
| NO_MORE_ENTRIES (descriptor admission) | EMFILE | -35 |
| BAD_NUMBER (descriptor) | EBADF | -37 |
| NO_FREE_STORE | ENOMEM | -39 |
| ACTION_NOT_KNOWN | ENOSYS | -32 |
| SEEK_ERROR, BAD_ARGUMENTS | EINVAL | -64 |
| WRITE_PROTECTED, DELETE_PROTECTED | EACCES | -36 |
| DISK_WRITE_PROTECTED | EROFS | -36 |
| OBJECT_IN_USE, OBJECT_EXISTS | EBUSY, EEXIST | -36 |
| DISK_FULL | ENOSPC | -1 |
| RENAME_ACROSS_DEVICES, DIR_NOT_EMPTY | EXDEV, ENOTEMPTY | -1 |
| BREAK | EINTR | -1 |
| Other operational failures | EIO | -1 |

The generic GEMDOS error -1 retains its precise native cause in IoErr and the
runtime's last-failure slot. There is no fabricated successful result for an
unsupported operation.

Metadata uses `ExamineExact`, checks its size flag and copies the native
DateStamp. An all-zero or invalid DateStamp is explicitly unavailable; it is
not a valid zero calendar date. The native timer clock is not UTC. Standard
`time()` returns -1 with ENOSYS, and the environment is an empty list.
Calendar/autosave support is outside the current port. Standard termination
uses the common C-only boundary. QedRetirementFault
retains the Task/Image/backing if an editor borrower cannot retire safely.

The build prepares the pinned [Calypsi source corrections](../../../../../toolchain/calypsi-runtime.json)
in a separate work copy, preserving notices and the installed archive. Common
runtime checks cover FILE initialization, transfers, buffering and termination;
QED saving and recovery checks exercise the editor's own transaction policy.

A failed common allocator backing acquisition records ERROR_NO_FREE_STORE in
IoErr so startup can return its causal failure after GUI/runtime cleanup.
Startup failure uses the Process result before ordinary editor alerts become
available. See [startup ownership](../../../../../docs/history/qed-startup.md).

`path.c` prepares canonical physical paths before reading a document.
A candidate retains its ordinary directory lock through commit or cancellation;
selected-file metadata queries release their locks immediately. No current-directory
mutation or private lock layout is used.

`stage.c` owns exact bounded serialization and a closed exclusive temporary T.
It never publishes D or changes B. The descriptor adapter admits slots before
creation and exposes terminal Close's own cause separately. Stage readiness
is private core state; publication belongs to `save.c`.

`save.c` owns the D/T/B/E transaction and persistent recovery facts. Its
core caller supplies explicit authorization; it does not simulate GUI consent.
Only confirmed logical moves are reversed, and post-publication errors retain
new D. Unknown outcomes perform no speculative filesystem cleanup. `saving.c`
connects Save/Save As to the Cancel-default consent and recovery dialogs.
