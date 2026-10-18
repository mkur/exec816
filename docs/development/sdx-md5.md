# MD5 on the SDX personality

M1 passes development checks with the pinned 6502 SDX 4.50 `MD5.COM` running
as an ordinary Exec Process. [Manifest](../../compat/sdx/md5-450.json),
[instruction audit](sdx-md5-audit.json), [execution record](sdx-md5-m1.json),
and [service contract](../reference/sdx-services.md) describe the admitted input
and scope. ARC remains unadmitted. These checks are not full hosted-system
qualification.

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
the SDX binaries are not redistributed. M2 covers verification, masks/attributes,
BREAK, concurrent real guests and failure recovery.

M1 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including guards,
alignment and spare capacity. The enabled personality retains P3's 544-byte
guarded DP pool and 64 KiB upper resident reservation. The Session stays at
592 upper-heap bytes; private-bank allocation capacity is unchanged. The shell
test reserves 7,424 upper static bytes instead of the default 4,096 to include
its ordinary shell implementation; this adds no bank-zero reservation.
