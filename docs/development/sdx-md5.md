# MD5 on the SDX personality

M1/M2 pass development checks with the pinned 6502 SDX 4.50 `MD5.COM` running
as an ordinary Exec Process. [Manifest](../../compat/sdx/md5-450.json),
[instruction audit](sdx-md5-audit.json), [M1 record](sdx-md5-m1.json),
[M2 record](sdx-md5-m2.json),
and [service contract](../reference/sdx-services.md) describe the admitted input
and scope. [ARC listing](sdx-arc.md) is a separate development slice. These checks are not full hosted-system
qualification.

## M1 named-file hashing

The audit walks 1,141 reachable instructions, including the error continuation,
inline PRINTF records, and every target of the four self-modified branches.
All executable writes change operands; sixteen message reads modify absolute
addresses and PRINTF selects digest bytes through its audited DP argument site.
The sole SEI is patched to NOP with balanced PHP/PLP. Hardware `/H` is rejected
by option parsing. Private MEMLO/MEMTOP give MD5 a 39,936-byte read buffer; its
OS variables never alias host bank zero. Normal `U_FAIL 0` completes successfully.

The optimized RAM run passes **987 checks**: empty input, `abc`, lengths
55/56/63/64/65, all byte values, 39,935/39,936/39,937, 65,535/65,536/65,537 and
131,073 bytes, plus `RAM:MD5 DATA.BIN >RAM:SHELL.OUT` through the ordinary shell.
Digests and exact ATASCII output agree with independent host MD5. Process
results are captured directly. Every run closes handles, releases its Image,
recovers the heap and checks guards.

A separate **192-check** run reads empty, `abc` and 65,537-byte files from a real
SDFS disk, created by the independent pinned Altirra producer. It uses native
SIO profile 4 with the matching `generic56k` disk model, accurate timing, SIO
patching off, and the pinned dedicated AltirraOS 3.44 65816 ROM. The record pins
the ROM, emulator configuration and emitted build. There were 17,585 native
IRQs during this run; the RAM run had 1,514 NMIs and 1,693 switches.

Reproduce with the privately obtained, pinned inputs under `build/sdx-inputs/md5`:

```sh
python3 tools/test_sdx_md5_exec.py --shell --output build/sdx-md5-exec/vectors-shell
python3 tools/test_sdx_md5_exec.py --disk --output build/sdx-md5-exec/sdfs
python3 tools/sdx_md5_audit.py build/sdx-inputs/md5/MD5.COM --output build/sdx-md5/audit.json
```

Builds explicitly enable `sdx=True` (CLI `--sdx`). Guest `A:` defaults to `RAM:`;
`sdx_drive_a` / `--sdx-drive-a` selects an immutable native volume/directory root.
This does not install global assignments. The standard demo is unchanged and
the SDX binaries are not redistributed. M2 adds verification, masks/attributes,
BREAK, concurrent real guests and failure recovery, described below.

M1 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including guards,
alignment and spare capacity. The enabled personality retains P3's 544-byte
guarded DP pool and 64 KiB upper resident reservation. The Session stays at
592 upper-heap bytes; private-bank allocation capacity is unchanged. The shell
test reserves 7,424 upper static bytes instead of the default 4,096 to include
its ordinary shell implementation; this adds no bank-zero reservation.


## M2 verification, selection and cancellation

M2 adds first-match 8.3 masks and P/H/A selection through ordinary DOS
Lock/Examine/ExNext, including real SDFS metadata. `FIBF_HIDDEN` and
`FIBF_ARCHIVE` expose existing disk attributes to any native caller; the FIB
layout and gateway are unchanged. `+S` raw directory reads remain unsupported.
NUL-terminated verification filenames and EOL-terminated command filenames both
work. Multiple command specifications remain distinct; a wildcard opens the
first matching file, as SDX FOPEN does.

GNU and BSD checksum lists accept LF, CR/LF, ATASCII and final unterminated
records. A mismatch prints inverse-ATASCII `BAD` and returns success, matching
the binary's behavior. Missing files return primary 20 with native cause 205;
overlong records return primary 20/SDX 137. Native read/write failures retain
their cause through MD5's cleanup/rethrow; a later Close error cannot replace it.
An explicit different guest error replaces that cause; successful new input
clears it. A separate guest-call regression checks all three cases.
Redirected output preserves bytes. Hardware `/H` and unknown options fail before
their effect.

The original binary has an unbalanced-PHP path for a line beginning with hex
but containing an invalid digit. The original-SDX extended control reached
repeated system errors after that malformed input. Four checked edits repair
this without changing valid digest parsing: EOF returns through the existing
RTS, with final FCLOSEAL responsible for the checksum handle; its former
three-byte tail becomes PLP/BRA to the next-record loop; both invalid-nibble
branches select that tail. The latter branch has exactly -128 displacement.
The patch explicitly removes the overwritten FCLOSE relocation after native
loading. The original-SDX repaired control rewrites that relocation record in a
disposable copy and independently compares placed images at two bases.

The compression checkpoint replaces the private OS BREAK poll after each
64-byte block. It uses a private veneer, outside the SDX import namespace,
and preserves registers/status. The owning Process's cancellation is latched
before entry and at native boundaries. I/O settles before trap delivery;
a caught BREAK may only close/remove traps/exit, within a bounded number of
cleanup calls. It cannot retry computation or turn cancellation into success.

