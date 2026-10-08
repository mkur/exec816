# Loadable GEM applications implementation plan

[Plans](../README.md) · [Program loading](../../reference/program-loading.md) ·
[C bindings](../../guides/calypsi-c.md) · [AES](../../reference/aes.md)

Status: LG1–LG4 implemented at the development tier; LG5/LG6 in progress.
Commit each passing executable slice.
The immediate priority is cartridge capacity, followed by independently
loadable, closable and restartable GEM applications.

[LG1 evidence](../../development/loadable-gem-lg1.json): OF816 XEX 962,488
bytes, 69,703 bytes of cartridge headroom and 152,895 bytes saved. The component
contains 156,152 file bytes. Startup from Exec entry to the first ready shell
takes 6,403 PAL frames (128.06 seconds) with accurate Generic 57600 disk timing,
in addition to the five-second OF816 countdown. The desktop walkthrough, six
component failure cases and raw/optimized two-second deadline cases pass.
Bank-zero change: fixed 0, per-public-Task 0, private-idle 0 bytes, including
guards and unused capacity. The upper global arena grows by 512 bytes.

[LG2 evidence](../../development/loadable-gem-lg2.json): raw and optimized
C/native probes pass with concurrent private copies in banks 3 and 5, IRQ/NMI,
retained-state reuse and heap restoration. Each C build is independently
verified at all 62 permitted bases. The [C file profile and entry bridge](../../reference/c-program-loading.md)
are now defined. Fixed, per-public-Task
and private-idle bank-zero deltas are all 0 bytes.

[LG3 evidence](../../development/loadable-gem-lg3.json): SDFS and MyDOS each
pass 87 assertions and 12 Process cycles, including concurrent private images,
retained restart, early return, failed admission/allocation and automatic AES
teardown. Native HELLO still runs. Raw/optimized bridge regressions pass with
IRQ/NMI; heap ownership and stack guards are restored. Import ABI 2 adds Process
argument access. Fixed, per-public-Task and private-idle bank-zero deltas are
all 0 bytes. Cooperative GUI Stop and desktop migration follow in LG4/LG5.

[LG4 evidence](../../development/loadable-gem-lg4.json): `COUNTER.APP` is 4,324
bytes and runs privately in banks 4 and 6. Five lifetimes cover physical close,
cooperative Stop, reload and Stop before entry, with heap restoration. The exact
OF816 desktop ZIP passes the panel/Files/shell walkthrough; its XEX is 974,531
bytes with 57,660 bytes of cartridge headroom. Counter code/model/Task entry are
absent from the shared image. Bank-zero deltas remain 0 in all three categories.

## Starting point and scope

The desktop currently links the counter, Control Panel and Files browser into
the boot image. Files can launch native o65 commands; it cannot load a C/GEM
application. The existing Program/Process machinery already supplies disk
loading, private image ownership, child results, cancellation and retirement.

The [capacity baseline](../../development/gem-cartridge-capacity-baseline.json)
records the inspected desktop artifacts and linker attribution. The OF816 XEX
already exceeds the Atarimax 8 Mbit payload limit. Application bodies account
for much less than the excess, so removing them alone cannot meet this goal.
This is artifact inspection, not a new build or execution qualification.

Deliver two things:

1. Load the shared GUI image once from the system disk, into its existing
   reserved upper banks. Keep it there for the desktop session.
2. Load each application separately through Program/Process, with private
   initialized data and BSS, and reclaim it after orderly exit and collection.

Keep the hybrid AES/VDI model: ordinary calls still execute in the calling
Task; existing messages, signals and timers handle coordination. Loading adds
startup disk traffic, not disk access or RPC to each redraw.

Do not add a general shared-library loader, demand paging, new scheduler policy,
new service Task, GEMDOS emulation, or arbitrary executable XEX support. The
first application profile has one Process per image and no retained callbacks
or additional Tasks executing application code. Classic GEM application source
remains the target; binary compatibility with Atari ST or GEM4XE files is not.

## Selected implementation boundaries

