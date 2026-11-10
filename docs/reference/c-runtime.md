# Hosted C runtime

[Reference index](README.md) · [C image contract](c-program-loading.md) ·
[C guide](../guides/calypsi-c.md) · [Implementation plan](../plans/c-runtime-implementation-plan.md)

Current APP ABI 32 uses runtime contract 1, defined in
[c-runtime.json](../../abi/c-runtime.json). Each loaded Image links its own
runtime state and selected pinned Calypsi 5.18 objects. One calling Task owns
an execution. Raw Tasks use the public Exec allocation/I/O interfaces.

## Entry and lifetime

Write `int main(void)`, or `int main(int argc,char **argv)` and select
`--main-signature args`. The builder emits a matching typed call. The loadable
entry is `__exec_c_runtime_entry`, with a generated 32-byte invocation record;
`main` is an application body. Rebuild providers, APPs and dependent objects
when the ABI changes. Ordinary resident/standalone C images retain their
explicit entry and native compiler ABI.

The resident runner calls INIT, attaches/registers AES, calls RUN unless an
early stop is pending, then calls FINISH. FINISH runs normal exit handlers and
closes streams/descriptors. It holds C heap backing until GUI retirement
acknowledges all borrowers. RELEASE sweeps remaining backing, then the runner
returns to the existing native Process DOS cleanup and Task retirement.
Collection releases execution ownership after that retirement acknowledgement.
A failed GUI retirement parks with the Task, Image lease and C backing held.
No loaded-code finalizer runs during collection.

A retained Image receives fresh runtime allocation counters, arguments, errno,
descriptors, FILE lists, standard FILE state, tokenizer cursor and srand(1)
state. Other application globals retain their Image lifetime. An Image admits
one execution at a time; separately loaded Images have independent state.

## Allocation and arguments

`malloc`, `calloc`, `realloc` and `free` use public AllocMem/FreeMem. A 16-byte
upper-memory prefix owns each backing. Payloads are eight-byte aligned, remain
within one bank and have a 65,520-byte ceiling. Heap rounding adds zero through
seven bytes per block. Zero-size allocation returns NULL; free(NULL) is a no-op.
calloc checks multiplication overflow. Failed realloc preserves the original
pointer, contents and ownership; realloc(p,0) frees and returns NULL. Allocation
failure sets ENOMEM and native ERROR_NO_FREE_STORE. Normal frees during RUN
release immediately. FINISH defers physical frees through GUI retirement.

The native tail and argv[0] name are each bounded to 255 bytes. Spaces/tabs
separate arguments outside double quotes; quoted fragments concatenate and
`""` preserves an empty argument. Backslashes are literal. There is no wildcard
or environment expansion. Unmatched quotes fail INIT with ERROR_BAD_ARGUMENTS.
The vector ends with NULL and shares one owned allocation with its strings;
the largest vector/text payload is 1,032 bytes. Application policy, including
QED's single-document rule, is separate.

## Streams and errors

The runtime has sixteen owned descriptors, indexed 3–18. Slots retain full
native BPTR identities. Slots 0–2 wrap the selected Input()/Output(); stdout
and stderr share Output(). Closing their wrappers preserves native ownership.
An absent selection gives EBADF on transfer. Reserve descriptor capacity before
Open can create/truncate. Terminal native Close consumes its slot on either
outcome and is never retried.

The byte-preserving stdio subset includes fopen/fclose, fread/fwrite, integer
fprintf/printf, buffering, position/seek operations, EOF/error indicators and
standard streams. Files support read, write, update (`r+`, `w+`, `a+`), append
and exclusive `x` modes. Stream devices retain their native mode/seek limits.
Text/binary flags do not translate CR, LF, ATASCII or bytes above 127.
The selected formatter is `printf=nofloat` in every independent relink.

