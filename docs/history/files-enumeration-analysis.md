# Files directory enumeration analysis

[Measurements](../development/files-enumeration-analysis.json) ·
[Observer](../../tools/trace_files_enumeration.py) ·
[Earlier New Window analysis](window-opening-analysis.md) ·
[Cheap metadata implementation](directory-metadata.md)

## Finding

Directory enumeration is a better next target than another small popup
optimization. A warm scan of nine `SYS:` entries takes **193 ms**; 29 entries
in `SYS:C` take **533 ms**. Neither performs physical disk I/O or runs the
presenter during the measured scan. Even two entries in `RAM:` take **67.5 ms**.

The largest opportunity is amortizing the repeated public DOS transaction.
Files asks for one entry per `ExNext`, and each request repeats caller
admission, packet submission, worker queue selection, dispatch, publication,
reply and collection. Backend decoding also costs time, but clearing the FIB,
copying names or removing duplicate validation alone will not remove most of
the delay.

Recommend a bounded public batch-enumeration operation, reused by the shared
Files/file-selector scanner. Keep the existing worker, ownership and ordinary
preemption. No new cache or GUI-private kernel service is indicated.

## Current measurements

The unchanged DR2 package contains production code `cbc0a16b`; HEAD `853bf014`
adds its measurement record. The observer exercises the desktop's folder
windows, which use the same browser/scanner implementation as `FILES.APP`.
It navigates and refreshes through physical keyboard/mouse input and reads
guest state without patching it.

Times start at `FileScanBegin` and end at the final `FileScanNext`, including
its `UnLock`. They exclude later sorting, layout, menu updates and drawing.

| Directory/action | Entries | DOS transactions | Enumeration elapsed | Physical SIO commands |
| --- | ---: | ---: | ---: | ---: |
| `SYS:` warm Refresh | 9 | 13 | **193.290 ms**, median; 192.477–193.290 | 0 |
| `SYS:C` first visit | 29 | 33 | **1,678.851 ms**, one sample | 2 |
| `SYS:C` warm Refresh | 29 | 33 | **533.148 ms**, median; 531.953–535.800 | 0 |
| `RAM:` warm Refresh | 2 | 6 | **67.541 ms**, median; 67.541–67.543 | 0 |

Each warm row has three repetitions. The first C visit is partially cold: two
directory transfers miss the cache, but boot and the root listing have already
used the filesystem. It is not a fully cold-cache benchmark. Serial `command`
records represent asserted/deasserted command-line edges: four edges here mean
two transactions, not four sector reads.

The first navigation to RAM takes 124.659 ms and overlaps 39.782 ms of presenter
CPU from the path dialog. Warm RAM refresh removes that interference. RAM has a
different backend and only two entries; it is a control for the shared request
overhead, not an equal-directory backend comparison.

The older 270 ms root result included concurrent New Window frame work. The
193 ms refresh here is a different workload, not a matched 270→193 ms speedup.

## Where the warm time goes

The first warm C repetition provides a representative, exactly reconciling
breakdown; the overview above reports the median separately.

| Execution owner | CPU/time in the 531.953 ms scan |
| --- | ---: |
| Desktop/Files caller, including its kernel calls | 113.385 ms |
| Filesystem Task, including its kernel calls | 324.941 ms |
| Native IRQ/NMI execution | 93.627 ms |
| Presenter, other public Tasks and idle Task | 0 ms |

This is CPU work shared between caller and filesystem, not a renderer waiting
for the display lock. Interrupt time remains separate from their CPU charges.
It cannot simply be attributed to the filesystem or treated as removable work.

By contrast, the first C visit includes 874.128 ms charged to idle and 9.655 ms
to the SIO Task, alongside 339.111 ms filesystem CPU, 117.596 ms caller CPU
and 338.361 ms of interrupts. That case has real media waiting. Faster cached
enumeration will not remove physical transfer latency.

### Repeated request costs

For 29 entries the application issues `Lock`, `Examine`, **30 `ExNext` calls**
(29 entries plus end), and `UnLock`: **33 synchronous DOS transactions**.
Successful `ExNext` calls take 13.370 ms median, with a 13.108–19.628 ms range
in the representative scan. Initial `Lock`/`Examine` takes 89.244 ms, including
path resolution; the final `UnLock` takes 12.406 ms. Retaining those setup costs
limits the gain from batching only `ExNext`.

These routine costs expose the repeated work. Rows are inclusive and **must
not be added to one another indiscriminately**: publication includes reply,
directory decoding includes date conversion, and higher-level calls include
their children.

| Observed operation | Calls | Charged CPU |
| --- | ---: | ---: |
| Caller `DOSCLIENT.Call` | 33 | 72.730 ms |
| Worker mounted-volume `FSHANDLER.TakeStep` | 41 | 48.222 ms |
| Worker `FSPACKET.Reply` | 33 | 58.748 ms |
| Worker cancellation checkpoint | 239 | 9.099 ms |
| Cancellation queue pump | 195 | 1.487 ms |
| SpartaDOS date conversion | 40 | 25.352 ms |
| FIB clear/name/fill/cookie publication, combined | 30/30/30/31 | 14.110 ms |
| Duplicate worker lock lookup (`FindObject`) | 32 | 2.445 ms |
| Worker result-buffer mapping check | 31 | 3.797 ms |

The caller performs 33 `PutMsg`, 66 `GetMsg`, and 34 DOS-context queries. The
worker performs 172 `GetMsg` calls to obtain 33 requests: **139 return empty**.
The worker also enters 210 Forbid/Permit pairs in this interval.

