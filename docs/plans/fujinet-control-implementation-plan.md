# FujiNet control implementation plan

[Plans index](README.md#device-io-and-sio) · [Roadmap](../roadmap.md) ·
[SIO contract](../reference/device-io.md#siodevice) ·
[User mounts](user-sio-mounts-implementation-plan.md) ·
[Platform contract](../reference/platform.md) ·
[Testing policy](../contributing/testing.md)

Status: FN0 implemented at the development tier; FN1–FN5 pending.
[Implementation record](../history/fujinet-control.md). Complete and commit each executable slice after its
focused development checks. The FASTEST125 timing investigation is separate;
FujiNet control starts at standard SIO speed.

## Outcome and scope

Add a loadable `C:FUJI` command that reports FujiNet status, lists configured
hosts and disk slots, browses a host directory, attaches an ATR to a drive slot
and ejects it. Use already configured SD/TNFS hosts; leave Wi-Fi setup and host
editing to FujiNet's existing configuration tools.

Keep image attachment separate from filesystem mounting:

```text
FUJI STATUS
FUJI HOSTS
FUJI DISKS
FUJI DIR HOST 1 PATH "/disks"
FUJI ATTACH D2: HOST 1 IMAGE "/disks/tools.atr"
MOUNT DATA: DRIVE 2 FORMAT MYDOS
DIR DATA:
UNMOUNT DATA:
FUJI EJECT D2:
```

Users select host slots 1–8 and drives D1–D8; convert to zero-based FujiNet
slots only at the protocol boundary. ATTACH defaults to read-only. Its optional
READWRITE controls the image's access; `MOUNT ... READWRITE` independently
requests filesystem writes. The filesystem still comes from the user, and
geometry still follows READ sector 1 → STATUS → PERCOM and cross-checking.

Reuse `sio.device`, its single bus worker, and the current block/filesystem
path. FujiNet command encoding belongs in the loadable client. Add no FujiNet
worker, resident `fujinet.device`, new kernel operation or alternate filesystem
implementation. Network streams, N: protocols, downloads, image creation,
host-table writes, firmware updates, reset, boot-slot management and automatic
speed negotiation are outside these slices.

## Protocol inputs

The initial source snapshots are FujiNet firmware
`b38796e0ea1950115b704b6f900dcd4f92193daa` and fujinet-lib
`dcca2eba2cdeadf1183a3a27223f536bb9f121d5`, inspected on 14 October 2026.
FN0 records immutable source URLs/hashes and the actual executable firmware
used by integration checks. Source compatibility does not establish hardware
qualification.

Control requests address `$70`; attached disks use the existing `$31–$38`
units. The official [control command reference](https://github.com/FujiNetWIFI/fujinet-firmware/wiki/SIO-Commands-for-Device-ID-%2470)
and pinned [command constants](https://github.com/FujiNetWIFI/fujinet-lib/blob/dcca2eba2cdeadf1183a3a27223f536bb9f121d5/include/fujinet-commands.h)
define the subset:

| Operation | Command | Direction and payload | AUX fields |
| --- | --- | --- | --- |
| Wi-Fi status | `$FA` | Read 1 byte | Zero |
| Adapter information | `$E8` | Read 140 bytes | Zero |
| Host slots | `$F4` | Read 256 bytes | Zero |
| Disk slots | `$F2` | Read 304 bytes | Zero |
| Mount host | `$F9` | None | AUX1 host |
| Open directory | `$F7` | Write 256 bytes | AUX1 host |
| Read directory entry | `$F6` | Read 255 bytes | AUX1 255, AUX2 zero |
| Close directory | `$F5` | None | Zero |
| Get image path | `$DA` | Read 256 bytes | AUX1 disk |
| Set image path | `$E2` | Write 256 bytes | AUX1 disk, AUX2 host/mode |
| Attach image | `$F8` | None | AUX1 disk, AUX2 mode |
| Eject image | `$E9` | None | AUX1 disk |

The [public layouts](https://github.com/FujiNetWIFI/fujinet-lib/blob/dcca2eba2cdeadf1183a3a27223f536bb9f121d5/include/fujinet-fuji.h)
give eight 32-byte host names and eight 38-byte disk records: host byte, mode
byte and 36-byte display filename. The disk table contains abbreviated names;
use GET_DEVICE_FULLPATH for a selected slot's complete path. Adapter information
contains fixed byte arrays; decode its fields explicitly rather than copying
a compiler's native struct layout.

The [Atari adapter](https://github.com/FujiNetWIFI/fujinet-firmware/blob/b38796e0ea1950115b704b6f900dcd4f92193daa/lib/device/sio/sioFuji.h)
packs SET_DEVICE_FULLPATH's AUX2 as `(host << 4) | mode`. Read-only mode is 1
and write mode is 2. The pinned [disk flags](https://github.com/FujiNetWIFI/fujinet-firmware/blob/b38796e0ea1950115b704b6f900dcd4f92193daa/lib/device/disk.h)
also define mounted bit `$40`; mask it off when interpreting access. Treat
unrecognized flags separately from access and do not infer live attachment
solely from a configured filename.

The pinned [firmware operations](https://github.com/FujiNetWIFI/fujinet-firmware/blob/b38796e0ea1950115b704b6f900dcd4f92193daa/lib/device/fujiDevice/fujiDevice.cpp)
use one open directory cursor, return `$7F,$7F` at directory end, and persist
slot changes during set-path/eject operations. These properties require control
exclusion and explicit reporting when attachment fails after configuration.

## Shared SIO changes

The current driver opens only disk units and admits up to 128 payload bytes,
plus selected 256-byte disk commands. FujiNet needs whole 256/304-byte frames;
splitting these into separate SIO transactions would change the protocol.

Add `$70` to unit admission and a reusable `SIO_PROFILE_STANDARD19200` profile:
POKEY divisor 40, payloads up to 512 bytes and an explicit/default timeout ceiling
of 15 seconds. This profile admits raw transactions on supported units without
knowing FujiNet opcodes. Keep legacy profiles' lengths, deadlines and disk
command restrictions. User filesystem mounts retain their existing profiles;
they do not acquire a new geometry or speed-selection policy.

Audit CARD-sized native counters, checksum loops, far-buffer increments and
deadline arithmetic before expanding admission. The current deadline conversion
is bounded for two seconds; extend its arithmetic to cover the new ceiling,
including tick wrap and upward rounding. Keep serial-byte timing, recovery,
offline-on-uncertain-error policy and IRQ/NMI ownership unchanged.

Add public `SIO_OPEN_EXCLUSIVE` OpenDevice flag semantics for every admitted
unit. Exclusive open requires zero existing opens; shared opens fail while an
exclusive binding exists. Return `IOERR_UNITBUSY` for either conflict. Borrowed
requests follow the existing binding lifetime, and exclusivity ends only after
all work has been collected and the binding closes. Use the driver's existing
protected admission/close boundary; never hold Forbid or IRQ exclusion across
wire activity.

Use the unused fourth byte of each four-byte DriverUnit for exclusivity. Put
the control unit at a checked spare offset, proposed `IS_BASE+240`, within the
existing 256-byte upper device metadata reservation. The eight disk records
end at +160, where the worker Task begins: do not append a ninth record there.
Generate/check unit offsets and extents together with the existing Task/name
reservations.

## Loadable command access

Native COMMAND imports currently expose DOS operations and the compiler's
CSTRING library, not Exec device I/O. Provide a small, reusable caller-context
`SIO` client interface backed by `lib/io/sioclient.act`:

```text
SIO.Open(unit, flags, session)       -> signed I/O error
SIO.Transfer(session, transaction)  -> signed I/O error, copied actual length
SIO.Close(session)
```

A caller-owned session holds its reply port and IOSIOReq. Open acquires these
resources and starts/joins the existing SIO driver when needed; partial failure
unwinds them. Transfer uses SendIO and exact reply collection with ordinary
Wait. Close requires no outstanding request and does not stop the shared driver.
Publish generated session/transaction layouts and signatures in a repository
ABI input. Keep actual port/request layouts internal to the session helper.

The helper can observe the current foreground BREAK scope while waiting. It
checks BREAK before submitting a frame, then collects a submitted frame before
returning. It never resets an active peripheral transaction just to interrupt
a command. Suppress repeated BREAK wakes after noticing cancellation, and let
the command stop at its next safe boundary. A standalone Task without a DOS
foreground scope uses the same transfer without that extra wake signal.

Publish these three ordinary library imports through the o65 provider mechanism.
Extend its explicit allowlist for this repository-owned library without changing
the compiler-owned CSTRING contract or adding compiler exceptions. Update the
program ABI/provider reservation and rebuild consumers together. No new COP
selector or DOS filesystem action is needed. Native clients and loadable Action!
commands are the first consumers; a separate C convenience binding can follow.

## Command behavior and media lifetime

Every FUJI invocation opens `$70` exclusively, including reports. Keep the
binding for the entire command so another client cannot replace the firmware's
directory cursor or interleave slot edits. An already open control binding
returns busy immediately; avoid a new lock service or waiting queue.

STATUS reports the adapter version, address and Wi-Fi state. HOSTS and DISKS
show copied configuration. A query occurs only when requested; boot does not
probe for FujiNet. Validate complete replies and bounded strings, retain raw
device/transport errors, and report command/phase/actual length on failure.

DIR mounts the selected configured host, opens the requested directory, streams
one bounded name per output row and closes the cursor on EOF, BREAK or output
failure. Send path plus an empty filter as two NUL-terminated strings inside
the zeroed 256-byte frame. Check the combined length before submission. Use
ordinary entry reads, no new directory block mode or full-directory snapshot.
Do not turn an ellipsized display name into an automatic image selection.

ATTACH and EJECT also open the target disk unit exclusively before any operation
that changes its image. An existing filesystem binding, pending I/O or another
raw client makes the unit busy. Keep this binding until the entire change ends;
new filesystem admissions then cannot open the drive during the change. An
observational mount-table query alone would leave a race. The caller must first
UNMOUNT every Exec volume backed by that unit, including a boot volume; normal
busy-unmount checks still apply. Reject reconfiguration of a drive supplying
this invocation's executable until its program file binding has been released.

ATTACH requires an empty configured target slot; changing images is explicitly
EJECT then ATTACH. Under both bindings:

1. Read disk slots and reject a configured target. Validate host, path and access.
2. Mount the selected host. A pending BREAK can stop before slot mutation.
3. Send SET_DEVICE_FULLPATH, then MOUNT_IMAGE with the same access mode.
4. Collect the result, release both bindings and report the drive/image/access.

Once set-path is submitted, finish the bounded attachment sequence even if BREAK
arrives. Successful final attachment wins over a late BREAK. The sequence is not
atomic in firmware: if set-path succeeds and image mounting fails, report that
the slot was configured but attachment failed. Do not claim rollback or start
unbounded compensation. A timeout can leave the result uncertain; retain that
fact and the driver's current bus state. EJECT likewise collects its submitted
mutation before reporting success or the causal error.

Neither command invokes DOS.MountVolume or UnmountVolume implicitly. A later
MOUNT performs fresh discovery and filesystem admission. Unmount retires the
old cache/binding before image replacement. External changes through FujiNet's
web UI, physical controls or another computer remain outside this exclusion;
users must unmount first. Keep configured host prefixes unchanged.

Control uses STANDARD19200. Attached disks use the profile chosen by MOUNT,
which must match the peripheral's configured disk speed. Do not change FujiNet's
HSIO index or retry at other rates. Standard-rate control can share the bus with
the existing disk profiles; validate switching between those request types.

## Executable slices

### FN0 protocol constants and integration fixture

Add `abi/fujinet.json` and generated protocol definitions for the selected
commands, byte layouts, slot conversion, modes and fixed payload sizes. Record
upstream provenance and firmware/peer pins under toolchain/development records.
Execute a small emitted pack/decode fixture: host/disk/adapter replies, AUX
packing, path limits, empty/invalid slots and directory EOF.

Provide a scripted `$70` peripheral at the emulator's serial integration
boundary for deterministic real-frame tests. Record any test-harness extension
as an emulator input; do not bypass emitted SIO code or put a fake FujiNet path
in the production driver. Confirm the runnable integration route before FN1.

### FN1 bounded raw frames and exclusive units

Implement the new profile, longer bounded deadlines, control unit and exclusive
opens in the existing SIO driver/generators. Run emitted read/write frames at
140, 255, 256, 304 and 512 bytes, including nonuniform checksums and far-bank
crossings. Reject 513 bytes and invalid deadlines before hardware starts.

Cover exclusive/shared conflicts on a disk and `$70`, reply collection before
release, reopen, shutdown and old disk/profile behavior. Check deadline rounding
and wrap, a long host-style completion, timeout/checksum/device errors and a
peer Task's progress. Assert that the bus remains serialized throughout.

### FN2 reusable client and native command imports

Implement the caller-owned SIO session, exact collection and cleanup. Publish
its generated interface through the ordinary program provider path. Verify small
raw/optimized layout/call probes, plus an optimized loaded command issuing a
real `$70` transaction. Cover partial allocation/open failure, BREAK before and
during a frame, causal error preservation, close/reopen and SIO-disabled builds.

### FN3 reports and directory browsing

Add `examples/commands/fuji.act` with STATUS, HOSTS, DISKS and DIR. Use ReadArgs,
selected output, standard return codes and bounded row writes. Reuse one
512-byte command-owned scratch buffer across all protocol replies and path
frames. Compile/install C:FUJI for standard and bitmap shells.

Exercise quoted paths, host/drive boundaries, malformed replies, directory EOF,
output redirection and failure, BREAK cleanup, busy control admission and no
FujiNet response. Check that neither reports nor DIR edits slot configuration.

### FN4 guarded image attachment and ejection

Add ATTACH/EJECT, empty-target admission and exclusive target-drive binding.
Check readonly defaults and matching read-write modes, busy mounted volumes,
in-flight filesystem binding acquisition, concurrent control clients, repeated
attach, failed host/path/image stages and late BREAK at each mutation boundary.
Assert that no image-changing frame is sent after local busy rejection.

Run ATTACH → MOUNT → read → UNMOUNT → EJECT → ATTACH different image → MOUNT.
Verify the second payload independently, not through a warm cache. Include one
persisted write/readback using READWRITE on both attachment and filesystem.

### FN5 combined workflow and development demos

Exercise selected MyDOS/SpartaDOS 128/256-byte images, disk/control profile
switching, a concurrent runnable Task and I/O on an unrelated drive. Retain
bounded failure, stack/domain guards, request ownership, unchanged readonly
media and final resource baselines. A real pinned FujiNet firmware walkthrough
with an SD or local TNFS host supplements the scripted peer; record its actual
scope separately from protocol-fixture evidence and physical qualification.

Update the shell guide, STORY.TXT, SIO/current client contracts, indexes and
roadmap. Refresh standard and VBXE development demos with `tools/build_demo.py`,
including OF816 and its five-second autoboot, matching commands/disks/ROM,
cartridges, notices and checksums. Keep network fixtures and build/test records
outside the distribution ZIP. Do not publish a GitHub release in these slices.

## Memory and validation budget

Target **zero added reserved bank-zero bytes**: fixed, per public Task and
private idle, including guards, alignment and unused capacity. Use the existing
worker, Task pools, native descriptor, device metadata and request machinery.
The extra unit fits existing upper metadata capacity; the exclusivity byte uses
existing record padding. Check these assumptions against emitted layouts.

Only shared client code and its provider entries are resident additions. Measure
their upper code size and full provider reservation, including padding; do not
assume the current 1,728-byte manifest reservation has sufficient space. The
512-byte scratch buffer, parsing/row storage, two sessions, ports and requests
belong to the loaded command's lifetime. Report live/allocated upper bytes and
stack peaks as well as reservation deltas for every implementation slice.

Use development-tier checks: host protocol/admission cases, changed generators,
focused emitted behavior and small raw/optimized ABI probes where required.
Pin inputs through the current compiler/platform records. Full release matrices,
FASTEST125 acceptance, broad firmware compatibility and physical hardware
qualification remain separate activities. For this plan-only change, run content
and local link/anchor checks without building or running the hosted system.
