# Desktop selection and batch file operations

[Implementation plan](../plans/gem4xe/desktop-selection-batch-plan.md) ·
[Desktop contract](../reference/aes.md#small-gem-desktop)

MS1–MS4 are implemented. This record reports development checks, not release or
real-hardware qualification.

## MS1 — selection

Folder selection uses a 32-byte bitmap, selected/selected-directory counts and
press-time modifiers. Both views expose Select All/None and keyboard controls.
Open/Rename require one selected member, even when the keyboard lead was toggled
out of the set. Refresh and sort remap selected filenames using temporary upper
memory. Visible selection changes retain the existing object painting path.

The emitted Browser record grows from 3,861 to 3,947 bytes: 38 bytes of state
and 48 bytes for two menu OBJECTs. The desktop record grows from 2,128 to 2,176
bytes for its menu. The directory snapshot and shared file-selector records do
not change. Each folder allocates refresh-name scratch only when needed, bounded
by 27,648 bytes and freed after remapping.

Raw and optimized emitted Browser/Desktop layout probes pass. A focused
548-check machine-code probe passes in both modes for every bitmap position,
counts, the last remaining member and adjacent state. It caught a Calypsi 5.18
signed-index shift narrowing above entry 31; bitmap helpers now use unsigned
indices, matching their nonnegative domain. Host checks pass 451 tests with
four historical-source checks skipped. The physical-input walkthrough passes
icon/list toggling, Select All/None,
Ctrl+A/Escape, sole-member command gates, refresh/sort remapping, independent
folders, a truncated 256-entry snapshot and entry 255. Full-scene pixel checks
and orderly shell/OS exit pass. The desktop Task used 757 stack bytes with
1,547 bytes remaining above its checked floor. These checks use the explicitly
recorded development disk, not the earlier packaged application bytes.
Exact image inputs and results are in the [evidence](../development/desktop-selection-batch.json).

Bank-zero reservation changes: **0 bytes fixed, 0 bytes for every public Task,
0 bytes idle**, including guards, alignment and unused capacity. The generated
budget remains 10,528 fixed runtime bytes, public reservations
`[1824,1600,1600,1600,1600,1600,2848,2848]`, and 800 idle bytes.


## MS2 — sequential batch Copy

One 974-byte private job owns a frozen pending bitmap and source snapshot.
Copy allocates one separate 16,384-byte buffer for the whole batch (17,358 bytes
combined); an extra Skip button increases each Browser to 3,971 bytes.
The destination directory is checked once. Each existing target offers
Replace/Skip/default-Cancel; transfers and temporary publication remain sequential.
Progress updates only the status strip on each chunk. Terminal results report
done/skipped/remaining counts, and cancellation removes only the current owned
temporary file. Owner close and desktop quit retire the job before its folder.

The physical development walkthrough passes empty, short, exactly 16 KiB and
multi-chunk binary copies with a tail; Replace/Skip/default-Cancel; all-skipped;
cancellation after an earlier completed file; preexisting temporary conflict;
read-only failure; and owner close/desktop quit at overwrite prompts. Independent
ATR extraction verifies all bytes, retained old targets and temporary cleanup.
A second batch and shell HELLO/EXIT pass. Raw/optimized layout probes and the
451 passing host checks (four skips) pass. The final integration slice also
covers the inherited partial-disk-full/single-copy walkthrough and measurements.
Bank-zero reservation delta remains **0 fixed, 0 per public Task, 0 idle bytes**.


## MS3 — sequential Delete and folder refresh

Delete uses the same 974-byte job without a payload allocation. One confirmation
covers the selection; each event turn deletes one entry. Nonempty-directory and
read-only errors stop the batch. Completed deletions clear membership, while
refresh remaps pending filenames. Each Browser adds a two-byte refresh flag
(3,973 bytes total). Affected paths match case-insensitively; volume aliases are
not resolved. Copy leaves its unmodified source snapshot in place and refreshes
open destination views. Sibling dialogs defer refresh until they end.

Physical checks pass mixed files/empty directories, default Cancel, a nonempty
directory after an earlier successful deletion, read-only failure, cancellation
between entries, surviving selection, second-batch exclusion and deferred refresh
with typed input preserved. The refresh case uses lowercase destination spelling.
Independent extraction verifies completed changes and untouched remaining files;
shell HELLO/EXIT, stack/domain guards and raw/optimized layout probes pass.
The pixel oracle now applies the existing OBJECT extent to folder G_STRINGs,
including clipped long error summaries; target rendering semantics are unchanged.
Host checks pass 451 tests with four skips. Bank-zero reservation change remains
**0 fixed, 0 per public Task, 0 idle bytes**.


## MS4 — integration and measurements

The final desktop and Files programs use the repository's actionc pin
`81dd7dc53377c772602cc09992bdf2a694b4a43b` and Calypsi 5.18. The host release
compiler wrapper accelerates the build; guest optimization and the compiler
revision are unchanged. No public API, kernel or driver changes are required.
A final cleanup adjustment retains a Close failure separately from an earlier
operation error. Filesystem enumeration errors retain the existing shared
helper's policy of discarding incomplete snapshots.

The exact OF816 ZIP passes the single-file operation walkthrough (including
partial disk-full replacement, retained old target, cancelled temporary, TXT
launch/collection and saved-settings restart), batch Copy with independent
binary readback, and standalone Files selection/list/resize/close. Standalone
Files returns both heap totals and largest extents to
`[2335800,65536,2335800,2031616]`, and restores the ownership ledger. After a
partially completed/cancelled batch and an all-skipped batch, free heap returns
to the warmed baseline of **2,335,688 bytes**. Unavailable destinations retain
the editable path dialog and report the DOS error without admitting a job.

### Selection feedback

| Selection | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Icons, plain click | 182.9 ms | 182.9 ms | 183.1 ms |
| Icons, Shift-click | 138.4 ms | 138.7 ms | 138.7 ms |
| List, plain click | 118.0 ms | 118.7 ms | 118.7 ms |
| List, Shift-click | 118.0 ms | 118.0 ms | 118.0 ms |

Each case contains forty physical completed-release edges to matching whole
work-area scanout, including the status strip. Geometry, the three-frame press
hold and fifteen-frame settling interval are fixed; polling uses PAL frames,
with no disk I/O. The observer reads the OBJECT tree after its paint counter
advances, avoiding a partially updated tree, then compares actual pixels.
These are endpoint measurements, not a breakdown of renderer execution time.

Each changed selection uses one paint transaction. Repeating a sole selection
does not repaint; Select All also uses one transaction. Plain arrows replace
membership, an arrow without a lead selects the first entry, and Shift-Up/Down
adds the destination. The selection path retains selective object painting;
this slice adds functionality and a measured baseline, not a latency claim.

### Throughput and independent Panel feedback

The matched 16 KiB comparison copies the same 32,805 bytes on fresh 2,880-sector
WORK media, with accurate Generic 57600 SIO, PAL, 8x 65C816 and the pinned
AltirraOS/VBXE configuration. First active payload READ to job retirement is
**54.69 s (600 bytes/s)**, versus **54.88 s** in the earlier 16 KiB baseline.
Data transfer ends at 54.26 s; Close/publication takes the remaining 0.43 s.
This is one completed transfer per implementation, not a throughput percentile.
The measured desktop APP is byte-identical to the final packaged application.

A batch of four files (empty, 37 bytes, exactly 16 KiB and a two-chunk file
with a 37-byte tail) copies **49,226 bytes in 99.88 s**. This wider boundary is
Return submission through job retirement, including directory admission,
per-file opens and publication; it is not directly comparable to the single-file
payload-only start boundary.

| Panel workload | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Idle | 80.3 ms | 100.3 ms | 100.3 ms |
| Concurrent 128 KiB copy | 80.3 ms | 140.2 ms | 180.6 ms |

Each row contains forty physical press edges to matching button scanout with
PAL-frame polling. Relative to the earlier loaded 16 KiB sample, median improves
from 100.2 ms while p95 worsens from 120.5 ms. These small phase-sensitive samples
do not establish a general latency improvement or close an HY4 gate.

Escape during the first Read reaches Close in **24.29 s**, with cleanup complete
at **38.49 s**. During the first Write those times are **12.98/27.19 s**.
These are two controlled phase samples, not worst-case bounds. The existing
throughput/cancellation tradeoff remains; no small-buffer gate was introduced.

### Memory and package

Final emitted sizes are Browser **3,973** bytes (3,976 heap bytes), Desktop
**2,176**, file job **974** (976 heap bytes), and a separately allocated
**16,384-byte** copy buffer. The job and payload reserve 17,360 heap bytes while
copying. Delete allocates only the job. Packed refresh names need at most
27,648 temporary bytes. Directory entry arrays and Task reservations are unchanged.
Desktop/Files load spans are 70,189/71,386 bytes; both remain two-bank images.
Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 idle**, including
all guards, alignment and unused capacity.

The final host run passes **451 tests**, with four historical-source checks
skipped. Raw/optimized emitted layout and bitmap probes are recorded under
MS1–MS3; the final integration and performance sessions use optimized machine
code. Stack/domain guards and orderly shell/OS exit pass. Across the final
sessions, the smallest public-Task margin above its checked floor is **183
bytes**, idle **121 bytes**, and the desktop **1,553 bytes** (751-byte peak).
The [machine-readable evidence](../development/desktop-selection-batch.json)
retains input hashes, configurations, samples and the individual stack records.

The final archive is `build/desktop-selection-ms4/demo/exec816-demo.zip`, SHA-256
`736bf1a5e3819c59c0bd515d77559f741d375025a787bd7c10a89551d42c7c57`.
All 22 checksum entries pass. It contains boot/media files, the guide and license
notices; evidence and intermediates remain outside the ZIP. OF816 and its
five-second autoboot are retained. Launch locally with:

```sh
./build/desktop-selection-ms4/demo/launch-altirra.command
```

This is focused emulator development evidence, not release, IDE or real-hardware
qualification. Long status text is clipped by narrow windows; volume aliases
require manual Refresh; recursive operations, Replace All and dragging remain
separate work. The Atari keyboard matrix cannot produce Ctrl+Shift with the
horizontal cursor keys, so physical Shift-arrow coverage uses Up/Down. No input
adapter workaround or keyboard policy change was introduced.