`FSHANDLER.TakeStep` scans mounted-volume ports; `FSMUX.Take` additionally
checks the management port and checks it again before sleeping when ordinary
ports are empty. This explains why queue probes greatly outnumber packets.
The 41 complete mounted-volume scans comprise 33 claims and eight idle results.

The empty `GetMsg` calls, measured through their following branch to `Permit`
entry, consume **15.289 ms CPU**. This excludes the surrounding Forbid/Permit
cost; skipping those calls safely has a larger potential than this number
alone. It remains a smaller opportunity than amortizing the whole transaction.

There are no observed `FindTask(NULL)` calls in these scans. `DOSCORE.Current`
does enter the kernel to obtain the Task's DOS slot. The 33 intervals from
that entry to `EnsureSlot` entry total **15.554 ms CPU**, including caller setup
instructions; this is a useful bound, not an isolated syscall measurement.

### Backend and validation

The cheap-metadata work is present: ordinary enumeration does not measure each
selected file's extent or read its contents. SpartaDOS retains a directory
cursor, but still routes each 23-byte record through `SDFSFILE`'s general read
state machine, including sector/map checks, resumable steps and metadata decode.
`SDFSFILE.Drive` performs a wide division by sector size. Date conversion loops
over preceding months. These are secondary candidates after request overhead.

`FSDIRECTORY.Select` repeats the caller's lock lookup and result-buffer checks.
For comparison, ordinary file Read/Write dispatch already trusts the object
resolved and retained by DOS. Matching that approach is a sensible cleanup;
the measured duplicate lookup is only about 2.4 ms for this complete scan.
Cookie identity, namespace epoch and cancellation/publication ordering have
different purposes and should not be removed as if they were the same check.

FIB clearing already uses the bulk memory primitive: its 30 clears consume
7.124 ms. Replacing the result format solely to save that clear would be a
small gain beside the request lifecycle. Names and rendering are not the
dominant cost inside the scan.

## Recommended next work

1. **Batch directory results at the DOS boundary.** Start with a bounded
   caller-owned buffer for eight entries, then compare sixteen. Keep ordinary
   `ExNext` available. Share the new public operation through `FileScan`, so
   Files and the file selector use it; native directory commands can migrate
   separately. With end-of-directory reported in a short final batch, C would
   need seven total transactions at eight entries, or five at sixteen, versus
   33 now, retaining `Lock`/`Examine`/`UnLock`. This is a transaction-count
   estimate, not a measured speedup.
2. **Trim admission and empty-port polling.** Avoid resolving an already
   retained lock twice. Consider advisory empty-queue tests that skip the
   costly probe but preserve durable signals, authoritative dequeue, management
   fairness and the check-before-Wait race. This can be a small independent
   preparation slice, but it will not transform a half-second listing alone.
3. **Remeasure, then simplify backend work where it still matters.** Candidates
   are month-offset lookup, power-of-two sector arithmetic and a cheaper path
   for a directory record already in the current sector. Keep malformed-media
   checks and existing mutation invalidation. Do not introduce another directory
   cache before measuring the batched path.

Batching should reduce packet exchanges, not create a long nonpreemptible
section. Keep ordinary preemption, cancellation checkpoints and I/O suspension
inside the worker. A batch occupies the filesystem service for longer, so bound
it and check another filesystem client as well as GUI input during development.
Buffers belong in existing caller/upper-memory storage, not enlarged bank-zero
reservations. Exact ABI, partial-result/error semantics and allocation belong
in the implementation design; this analysis does not choose a new public layout.

The measured `Call`/`TakeStep`/`Reply` costs contain roughly 180 ms of CPU in the
representative scan and largely describe separate phases. They are an opportunity
budget, not a promise that all 180 ms disappears: some transactions, service
work, copying and synchronization remain. This is nevertheless substantially
larger than the popup filter's estimated 3.5 ms before overhead.

## Evidence and limits

Development analysis: eleven real application scans in one optimized packaged
capture, plus an unprofiled functional control with the same listings and paint
counts. Normal EXIT completes with zero live Tasks and intact guards in both.
No production code, ABI, compiler pin, disk contents or demo package changes.

The unchanged OF816 ZIP SHA-256 is
`ade55940e2468bd000ece5a22266f2b23deac34f47ad1827f708c305ff6d33d3`.
The machine is 800XL/PAL, 65816 x8, VBXE, 64 KiB plus 63 upper banks,
256-byte SDFS system sectors, accurate generic56k timing, with SIO patching,
burst I/O and random delay disabled. The evidence records compiler, ROM,
emulator, package, media and observer hashes.

CPU and elapsed spans come from passive instruction markers in emitted code.
Debugger/frame waits surrounding input and inspection are outside the scan
boundaries. The observer's broad relocation markers slow host execution;
reported milliseconds are emulated machine time. Exclusive accounting assigns
each CPU interval once and reconciles Task CPU plus interrupts with elapsed
time. Full inclusive/per-call traces remain in `build/files-enumeration-trace`;
compact measurements are linked above. The unprofiled control is under
`build/files-enumeration-capture`.

No p95, general cold-cache, MyDOS, IDE or real-hardware claim is made. Later
painting is excluded, so these numbers do not establish complete refresh or
first-visible-content latency. Full qualification and broad regression matrices
were not run for this analysis. Reserved bank-zero delta is **0 fixed, 0 per
public Task and 0 idle bytes**, including guards, alignment and unused capacity.

Reproduce using the retained unchanged bundle:

```sh
python3 tools/trace_files_enumeration.py \
  --bundle build/damage-retirement/demo --output build/files-enumeration-new
```
