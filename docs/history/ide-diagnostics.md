# IDE diagnostics development record

Follow the [implementation plan](../plans/ide-diagnostics-implementation-plan.md)
and [device contract](../reference/ideplus-device.md).

## D1: retained controller observations

Generated IDE interface revision 2 adds copied controller and APT-slot records.
The controller record uses bytes 704–727 of the existing 1024-byte upper arena;
slot reasons reuse existing partition padding. No reservation or heap allocation
is added. Fixed/per-Task/idle bank-zero delta: **0/0/0 bytes**.

Development checks use the pinned compiler and IDE Plus revision-E/PBI-ID-0
emulator with BIOS 2.1 and AltirraOS816. Native APT fixtures cover direct,
low-byte, MBR and chained tables, revision/cycle/overlap/bounds/offset failures,
unsupported 128/256-byte slots and absent controller/media. Snapshot assertions
cover unattempted state, admission reasons, capacity, access and retention after
stop. Raw and optimized native layout probes cover all three generated records.
Evidence stays in `build/ide-diagnostics/` and the layout development directory.
These are development checks, not a physical-hardware qualification.

## D2: mount failure lifetime

The private DOS registry grows from 108 to 114 reserved upper-memory bytes.
Its new six bytes retain the failed configured slot, admission phase and error
after worker cleanup. A successful retry of that slot clears the failure.
The worker carries its current mount phase; the block adapter records the
existing geometry check's specific rejection rather than repeating it.
Published mount snapshots also copy their existing offline error.
Fixed/per-Task/idle bank-zero delta remains **0/0/0 bytes**.

`tools/test_ide_diagnostics_mount.py` passed seven native development scenarios:
normal mount plus failed/successful remount, incorrect sector count, protected
writable mount, empty APT slot, bad SDFS header, missing controller and missing
disk. Checks preserve IoErr, inspect failures after teardown, reject partially
published startup state and restore heap ownership without modifying media.
Evidence: `build/ide-diagnostics/mount/`.

## D3: boot and interactive presentation

Verbose boot prints copied controller/capacity/APT observations. Plain MOUNT
adds retained mount failures; `MOUNT DIAGNOSTICS` repeats the hardware report and
supports ordinary redirection. Failed startup always explains its mount failure,
including the specific reason behind an IDE open rejection. The renderer
preserves causal IoErr and uses existing output/transfer buffers.

The boot ordering correction initializes the controller when an IDE mount is
configured, then prints its verbose report before the filesystem mounting
announcement and the first filesystem lock. Subsequent filesystem device opens
join the ready driver. SIO-only configurations do not initialize IDE, and quiet
boot suppresses the hardware report. Interactive reporting remains observational.
The correction adds **0 fixed, 0 per-Task and 0 idle reserved bank-zero bytes**;
it uses the existing driver worker and shell stack without enlarging reservations.
Focused optimized native boot checks passed with valid media and an absent
controller. The output observer verified that the filesystem service was still
unstarted during the IDE report and mounting announcement; the transcript also
places mount outcomes afterward. Evidence: `build/ide-diagnostics/boot-order/`.
The 447 host checks and documentation link/whitespace checks passed.

The demo global arena grows by **2048 upper-memory bytes**, from 4352 to 6400,
including all unused capacity. The standard/IDE image uses 5822 bytes (578
spare); VBXE/IDE uses 5834 (566 spare). DOS registry growth is separately counted
in D2. Fixed/per-Task/idle bank-zero deltas remain **0/0/0 bytes**; no Task pool
or interrupt reservation changes. IDE worker calculated stack bound is 736
bytes including its interrupt reserve and dispatch margin, leaving 288 bytes in
its existing 1024-byte requirement. Standard demo stack watermarks leave at
least 721 bytes above the interrupt floor in the exercised worker pools; these
observed depths are lower bounds, not exhaustive stack qualification.

Validation at the development tier:

- 447 host checks passed; generated IDE/DOS definitions and whitespace checks
  passed.
- Five native renderer scenarios passed: count mismatch, protected writes,
  empty slot, malformed APT revision and absent controller. Exact diagnostic
  transcripts stay within 40 columns and retain the original IoErr.
- Native writable/protected/failed-write checks passed. The failed ATA command
  retains its status and hardware error separately from logical error 3.
- Exact standard/IDE and VBXE/IDE OF816 demos passed boot, MOUNT, diagnostic
  display, redirection to RAM, CAT of the captured report and complete shutdown
  with guards/ownership checks. Both builds include five-second OF816 autoboot
  and fit the existing Atarimax cartridge formats.

Evidence and disposable packages are in `build/ide-diagnostics/`; no full release
qualification matrix or physical-hardware test was run. No packages were published.
