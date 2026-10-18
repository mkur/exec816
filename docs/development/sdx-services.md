# SDX MD5 service subset

P4 implements the fourteen MD5 imports and exercises them through source-audited
6502 commands loaded by P3's ordinary Process path. This is a **development**
result for the P4 slice. [M1](sdx-md5.md) subsequently admits the audited MD5
binary for named-file hashing; ARC remains unadmitted.

[Plan](../plans/spartados-personality-implementation-plan.md) ·
[Service contract](../reference/sdx-services.md) ·
[Execution record](sdx-services.json) ·
[Loader and Process record](sdx-loader.md)

## Implementation

Each Image's upper-heap Session owns two native file handles, ten guest error
traps, command/path scratch and a bounded output buffer. Services run on the
Process's native continuation after the bridge releases physical page one.
Ordinary DOS calls provide streams, blocking I/O and resource ownership.
`FCLOSEAL` and final cleanup consume only that Session's handles. Cleanup drains
all handles and preserves the first causal error, including terminal Close
failures after a native handle has been consumed.

`PRINTF` parses the inline format and pointer words in the private guest bank,
then advances the suspended return PC past the complete record. The admission
catalog classifies direct-page operands by their audited argument-word address.
Numeric pointer values alone never select bank zero. The probe deliberately
poisons the same offset in the upper bank and places the actual digest byte and
filename pointer in the guest direct page. A format crossing a low-byte boundary
checks continuation arithmetic. Redirected output preserves ATASCII bytes;
interactive output translates newline, backspace, tab and clear-screen controls
for the native console.

`U_SFAIL` records a guest handler and post-call stack pointer. After a native
operation settles, error delivery removes the newest trap, moves the complete
suspended frame to that saved stack, sets A/error and N, and resumes the handler.
Caught errors leave files open. Uncaught errors complete the ordinary Process
with primary result 20 and the native I/O cause, or the explicit SDX error byte
when no native error caused it. No native frame or outstanding I/O is abandoned.

## Executed scope

| Run | Passing checks |
| --- | ---: |
| Optimized guest services and console | 103 |
| Optimized terminal Close-error injection | 84 |
| Focused Session/frame ABI, raw and optimized | 44 each |
| Optimized concurrent Process regression | 72 |

The optimized guest-call probe covers all fourteen imports, two simultaneous
binary input streams, a third open failing, zero/high-bit bytes, partial reads,
EOF, owned close, nested traps and nonlocal stack unwind, trap capacity, register
preservation including hidden B, options/attributes, parsed `/H` rejection,
missing files and unsupported drives. It compares exact redirected output and
checks the native console's cells and cursor after translated controls.

The Close-error build uses an explicitly recorded test override: it performs
the real `DOS.Close`, then reports native error 221. This tests handle consumption,
all-handle cleanup and retention of an earlier error. It does not simulate an
unsettled device request. The override's hash is in the execution record.

A small raw/optimized probe checks the new Session record layout, packed far
handle pointers, trap array access and movement of every preserved frame byte.
It does not duplicate the complete Process scenario in raw mode. The optimized
P3 regression runs two independent guest Processes, output, owner unload,
collection, slot reuse and retained-Image relaunch with the P4 dispatcher.
All scenarios check platform/DP guards and recover their heap allocations.

```sh
python3 tools/test_sdx_services.py --output build/sdx-services/opt
python3 tools/test_sdx_services.py --close-error --output build/sdx-services/close-error
python3 tools/test_sdx_service_shape.py --case raw --output build/sdx-services/shape-raw
python3 tools/test_sdx_service_shape.py --case opt --output build/sdx-services/shape-opt
python3 tools/test_sdx_process.py --output build/sdx-services/process-regression
python3 tools/generate_sdx.py --check
python3 -m unittest discover -s tests -p 'test_sdx*.py'
```

These runs use the pinned dedicated AltirraOS 3.44 65816 ROM and Altirra 4.40
bridge/configuration recorded in the JSON. They do not extend the earlier P2
interrupt evidence or constitute full hosted-system qualification.

The 15 SDX host checks and generated-definition checks pass. The complete host
suite reports 507 passes, four skips and two pre-existing failures: the C package
test expects provider ABI 19 instead of 20, and the provider-contract test expects
1,807 payload bytes instead of 1,844. Neither failure involves the SDX changes.

## Memory and remaining scope

P4 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including guards,
alignment and spare capacity. The enabled personality still reserves P3's
544 fixed bank-zero bytes for two guarded guest direct pages, with no native
Task, root, kernel or idle growth. The resident upper bank and rounded private
bank allocations also retain P3's capacities. The Session requests 592 upper-heap
bytes, also 592 after heap alignment, compared with P3's rounded 16 bytes:
**576 additional upper-heap bytes per loaded Image**. This includes both handles,
all ten traps and unused buffer capacity. Native DOS objects are separately owned
by the normal DOS APIs.

The current drive policy maps guest `A:` and bare filenames to `RAM:` without
changing global assignments. Read-only opens, ordinary private-bank buffers,
the documented bounded formatter and command parser are supported. Directory
enumeration, writing/seeking, other drives, stack-pointer arguments, callbacks,
overlays and general hardware access remain unsupported. BREAK latency,
real MD5 digests and `/C`, and ARC operations belong to subsequent gates.
