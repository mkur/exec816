# Hosted message service

[Port overview](../README.md) · [Hosting contract](../../../docs/reference/gem-vdi.md)

The service implements private OPEN/SUBMIT/CLOSE/STOP/CURSOR transport using ordinary Exec
Tasks, messages, signals and removal leases. The test executable supplies an
explicit fixture backend. It links neither the GEM renderer nor VBXE drawing;
its workstation outputs are test values. This is a development integration
boundary, not a public GEM library or a graphics qualification.

## Build and validation

```sh
python3 tools/generate_calypsi.py --check
python3 tools/generate_gem_vdi.py --check
python3 tools/test_gem_vdi.py --slice g2 --mode raw
python3 tools/test_gem_vdi.py --slice g2 --mode opt
```

The [builder](../../../tools/build_gem_vdi.py) uses the shared checked C emission
and native packaging paths. It verifies emitted `sizeof`/`offsetof` constants for
every wire field and the public Task lease. Definitions, operation validation
and reply widths come from [gem-vdi.json](../../../abi/gem-vdi.json). G2 adds reply
width metadata in the original revision-1 layout. Current revision 2 preserves
those header offsets and adds the eight-byte CURSOR payload; old revisions fail.
Maps, manifests and
results remain under `build/gem-vdi/g2-{raw,opt}/`; the retained
[development record](../../../docs/development/gem-vdi-g2.json) includes the C
context and G1 control runs.

## Ownership and calls

Zero-initialize address-stable `GemServer` and `GemClient` records in upper RAM.
Register `GemServiceWorker` as a C Task entry in the containing image. Ordinary
C records and Task leases may have odd addresses; wire packets must be even.
The caller remains the sole client and stop supervisor for this service lifetime.
There is no public port registration, client discovery or unrelated application
attachment. Record fields are implementation state; callers must not copy or
alter live records except the packet fields prepared below.

| Call | Behavior |
| --- | --- |
| `GemServiceStart(server, backend)` | Retain the caller, admit and retain an ordinary 2,560-byte Task, initialize its private port/scratch, then publish readiness. The caller waits on a temporary signal. Failed admission/startup unwinds before returning. A fresh zeroed server begins a new service lifetime. |
| `GemClientInit(client, server)` | Allocate a private reply port and a 2,204-byte packet, retain the caller, then attach the one client. Reject a second attachment. |
| `GemPrepare(client, operation, count, payload_bytes)` | Reset the owned packet and fill its header. The caller fills command descriptors and inline arrays before submission. Payload bytes include the complete descriptor table. |
| `GemSubmit(client)` | Check placement/ownership, mark one request outstanding and publish it under Forbid. The packet stays immutable until collection, even if a reply has already arrived. |
| `GemCollect(client)` | Wait for and remove the exact reply before releasing outstanding ownership. Update local session/sequence state. An unexpected reply stays queued and storage remains retained. |
| `GemTryCollect(client, ready)` | Collect the exact pending reply without waiting. An empty queue returns OK with ready zero and leaves pending ownership/session/sequence unchanged. |
| `GemPrepareCursor(client, x, y, visible)` | Validate coordinates/visibility and prepare a 164-byte revision-2 request. Submit and collect through the same single-packet ownership path. |
| `GemOpen`, `GemCall`, `GemClose` | Synchronous helpers over prepare/submit/collect. `GemCall` copies borrowed input arrays into the packet before publication. All helpers return a status; `GemStatus` also exposes it for drawing calls corresponding to classic void VDI operations. |
| `GemServiceStop(server)` | Use the control request and reply port reserved by startup, withdraw submission under Forbid, enqueue STOP after accepted work and await retirement without allocation. The client's drawing reply remains its separate collection obligation. |
| `GemClientDispose(client)` | Reject outstanding work or an open live session. After close or service stop and exact collection, detach, free packet/port and release the client lease. |

Admit any computing peer with a 2,560-byte request before smaller workers can
consume the two large pools. The fixture admits the peer first, then the renderer;
neither pool is reserved for GEM. The worker validates its startup identity and
lease before touching the service, so an unrelated duplicate entry returns safely.

