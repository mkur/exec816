# Native QED runtime

[Source preparation](../README.md) · [Feasibility design](../../../../../docs/plans/gem4xe/qed-native-feasibility-design.md)

This is private application code built against the current public Exec/GEM
headers. The QED/cflib patches preserve their upstream notices. It contains no
donor startup, COP bridge, board allocator or forced Task termination.

`QedRuntimeRun` copies bounded arguments, initializes the pinned library's
per-image streams, calls its body, closes remaining streams/descriptors and
frees owned heap backing. The body retires every GUI borrower before returning.
A nonzero body result retains its current native cause through cleanup; the
body must capture and restore its first unhandled cause if it performs later
I/O. A cleanup failure promotes a successful result to 20. Handled operational
errors do not automatically fail an otherwise successful body.

Arguments accept zero or one native path, including a quoted path. Invalid
syntax/extra arguments reach the body with argc=0 so QED can report the error
beside its empty document. Allocation failure returns 20 before entry. Normal
argc/argv storage remains owned by this runtime. The public Process caller must
provide the argument byte count and any current directory to inherit; relative
paths retain the native no-default-directory error when none is selected.

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

The four owned descriptor slots use identities 3–6 and keep complete native
BPTRs. Standard output/error borrow `Output()` and cannot close its native
ownership. Standard input is explicitly unsupported. Retained GEMDOS and
Calypsi hooks use one table; append seeks to EOF for each physical write.
Create/update/exclusive modes use the corresponding public native operations.
Seek returns the new position; rejected native seeks preserve the cursor.
Terminal Close retires the slot on either result. Transfer causes survive a
subsequent Close, and cleanup preserves the first unhandled cause.

The pinned hooks use 16-bit `size_t` and 32-bit `fpos_t`. Read/write errors use
the negated errno representation in `size_t`, as declared by
`<calypsi/stubs.h>`. Hook transfers are bounded to 32,767 bytes so that a
successful result fits the library's signed count. Retained stdio requests are
smaller than that bound; larger single stdio requests are not qualified.
GEMDOS-shaped calls retain native LONG counts. Required integer formatting
selects `printf=nofloat`, including the independent bank relinks. Floating
formatting is outside the retained source scope.

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
`time()` returns -1 with ENOSYS, and the environment is an empty list. Optional
calendar/autosave callers must be removed or adapted in the retained-source
slice. Unexpected exit/assert hooks print a diagnostic and retain the live
Process; expected errors return through their owners.

The build prepares the explicit [Calypsi source correction](../../../../../toolchain/calypsi-runtime.json)
in a separate work copy. It initializes FILE list/unget state, preserving the
original library notices and archive. The emitted file fixture poisons malloc
backing and exercises multiple streams, allocation rollback, buffering and
terminal fclose failure. These checks do not qualify QED's Save/backup workflow.

A failed private allocator backing acquisition records ERROR_NO_FREE_STORE in
IoErr so startup can return its causal failure after GUI/runtime cleanup.
Startup failure uses the Process result before ordinary editor alerts become
available. See [startup ownership](../../../../../docs/history/qed-startup.md).

QW2 prepares canonical physical paths with `path.c` before reading a document.
A candidate retains its ordinary directory lock through commit or cancellation;
selected-file metadata queries release their locks immediately. No current-directory
mutation or private lock layout is used. Save commands remain disabled.