Compiler-pin changes are authorized when needed. Put native ABI, emission and
compiler-runtime changes in actionc with focused raw/optimized regressions,
then update `toolchain/actionc.json` and rebuild affected artifacts together.
The Action! pin does not control Calypsi's C linker; evaluate C relocation using
the actual C toolchain rather than assuming an actionc update supplies it.

### Shared GUI component

Use one build-matched disk component, provisionally `SYS:GEMSYS.BIN`, holding
the linked C GUI segments, tables and BSS description. Initially it can contain
the existing resident application bodies; remove them as applications migrate.
Keep the current fixed C bank layout and native binding addresses. This avoids
relocating presenter callbacks or introducing runtime library discovery.

Reserve those banks through memory adoption even though their payload is no
longer in the XEX. Keep native placement above them. The bootstrap must know
the permitted extents and expected component identity before reading the disk;
the file cannot choose arbitrary load destinations. Read bounded chunks directly
into reserved storage, clear BSS, and publish bindings only after the complete
component and checksum have been accepted. Do not serialize empty bank padding.

Move disk/device/filesystem bootstrap ahead of bitmap-console startup. Reuse
the existing SIO and DOS paths, separating them from shell printing and startup
scripts. This breaks the current ordering in which the bitmap console precedes
system-volume access. Missing, truncated or mismatched components must fail
through the native startup/OF816 restoration path without entering unloaded C
code. The graphical desktop consequently requires the matching system disk.

The component stays pinned until all applications, presenter work, timers and
drawing callbacks have stopped. It is a fixed boot dependency, not an unloadable
Process. It needs no application relocation mechanism.

### C application profile and imports

Keep the current Calypsi large-code/huge-data ABI and Task-relative lower-DP
workspace. Define a small versioned Exec C application container, separate from
the native `action65816.native.v2` o65 contract. Do not pass a C function pointer
through the native `LONGINT FUNC()` ABI unchanged.

Use one bank-aligned upper-heap backing per application, with fixed relative
placement of its code, constants, initialized data and BSS. Whole-bank movement
keeps intra-bank offsets unchanged and makes bank-byte relocation sufficient
for the initial supported profile. Retain the original allocation base and size
for freeing; account for alignment waste and holes. No application acquires its
own bank-zero DP or stack, and no raw bank allocator competes with the heap.

Calypsi's current final-link path does not supply the relocations this loader
needs. Prove the packaging step before depending on it: use controlled links of
the same objects at different bank bases, following GEM4XE's relinking approach
but retaining Exec's DP, pointer and memory model. Compare section/symbol layouts
and reconstruct independent verification links from the generated fixups.
Reject unsupported address-dependent layout or arithmetic on the host. This is
a bounded build profile, not a claim to relocate arbitrary C binaries. Do not
copy GEM4XE's bank-zero allocation or COP signatures. Keep donor analysis and
all generated files outside `~/atari/gem4xe`.

Generate a small, versioned function-import table and application-local tail
thunks from one machine-readable definition. Bind each thunk eagerly at load;
ordinary calls then reach the shared implementation without a dispatcher or
per-call ABI checks. Start with the GEM/VDI, Exec and DOS calls actually used by
the three applications. Keep small compiler runtime routines local; do not
export mutable service globals or private presenter interfaces. Function pointers
to imported calls target the same bound thunks. ABI changes require rebuilding
applications; do not maintain obsolete profiles.

The container needs only version/ABI identity, entry offset, bounded segment
descriptions, BSS size, bank fixups and import bindings. Finalize exact fields
and caps after the emitted-code proof. Check file bounds, supported versions,
relocation/import bounds and allocation failures once at loading. Trust admitted
code and caller-owned pointers afterward. Preserve existing synchronization,
ownership and stack/domain checks.

### Process entry and lifetime

Extend the existing Image dispatch with a C entry kind and an ordinary native/C
bridge. Reuse the admitted resident Process trampoline and finalizer; arbitrary
loaded Task entries remain unsupported. The C startup wrapper calls ordinary
`int main(void)` and widens its signed result to the Process result convention.
Specify argument access through the existing Process argument string; command
line parsing and a full hosted C runtime are outside this slice.