Tests inspect a suspended compression PC, an active native SDFS Read and a
blocked Write to a full native pipe, then call `PROCESS.RequestBreak`.
They also request cancellation before guest entry. Each case checks the Process
result 20/304, consumed handles, released slot, guards, recovered heap and a
subsequent ordinary shell command. Test inspection never modifies guest bytes.
The recorded timing is specific to the pinned 800XL PAL 65816 x8 machine,
AltirraOS ROM, generic56k SIO model and workload; it is not a universal bound
for arbitrary devices or scheduler load.

The fixed and per-native-Task reserved bank-zero deltas are both **0 bytes**,
including guards, alignment and spare capacity. M2 grows each loaded Image's
upper Session from 592 to **864 bytes** (also 864 rounded): **272 extra bytes**
for the persistent public FIB and pattern scratch. Existing private-bank,
resident-bank and DP-pool capacities are unchanged. The acceptance harness
uses an 8,192-byte upper static arena to include its shell and observations.

Reproduce the focused M2 development checks with:

```sh
python3 tools/test_sdx_md5_acceptance.py --output build/sdx-md5-m2/acceptance
python3 tools/test_sdx_md5_acceptance.py --attributes --output build/sdx-md5-m2/attributes
python3 tools/test_sdx_md5_acceptance.py --breaks --output build/sdx-md5-m2/breaks
python3 tools/test_sdx_md5_faults.py --case read-close --output build/sdx-md5-m2/read-close
python3 tools/test_sdx_md5_faults.py --case write --output build/sdx-md5-m2/write
python3 tools/test_sdx_md5_faults.py --case close --output build/sdx-md5-m2/close
python3 tools/test_sdx_md5_faults.py --case partial --output build/sdx-md5-m2/partial
python3 tools/test_sdx_service_shape.py --case raw --output build/sdx-md5-m2/shape-raw
python3 tools/test_sdx_service_shape.py --case opt --output build/sdx-md5-m2/shape-opt
python3 tools/test_sdx_md5.py --group edge-reference --inputs build/sdx-inputs/md5 --output build/sdx-md5-m2/reference-edges
python3 tools/test_sdx_md5.py --group malformed-reference-patched --inputs build/sdx-inputs/md5 --output build/sdx-md5-m2/reference-repaired
```

Fault builds record local test overrides: they complete the actual native
operation before reporting an error, or request one-byte transfers. No pending
I/O is discarded. Raw/optimized checks cover the small Session/frame shape;
full application scenarios use optimized emitted machine code. Original-SDX
controls capture output bytes, not shell exit codes; native Process results are
asserted directly and are never inferred from output.

### Executed development scope

The [M2 execution record](sdx-md5-m2.json) pins each emitted build and its
results. The main checks passed:

| Scenario | Checks |
| --- | ---: |
| 25 command/list/error cases, shell recovery and two concurrent MD5 Processes | 2,223 |
| Full digest matrix, explicit all-256-byte vector and shell redirection | 1,052 |
| Real SDFS P/H/A attributes and masks | 1,347 |
| BREAK before entry, during compression, Read and blocked output | 306 |
| Native read plus Close failure, write failure, terminal Close failure | 30 each |
| One-byte native reads/writes | 136 |
| Guest services, console and caught-error/rethrow policy | 121 |
| Session/frame ABI, raw and optimized | 44 each |

All runs check guards and resource recovery. The concurrent run records 347
native-peer iterations. The malformed-list case places 48 invalid high/low
hex records between two valid records and verifies both results exactly.
The BREAK run observes actual suspended phases, returns primary 20/secondary
304, and measures three PAL frames (about 60 ms) from request to Process
collection in each case. This includes native cleanup, not just guest dispatch.

The unmodified original-SDX edge control passes 16 commands. A wider original
control produced all 15 expected digest vectors before timing out on malformed
hex; those completed outputs were independently checked, and the timeout is
retained as a failure in the record. The repaired original-SDX control passes
18 commands, including both malformed-record cases, without the Exec checkpoint.
This establishes the malformed-input repair separately from native services.

The 64-byte checkpoint has a measurable cost. On the matched RAM digest/shell
matrix before adding the explicit all-byte vector, M1 used 1,514 NMIs and 20,453
gateway calls; M2 used 2,613 and 32,371. At PAL cadence that is approximately
30.28 versus 52.26 emulated seconds for the entire harness. This includes native
filename enumeration and setup; it does not isolate compression or checkpoint
cost. The final expanded matrix uses 2,659 NMIs and 33,863 gateway calls.

The 15 SDX host checks and SDX/DOS/C generators pass. The full host suite reports
507 passes, four skips and the same two pre-existing failures recorded for P4
(provider ABI 19 versus 20; payload 1,807 versus 1,844 bytes). Functional scenarios
are optimized; only the focused ABI shape probe also runs raw. Component runs
preceding the malformed-record repair retain their build hashes, and the final
error-policy correction has focused guest-service, read/Close and BREAK reruns.
No full hosted qualification matrix was run.