A transfer can return a confirmed short prefix and retain its cause for the
library's next transfer. FILE error/errno expose that cause; an I/O failure
never becomes EOF. ferror acknowledges a pending cause while preserving the
error indicator; clearerr clears it. A failed flush retains only unwritten
bytes, so retry does not duplicate its confirmed prefix. stdio splits transfers
at the vendor's signed 32,767-byte count limit; development checks include a
40,000-byte transfer and poisoned FILE allocations.

| Native cause | errno |
| --- | --- |
| No free store / descriptor capacity | ENOMEM / EMFILE |
| Missing object/directory | ENOENT |
| Object in use / already exists | EBUSY / EEXIST |
| File/delete protection / write-protected disk | EACCES / EROFS |
| Disk full / cross-device rename / nonempty directory | ENOSPC / EXDEV / ENOTEMPTY |
| Invalid descriptor / argument or seek | EBADF / EINVAL |
| Unsupported operation / BREAK / broken pipe | ENOSYS / EINTR / EPIPE |
| Other operational failures | EIO |

Ordinary successes preserve errno. A successful main result has secondary zero;
a nonzero result snapshots its native IoErr. A later flush/Close failure after
success produces primary 20 and the first cleanup cause. An earlier nonzero
primary/secondary pair is preserved. Handled errno/FILE errors alone do not
invent another exit failure. Capture/restore the first native cause when an
application performs further I/O before returning a failure.

## Termination and limits

Normal return and exit(status) run at most 32 registered atexit functions in
LIFO order, then flush/close. Registration exhaustion returns failure. _Exit
skips callbacks and pending output; abort and failed assertions do the same,
with bounded diagnostics. Mandatory descriptor/GUI retirement and backing
release still follow. abort returns 20/ERROR_BREAK; an assertion returns
20/ERROR_BAD_ARGUMENTS. This does not promise recovery from corrupted invariants.

The nonlocal boundary contains C activations only. It cannot escape a native
service, ROM or interrupt activation. The corrected 16-byte jump context saves
S, virtual frame pointer, return PC/bank and DP8–15. APP builds disable cross-call
and interprocedural cross-jump optimization. The pinned source corrections and
header are selected by [calypsi-runtime.json](../../toolchain/calypsi-runtime.json);
the installed archive is unchanged and relinking preserves explicit overrides.

Environment is empty. time() returns -1/ENOSYS: the timer clock is not UTC;
file DateStamps are separate native metadata. C threads, signals, locale,
floating printf, arbitrary board CRT initialization, C o65 commands and a
headless C-provider distribution are outside this contract. Other vendor
library facilities are not qualified by this subset.

Reserved bank-zero delta is **0 fixed, 0 root/kernel, 0 per public Task and
0 idle bytes**, including guards, alignment and unused capacity. Scope storage
is 160 image-local bytes (including 32 handler slots); heap bookkeeping adds
22 bytes, descriptor/error state 204, and standard FILE/list state 99, plus
selected vendor state/code and loader backing. A default dynamic FILE and its
64-byte buffer use 128 rounded heap bytes. The resident invocation record uses
32 bytes within the existing Task stack; admission requirements must cover the
actual program. Development checks are not full hosted-system qualification.

The [CR3 record](../development/c-runtime-cr3.json) covers raw/optimized entry
and unwind, 9 raw/17 optimized lifecycle executions, failed retirement retention,
all nine rebuilt APPs starting/stopping, obsolete-ABI rejection and an ordinary
resident C main. [QED consumer acceptance](../development/c-runtime-cr4.md)
covers editing, saving/recovery, Stop and repeated lifetimes beside a peer.
GemARC delivery remains in progress.

[CR5 acceptance](../development/c-runtime-cr5.md) adds GemARC, the generic
`SetFileDate` C binding, matched APP ABI 32 artifacts and selected distribution
walks. The [GemARC guide](../guides/gemarc.md) records archive recovery, supported
methods, timestamps and production admission limits. The additional reserved
bank-zero cost remains zero for fixed state, root/kernel, each public Task and
idle; application code, tables and owned allocations are charged in upper RAM.