Preserve the existing native checked boundaries and Task stack guards. Calypsi
application code does not acquire Action!'s per-routine stack checks merely by
using a Process; record that limit and measure its stack use under nesting,
blocking and interrupts before accepting the existing stack reservation.

Attach the caller's AES context before application entry. On return, finish
AES/VDI/resource/timer teardown before native DOS and Process retirement. Keep
one DOS context owner: the Process cleanup path and the C wrapper must not both
release it. Do not free image storage while windows, borrowed trees, redraws,
replies, child Processes or callbacks can still reference it. A teardown failure
retains the live owner/image and reports failure instead of freeing it.

Use existing AES ownership records to request cooperative window close for a
GUI child. Native command Stop retains its Process BREAK behavior; a GEM loop
waiting only for AES events must not depend on polling DOS BREAK. Resolve the
child through retained Process/AES ownership, not application model globals.
There is no forced unload or kill in this profile.

## Executable slices

### LG1 — Move the shared GUI payload to disk

- Add the component packer/descriptor and remove its payload from the desktop
  XEX while preserving upper-bank reservations and generated binding addresses.
- Separate native disk bootstrap from console/shell presentation; load the
  component before any C entry, then start the existing desktop unchanged.
- Package the matching component with `build_demo.py`. Add a cartridge payload
  size check using the actual final OF816 XEX and existing cartridge builder.
- Exercise normal boot and missing, wrong-build, truncated and failed-read
  rollback. Verify memory adoption cannot allocate over the reserved C banks.

Gate: the existing desktop works from disk-loaded shared code, without changes
to its drawing path, and both boot variants fit the cartridge payload. Record
actual savings, remaining headroom, disk bytes read and cold-start time.

Implementation finding: accurate Generic 57600 disk timing can exceed the old
one-second deadline when seeking back to directory metadata after reading the
shared component. A diagnostic two-second deadline passed the complete desktop
walkthrough. LG1 therefore also extends that profile's default/maximum to two
seconds, with explicit admission and physical timeout tests. This keeps the
existing bounded offline/error-retirement policy and serial byte timing.

### LG2 — Prove the C image, imports and entry bridge

- Add a focused C executable with initialized/BSS data, internal and imported
  calls, static object/string/function pointers, switch tables and return values.
- Implement the host packing/relocation proof and the generated import thunks.
  Compare reconstructed output with independent links at multiple legal bases;
  execute two concurrent copies at different upper addresses.
- Exercise C → native → C calls, blocking/yielding, signed return conversion,
  DP/register/bank/mode restoration and interrupt entry through the bridge.
- Run small raw/optimized C and native ABI probes. Freeze the container and
  document the supported compiler/runtime subset only after these pass.

Gate: private state and imports work away from link addresses, with preserved
native context and no changes to the Exec gateway or Task admission policy.

### LG3 — Integrate loading and cleanup with Program/Process

- Dispatch the C file profile through `PROGRAMFILE`/`PROGRAM`, reusing bounded
  reads, errors, upper allocations and Image reference ownership.
- Add the typed Process entry bridge, C startup/teardown and eager import
  binding. Keep native o65 loading on its existing ABI.
- Exercise fresh load, retained-instance restart, owner release while running,
  load/start failure, early application failure, collection and slot reuse.
- Cover incompatible ABI, missing import, bad fixup, truncated input and memory
  exhaustion at the loader boundary. Check a loaded native command still works.

Gate: repeated complete load/run/collect cycles restore the heap and ownership
baseline. A fresh load resets data/BSS; restarting a retained instance preserves
it, matching the existing Image semantics. Partial startup leaves no published
binding or leaked Process lease.

### LG4 — Make the counter the first disk application

- Build `COUNTER.APP` with a small `main` wrapper and application-owned model;
  retain its normal GEM event/redraw loop. Remove its body and model from the
  shared GUI component and its entry from the resident Task table.