The service retains the caller and renderer throughout startup and operation.
The client has its own caller lease through disposal, including an uncollected
reply after STOP. All allocation and backend work occurs outside internal Forbid
sections. Readiness publication is a short Forbid section. Final lease release,
reply publication and renderer removal are indivisible under Forbid, using the
existing worker retirement protocol. No request is accessed after ReplyMsg.
Do not force client removal or free storage on a timeout.

## Validation and completion

Packets are at most 2,204 bytes in one upper CPU bank. The sender owns that full
capacity; `mn_Length` and `total_bytes` name the submitted extent within it.
The receiver independently checks that extent, revision, flags, command table,
offset alignment, empty-array rules and widened count arithmetic. Arrays must
follow the entire table; shared read-only input is accepted. A valid Exec Message
with fewer than 156 advertised bytes receives only an Exec reply, without writes
to unavailable service fields. The client wrapper rejects such short submissions.

The receiver validates every command before any backend call or sequence change.
Malformed or unsupported input leaves the session usable. It checks the exact
admitted packet and reply port as well as the live generation/next sequence.
OPEN is exclusive; stale generations never address a replacement session. The
last sequence is reserved for CLOSE, and generation wrap returns EXHAUSTED.
This is a shared-address-space ownership protocol, not memory isolation from
arbitrary invalid Exec Message or reply-port pointers.

Validated coordinates and integers are copied into service-owned scratch before
dispatch. G2 fences each command before adding it to the completed prefix or
publishing its setter output. This conservative rule also fences `v_updwk` and
batch completion; later batching must preserve truthful failure prefixes.
Command/fence failure retires the generation and closes the backend. STOP drains
accepted work, closes any live session, frees worker resources and acknowledges
only after releasing its removal hold. Submissions after withdrawal fail STOPPING.

The backend interface is synchronous and renderer-owned. It must not retain
borrowed descriptors, input/output pointers or request storage. Open failure must
roll back its own resources. Close must return only after quiescence and release;
an unquiesced hardware backend must take the controlled platform fault path
instead of returning. The backend also implements a synchronous cursor callback.
The [VBXE adapter](../adapter/README.md) supplies real display exclusion, bounded
waits, fences, recovery and cursor save/restore.

## Measured scope and memory

The historical G2 record covers 13 cases per mode: protocol/limits, queued and active stop, Task
admission, startup signal exhaustion, worker port/scratch exhaustion, client
port/packet exhaustion, stop port/packet exhaustion, and held renderer/client
removal. Protocol checks include no partial mutation, exact reply collection,
maximum payload/counts, short/raw headers, bad offsets/counts/values, stale
generation/sequence, command/fence failure prefixes, exhaustion and unauthorized
stop. Heap failures use actual exhausted public memory and verify rollback;
the two removal cases deliberately reach the native held-Task fault.

The normal cases restore heap ownership, signals, OS presentation and the
unmapped aperture sentinel. The protocol case observes real VBI in both C workers,
checks independent computing results, lower DP/callee-preserved registers and
all stack/domain guards. These are development checks on the pinned hosted
machine, not release qualification or concurrent disk-I/O evidence.
Calypsi still has no automatic function-entry stack checks; recorded watermarks
cover this fixture's call chains, not a worst-case hardware drawing bound.

Reserved bank-zero change relative to the larger-stack baseline is **fixed 0;
per public Task 0; idle 0**, including guards, alignment and unused capacity.
The C executable retains its checked `$0C` code and `$0D` data/BSS reservations
(131,072 upper-RAM bytes including slack), and its existing 20-byte lower-DP
workspace. Dynamic upper-RAM allocations are the 27-byte renderer port, 192-byte
scratch, 27-byte client port, 2,204-byte client packet and preallocated 27-byte stop
port/156-byte stop request. With the heap's eight-byte rounding, these occupy
2,656 bytes throughout the service/client lifetime, excluding allocator metadata
already reserved by Exec. Caller state and fixture data are in the recorded C BSS.
G2 reserves no VRAM. The standard OF816 demo is unchanged.

[Input implementation evidence](../../../docs/history/gem-input.md) records the
later allocation-free stop, nonblocking collection, revision-2 cursor and real
allocation/signal-exhaustion controls. The interactive application owns the
renderer and client; root has only disk/control responsibilities.
