# Shared filesystem progress

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystem-progress.md) and [history index](README.md).

[FSSTATUS](../../lib/fs/fsstatus.act) defines the byte-sized `CONST` values used by
MyDOS, SpartaDOS, directory traversal, path resolution and worker callbacks.
The module contains no routines or storage.

| Outcome | Meaning |
| --- | --- |
| `ERROR` | Failed; the workspace retains the causal error. |
| `DONE` | Completed this operation; directory decoding produced an entry or header. |
| `NEED_IO` | Fetch `work.neededSector`, then resume. |
| `MORE` | CPU work remains; the worker checks cancellation before resuming. |
| `END_DIR` | Directory exhausted. |
| `SKIP_ENTRY` | Deleted or unused directory slot. |
| `NEXT_COMPONENT` | A resolved directory leads to another path component. |
| `OPEN_VOLUME` | Worker must open the selected block volume. |
| `IDLE` | Worker has no packet to process and may wait. |
| `STOP` | Fatal worker startup failure; clean up and publish failure. |

Pending I/O and CPU results pass unchanged through the backend dispatcher and
handlers. `SDFSDIR.EntryProgress`, `SDFSNAME.EntryStatus`, and the special
`FSBACKEND.BeginEntry` conversion are removed. Mount recognition also returns
`NEED_IO` when it requests its first sector. Callers use named outcomes rather
than ordering tests such as `status>=4`.

Handlers still consume completed entries, path components and packet results:
those events require real work, such as selecting the next callback or replying
to a caller. After replying, a callback returns `MORE`, including after a failed
packet; packet failure does not stop the service. Ordinary validation booleans,
DOS errors and backend stage numbers retain their separate meanings.

The worker sets a successful prerequisite result for `MORE` centrally. Cached
sectors still return through the same cancellation checkpoints. Sector requests,
I/O failures, final publication checks and partial-read/seek cancellation retain
their previous behavior. The block-fetch API already uses compatible error,
ready and transfer-needed values, which FSIO passes through unchanged.

The matched optimized mixed-filesystem integration image shrinks from **325,840
to 325,054 routine bytes**, saving **786 bytes** with the pinned compiler
`27119ab2804e795b0bbb067c269826b934271754` and stack guards enabled. This compares
against `288e15e`, using the same program, media geometry and build settings.
Memory maps are identical: reserved bank-zero change is **0 fixed bytes and
0 bytes per Task**, including guards, alignment and unused capacity. No record
layouts, workers, signals or upper-RAM allocations are added.

Development checks: 236 host tests; raw SDFS namespace traversal; optimized
MyDOS metadata and mixed-filesystem DOS integration; warm MyDOS mid-read
cancellation; SDFS mid-read, directory scan, lookup and directory accounting
cancellation. Native guards and ownership cleanup pass. Results are under
`build/development/fs-progress/`. These checks do not constitute release
qualification; the demo image is unchanged.
