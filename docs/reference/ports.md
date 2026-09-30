# Messages and ports

[Reference index](README.md) · [Message-passing example](../guides/messages.md)

A port is a FIFO queue of caller-supplied Message records. Sending passes a
reference; it does not copy a payload, allocate memory, create a Task or wait
for a reply. Signals announce possible activity; queue entries retain the work.

## Records and storage

`MsgPort` embeds a Node for the public registry and a separate List for queued
messages. `Message` embeds its queue Node, reply-port pointer and `mn_Length`.
Use the generated [port declarations](../../lib/exec/exec-port-types.inc) for
layouts. They retain Amiga field names but use native pointers and are not
Amiga binary layouts.

Set `mn_Length` to the complete inline descriptor size including its header. It
is a CARD, not a payload copy count. Large payloads belong in separate buffers
referenced by the descriptor. Initialized ports and linked messages cannot be
moved: their links contain addresses.

`PA_SIGNAL` posts `mp_SigBit` to the live `mp_SigTask`; the bit is a number, not a
mask, and must belong to the owner. `PA_IGNORE` queues without notification.
Software-interrupt ports and other flag combinations are unsupported.

## Calls and queue semantics

All calls belong to `EXEC` and are Task-context operations.

| Call | Contract |
| --- | --- |
| `PutMsg(port, message)` | Set `NT_MESSAGE`, append at the tail and perform the arrival action. |
| `GetMsg(port)` | Remove the head or return `NULL`; preserve its message type and application fields. |
| `ReplyMsg(message)` | Set `NT_REPLYMSG` and enqueue at `mn_ReplyPort`. With no reply port, set `NT_FREEMSG` without freeing storage. |
| `WaitPort(port)` | Wait for a nonempty port and return its head **without removing it**. Only its PA_SIGNAL owner may wait. |
| `CreateMsgPort()` | Allocate a private PA_SIGNAL port and caller-owned signal; return `NULL` on exhaustion. |
| `DeleteMsgPort(port)` | Release a created port and signal; `NULL` is harmless. Require an empty, quiescent, unregistered port. |
| `AddPort(port)` | Initialize an inactive port's queue and insert its node into the public registry in priority order. |
| `RemPort(port)` | Unlink a registered port; do not free it or revoke existing pointers. |
| `FindPort(name)` | Return the first exact, case-sensitive name match or `NULL`. Hold Forbid across lookup and immediate use. |

AddPort is not for a port with pending messages: it initializes the queue.
Queue order remains FIFO regardless of message priority. Only DeleteMsgPort
accepts a null port argument; a null message or FindPort name is misuse.

## Publication and completion

Initialize an unlinked message, its length, reply port and body before PutMsg.
Once published, retain its descriptor and borrowed payload until the matching
reply is removed. The receiver may run and reply before PutMsg returns. Likewise,
a sender may free a replied record before ReplyMsg returns; the receiver must
stop touching it as the reply is published.

A message can be on only one intrusive list at a time. Remove it before placing
it on a worker's private queue; detach it there before replying or forwarding.
Stale links and node types are not membership tests. Observing NT_REPLYMSG is
not enough to reclaim a request still linked at the reply port.

GetMsg neither replies nor clears the signal bit. Do not reply again to a reply.
A one-way message with no reply port needs its own lifetime agreement;
NT_FREEMSG is not a storage-release or safe polling protocol.

## Waiting and shutdown

Check the queue before waiting, then drain messages after waking. WaitPort does
this check/wait loop; it does not reserve the returned message against another
consumer. Use one waiting owner per port. Signals can be stale or coalesced;
queue contents decide whether work exists.

Stop producers, collect outstanding replies and withdraw public discovery before
deleting a port or freeing its signal. RemPort alone does not invalidate pointers
already handed out. DeleteMsgPort only frees ports created by CreateMsgPort;
caller-prepared static ports keep caller-owned storage and signals.

For device completion use the additional [I/O request contract](device-io.md).
The [historical design](../history/messages-ports-design.md) retains the original
layout probes, implementation sequence and synchronization rationale.
