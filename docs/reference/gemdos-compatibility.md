# GEMDOS source compatibility

[Reference index](README.md) · [C runtime](c-runtime.md) · [DOS](dos.md) ·
[Implementation plan](../plans/gemdos-compatibility-implementation-plan.md)

Include `<compat/gemdos.h>` and select `--gemdos` with
`tools/build_c_program.py`. This opts a rebuilt Calypsi C APP into the shared
source library. The current APP ABI is declared in
[c-program.json](../../abi/c-program.json); declarations and constants come
from [gemdos-compat.json](../../abi/gemdos-compat.json). QED and the
[original MGVIEW port](../guides/mgview.md) select the same library
automatically. This is a source subset, without TOS binary execution,
TRAP dispatch, basepages or a second filesystem.

## Supported calls

| Calls | Contract |
| --- | --- |
| Fopen | Modes 0/1/2 mean existing-file read/write/update; other bits return EINVFN. |
| Fcreate | Create/truncate with default attributes (zero) only. |
| Fread/Fwrite | LONG binary byte counts/results, positive short prefixes and EOF; no newline translation or exact-fill loop. |
| Fclose | Consume the descriptor on success or terminal failure; never retry it or replay an earlier transfer error. |
| Fseek | Origins 0/1/2 mean beginning/current/end; return the resulting position. |
| Fdelete/Frename | Native DOS deletion/rename restrictions; Frename's reserved first argument must be zero. |
| Fcntl | Only FSTAT (`0x4600`), with the XATTR pointer carried in the LONG argument. |
| Malloc/Mfree | Common-runtime allocation and lifetime; Malloc returns a huge pointer or NULL. |
| Pterm/Pterm0 | Ordinary exit/status zero through the common runtime, including FINISH, GUI retirement and RELEASE. |

WORD is two bytes, LONG and huge C pointers are four. File calls return LONG;
FSTAT returns zero on success. Owned descriptors are the common runtime's
sixteen slots 3–18. Wrappers 0–2 borrow Input/Output; closing those wrappers
preserves native ownership. Paths use native `SYS:`, `WORK:`, `RAM:` and relative
DOS semantics; there is no implicit Atari drive-letter translation.

A positive partial transfer can retain an error for the next transfer. Metadata
queries preserve that pending error. Applications requiring an entire file must
check the returned count and preserve the cause before their own cleanup.
Fclose does not turn an already reported read error into another close failure.

## FSTAT information profile

XATTR is 52 bytes, with LONG size at offset 16. The generated
`GEMDOS_XATTR_SIZE_TYPE_ONLY` macro advertises the information subset: exact
nonnegative size and S_IFREG type bits only. All remaining fields are zero and
unavailable, including timestamps, IDs and Unix permissions. This does not
promise complete MiNT stat behavior.

FSTAT queries the opened object's identity through public ExamineFH. It leaves
the file position unchanged, including inherited shared positions. A valid empty
file succeeds with size zero. Unsupported streams/commands, invalid descriptors,
unavailable/bounded size and allocation/I/O failures leave the caller's complete
output record unchanged. The size is an observation; applications must handle
changes between metadata and Read.

Temporary FIB storage uses the common upper heap: 260 payload bytes plus the
16-byte runtime prefix, rounded to 280 bytes. It is released before return.
The initialized XATTR result is a 52-byte local record. No additional descriptor
registry, heap ownership list, worker, scheduler lock or drawing ownership is
introduced.

## Allocation and errors

Malloc admits at most 65,520 payload bytes, within one bank. Check LONG lengths
and multiplication before allocating document buffers or pointer indexes.
Zero returns NULL without allocating; values below -1 return NULL/BAD_ARGUMENTS;
oversized requests return NULL/NO_FREE_STORE. Mfree(NULL) succeeds as an extension.
Other pointers must be live allocations from this runtime.

`(LONG)Malloc(-1)` gives the largest currently admissible payload, capped at the
same limit and excluding the ownership prefix. The result is encoded as a
pointer; convert it to LONG and never dereference it. It is not a reservation.
Callers owning a sufficient contiguous native buffer can still use larger LONG
transfers; this does not enlarge ordinary malloc or add a cross-bank allocator.

| Native cause | GEMDOS result |
| --- | --- |
| OBJECT_NOT_FOUND / DIR_NOT_FOUND | EFILNF (-33) / EPTHNF (-34) |
| Descriptor capacity / BAD_NUMBER | ENHNDL (-35) / EBADF (-37) |
| NO_FREE_STORE | ENSMEM (-39); Malloc returns NULL |
| ACTION_NOT_KNOWN | EINVFN (-32) |
| BAD_ARGUMENTS / SEEK_ERROR | ERANGE (-64) |
| Protection, read-only media, busy or existing object | EACCDN (-36) |
| Other I/O failures | -1; preserve full native IoErr |

File failures also retain the cause in the common runtime's file-error slot;
errno uses the common C translation. Allocation keeps errno/IoErr conventions.
Ordinary success does not clear every error channel. One calling Task owns each
loaded runtime execution; separately loaded Images have independent state.

Reserved bank-zero change is **0 fixed, 0 root/kernel, 0 idle and 0 per public
Task bytes**, including guards, alignment and unused capacity. Wrapper code and
scratch use upper RAM. Development probes cover the admitted subset; they do not
qualify the complete hosted system or implement the MGVIEW GUI.