- Start it as a loaded Process beside the shell and existing panel/browser.
  Replace parent reads of counter globals with Process/AES ownership and results.
- Close, collect and relaunch it without reboot. Check two private instances
  in a focused fixture with enough free windows/registrations, and continued
  shell operation while a counter is running or closing.

Gate: the same application file runs at different addresses; return, window
close and startup failure reclaim all per-instance resources after collection.

### LG5 — Migrate Control Panel and Files; finish launch ownership

- Package `PANEL.APP`, `FILES.APP` and the existing `DESKTOP.RSC`; remove the
  remaining application bodies, model globals and raw worker-Task startup.
- Have the existing desktop owner retain bounded Process identities for initial
  applications. Service their completion signals through the desktop shell's
  wait/service path so closing an app releases its lease even at an idle prompt.
  Do not add a polling timer or a reaper Task to compensate for missed completion.
- Extend the existing Files launcher to accept the C profile as well as native
  commands. Keep its one-child policy: Files owns and collects that child;
  closing Files requests child close/cancellation and waits for collection.
  Initial desktop apps remain owned by the desktop, independently of Files.
- Add cooperative GUI Stop/close by Process ownership. Preserve pending close
  messages during popup interaction. Support launching Files again from the
  shell after it closes, without introducing another application manager.
- Keep current Task, AES-registration and layer capacities. Reclaim retired
  initial applications before reuse; report ordinary capacity exhaustion when
  all slots are occupied. Closing an app must restore usable capacity.

Gate: the disk-loaded panel, counter, Files and shell coexist; close/relaunch and
exit with a live child complete without leaked images, registrations or Tasks.
Native HELLO/TICK launch and shell pipelines still work within existing limits.

### LG6 — Check the exact cartridge and disk package

- Build through `tools/build_demo.py`, including OF816, pinned AltirraOS ROM,
  notices, checksums and the normal five-second autoboot. Preserve the default
  shell/prime profile and ship boot assets only in `exec816-demo.zip`.
- Build the existing old/new Atarimax cartridge variants from the exact XEXs.
  Cold-boot them with the matching disk under the pinned VBXE configuration.
  Extend the desktop integration used by `tools/test_cartridge.py` for this case.
  Exercise the loaded desktop, physical button/keyboard interaction, window
  moves/close, launch/relaunch, native commands and orderly OS return.
- Run the host suite, affected generator checks and focused emitted regressions
  for loader, Process lifetime, C ABI and the changed desktop startup. Check
  both supported filesystems on the loading boundary without duplicating the
  entire desktop matrix. Record actual development scope and remaining limits.
- Publish current C loading/startup contracts, application build instructions
  and the revised demo guide. Remove obsolete resident-application build paths
  for migrated examples; retain focused fixtures where they test shared APIs.

Gate: both final XEXs fit the existing cartridge payload limit; report remaining
headroom and aim for at least 32 KiB, rather than hiding loader growth behind
compressed ZIP size. No application body is present in the cartridge or shared
GUI component. Repeated launches return heap/ownership counts to baseline.
Record startup cost and a bounded interaction comparison; this work neither
closes PI4/HY4 nor claims hardware/release qualification.

## Budget and principal risks

Every slice targets **0 additional fixed, per-public-Task and private-idle
bank-zero bytes**, including guards, alignment and unused reserved capacity.
Report those categories explicitly, plus existing pool stack high-water marks.
Upper memory may grow: report application backing padding, image/Process metadata,
shared-component reservations and peak staging. Keep all lifetime records there.

The main risks are the native-only bootstrap ordering, compiler relocation
assumptions, C/native stack restoration, and releasing an image before all GUI
references retire. LG1–LG3 isolate them before migrating every application.
If the bank-only relocation proof fails, resolve the unsupported construct or
revise the bounded format before proceeding; do not silently substitute fixed
per-application addresses or code that works only at the reference link base.

Disk loading trades cartridge occupancy for cold-start time and a required
system disk. Measure that tradeoff separately from steady-state GUI latency.
The hard capacity gate applies after adding the loader as well as before it.
