# ARC on the SDX personality

A1–A4 admit the pinned 6502 SDX 4.50 `ARC.COM` and its three overlays for listing, extraction and archive mutation as
ordinary Exec Processes. [Manifest](../../compat/sdx/arc-450.json),
[plan](../plans/spartados-personality-implementation-plan.md),
[service contract](../reference/sdx-services.md) and
[execution records](sdx-arc-a4.json) define the development scope. This is not
full hosted-system qualification.

## A1 loading and listing

`L archive [mask ...]` and `V archive [mask ...]` execute the original command
and listing overlay, with the checked six-inline-byte helper patch. `N` and `W`
are the only additional admitted flags. Hardware `H` is rejected before entry.
Guest A: maps to the immutable `sdx_drive_a` root; CAR: maps to
`sdx_car_root` (both default RAM:). CAR: accepts only the exact admitted overlay
name and verifies its original size/CRC32 before relocation and execution.
No binaries are redistributed and no global assignments are changed.

The loader accepts caller-owned import bindings. Each Image supplies its own
`_ARC` export, rather than a global current-parent pointer. One overlay runs
synchronously above the main image at $4A6C; its frame and trap level are
retired before returning to the main command. All overlay-owned native handles
are closed on return and the overlay extent is cleared. Native file loading
and waits release physical page one through the existing service bridge.

COMTAB is private guest address $1000. ARC's arithmetic workspace extends through
COMTAB+$10A; the old $0600 placement collided with FILE_P and the kernel entry.
Ordinary pointers select the private bank. Audited header reads and inline
PRINTF operand sites select the private direct page; strings cannot cross its
256-byte boundary. The formatter admits ARC's 587-byte help record structurally,
although help execution is not yet admitted. The sole VPRINTF callback is the
pinned main module's single RTS leaf: the adapter consumes its format and emits
nothing, matching that leaf. General callbacks remain unsupported.

`__MISC` was traced in the original SDX cartridge at $BF4E. A=1 reads DAYTIME;
with the variable absent, it returns A=$9A, X=$FE, Y=$9B. ARC tests X to choose
day/month and 24-hour output. The personality freezes that policy and the
40-column console width, matching the original control. DIV_32's zero divisor
produces zero with carry, which preserves ARC's 100% display for empty entries.

`tools/sdx_arc_audit.py` verifies the frozen inputs and walks reachable code,
skipping inline records and following the main export table and trap entries.
It inventories 704 main, 244 listing, 488 extraction and 1,471 addition
instructions. None of those decoded instructions is SEI. The extraction inventory includes both targets of each mutable LZW code/output
vector. The A3 section below records addition admission.

The optimized A1 run covers L/V, masks, an empty member, missing/corrupt overlays
and subsequent recovery. Four outputs match original SDX byte for byte. Every
Process result is checked; the original control records output but does not
capture an exit code. Native cleanup checks handle/trap retirement, guards and
heap recovery. Small raw/optimized shape probes cover the shared ABI; the
loader probe exercises two private parent bindings with nonzero import addends.
MD5 and the existing service suite provide regressions. Full run artifacts stay
under `build/sdx-arc/`.

```sh
python3 tools/test_sdx_arc.py --group reference --output build/sdx-arc/reference
python3 tools/test_sdx_arc.py --group a1 --output build/sdx-arc/a1-final
python3 tools/sdx_arc_audit.py --help
```

A1 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including guards,
alignment and unused capacity. The enabled profile retains its 544-byte guarded
DP pool. Each Image's upper Session grows by **32 bytes**, from 864 to **896**.
The private 64 KiB guest bank still uses 131,072 backing bytes; resident upper
capacity is unchanged. Listing load temporarily stages 1,999 bytes plus the
ordinary loader layout and its 8,192-byte relocation bitmap. The test program's
12,288-byte upper static arena is test-only.

## File-date dependency

`DOS.SetFileDate` is implemented as a public reusable path operation, following
Amiga semantics. Its [write contract](../reference/filesystem-writes.md) covers
ownership and representable dates. The [execution record](dos-file-date.json)
contains 15 raw RAM checks and 26 optimized RAM/SDFS checks: public argument
marshalling, exact dates, live-lock rejection, invalid values, missing paths,
heap/guard retirement and independent persisted timestamp bytes. The 47 DOS
host tests pass. Fixed and per-Task reserved bank-zero growth are both zero.
The test-only upper static arena is 4,096 bytes.

```sh
python3 tools/test_dos_file_date.py --raw --output build/sdx-arc/file-date-raw
python3 tools/test_dos_file_date.py --output build/sdx-arc/file-date-opt
```

## A2 extraction

`X archive [mask ...]` and its `E` synonym now run the original extraction
overlay. Supported methods are old/new stored (1/2), RLE (3), Huffman plus RLE
(4), 12-bit LZW plus RLE (8), and SDX LZW (15). Method 15 uses a 16-bit byte sum;
the others use ARC CRC-16. The independent host fixture writer/reader and original
SDX cartridge controls agree on all six methods. The original algorithms run
inside the guest; the adapter does not implement a decompressor.

Native output uses owned handles, bounded writes and public SetFileDate after
successful Close. A captured timestamp must be representable before output is
opened. Output cannot exceed the member's declared length. A short header,
packed extent beyond the archive, inconsistent stored length or unsupported
method fails before the member is opened. These checks are not a sandbox or a
general malformed-compressor-stream validator. Member names are bounded 8.3
leaves; directory/path members, hardware H, encryption G and P/T are excluded.

Overwrite Y/N/A is read from ordinary Process input. W skips prompts and
suppresses warnings, as the original binary does. A CRC mismatch prints a
warning without changing the original zero exit status; a native I/O failure
still returns primary 20 and its first native cause. Failed/BREAK extraction can
leave a partial member; the input archive is unchanged. No successful completion
or timestamp preservation is claimed for that partial output.

The [A2 record](sdx-arc-a2.json) contains **525 optimized RAM checks**: all codecs,
empty/binary/multiple members, 65,537-byte streaming, overwrite decline/accept,
CRC output, truncation/length/method rejection, missing/corrupt overlays, locked
targets and subsequent listing. It adds three **33-check native SDFS runs**:
normal persistence, real full media and BREAK after the first output-write
service. Independent directory/file read-back verifies bytes and timestamps.
Full media reports IoErr 221 with a valid 37,120-byte prefix; BREAK reports 304
with a zero-byte partial member. The BREAK run observed 15 PAL ticks (300 ms)
between request and retirement using the test's byte RTC counter; this is an
observation on the pinned configuration, not a universal latency guarantee.
The normal run saw 45,739 native IRQs. Small raw/optimized ABI probes each pass
44 checks. All 15 SDX host tests pass.

A2 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including guards,
alignment and spare capacity. Each upper Image Session grows **560 bytes**, to
**1,456**, including the private directory FIB, captured output pathname/date,
length ownership and handle-size table. The extraction overlay reaches $9438,
inside the same private bank; staging needs 1,912 bytes, below A1's 1,999-byte
maximum. Existing guest-bank backing and resident capacities are unchanged.
The expanded test reserves a 16,384-byte upper static arena only.

```sh
python3 tools/test_sdx_arc.py --group reference-extract --output build/sdx-arc/reference-extract
python3 tools/test_sdx_arc.py --group a2 --output build/sdx-arc/a2-final
python3 tools/test_sdx_arc_disk.py --output build/sdx-arc/a2-sdfs
```


A3's reusable [exclusive-open dependency](dos-exclusive-open.json) passes 17 raw
RAM and 31 optimized RAM/SDFS checks. `MODE_CREATE_EXCLUSIVE` reserves a new name
atomically; `MODE_UPDATE_EXISTING` retains the existing archive as an exclusive
writer without truncating or creating it. Both have zero bank-zero growth.

## A3 creation and mutation

`A archive files...` creates an archive or adds/replaces selected members.
`D archive masks...` deletes selected members. `U` adds missing members and
replaces older ones; `F` replaces older existing members only. `B` retains the
old archive as `.BAK`; `N` and `W` keep the original message policy. Update and
freshen require known source/member dates: an unspecified zero date is rejected,
not treated as an invented timestamp. Newly written headers retain the source
date. Ordinary `A` chooses stored, RLE or LZW output in the original compressor.

ARCADD receives two checked patches. `STA $00AB,Y` becomes `TYX / STA $AB,X`
at its audited filename terminator; X and NZ are dead there. Its `MUL_32+2`
call receives a separate veneer, because entering the middle of the ordinary
service veneer is invalid. Original-library probes establish the Y=8 operation:
the top byte of the first operand times the 24-bit second operand, with the
original register/flag results. The generator now preserves import addends in
patch preimages. The overlay's MEMLO includes its entire BSS before execution.

The original archive opens with the public exclusive-writer mode without
truncation. The new `.XAR` uses atomic create-exclusive. A pre-existing `.XAR`
or `.BAK` is a collision, including with `B`; the adapter never adopts or removes
an unrelated file. ARC closes the completed temporary before replacement. The
adapter stages the original under `.BAK`, then renames the owned temporary to
the original name. That final rename is the replacement point. Without `B`,
the owned backup is deleted after publication. With `B`, it remains for the user;
move or remove it before another mutation of that archive.

Every error after temporary ownership is terminal, after native I/O settles.
This prevents ARC's header recovery from interpreting a read failure as a valid
end marker and publishing incomplete work. Native Close/rollback preserves the
first cause. A failed final rename restores the staged original and removes the
owned temporary. BREAK also retires the guest first; only then does native
cleanup acknowledge the signal to permit rollback, retaining Process result
20/304. There is no guest resumption after that acknowledgement.

Replacement spans several native namespace operations and is not atomic against
power loss or independent native namespace operations. If rollback or deletion
itself fails, a recoverable `.BAK`/`.XAR` can remain; the original causal error
wins and a later invocation rejects the collision. These limits follow the
[native write contract](../reference/filesystem-writes.md), not an emulated
transaction guarantee.

The [A3 record](sdx-arc-a3.json) contains **383 final RAM checks**, including byte-for-byte creation against
original SDX, independent decoding/CRC and header dates, add/delete, backup
contents, older/newer update and freshen, unknown-date rejection, native lease
conflict, unrelated temporary/backup collisions, missing/corrupt ARCADD and
recovery. **174 injected-failure checks** cover read, a committed one-byte short
write, seek, late Close and final rename after staging. Each preserves the
original archive, retires all handles and removes the owned temporary. Raw and
optimized layout/frame probes each pass **44 checks**.

Native SDFS runs add **46 normal**, **35 full-media**, **35 BREAK** and
**35 protected-archive checks**. Independent file/directory read-back verifies
archive contents, header dates, protected source preservation, unchanged original
and filler after full media, and absence of owned temporary/backup files. BREAK
observed **62 PAL ticks (1.24 seconds)** from request to settled retirement,
using a stable 16-bit RTC sample. This is a measured case, not a universal bound.
The full-media run saw 14,441 native IRQs. MD5's **136 checks**, extraction's
**525 checks** and **15 SDX host tests** also pass.

The pinned original `AS` control leaves `NEW.XAR` and never publishes `NEW.ARC`.
Its store-only branch restores an output position before the corresponding save.
`S` therefore remains rejected before guest entry. This observation applies to
the pinned binary/configuration; ordinary `A` still produces stored members.
Move `M`, encryption `G`, hardware `H`, print/test `P`/`T`, arbitrary overlays
and unreviewed binary versions also remain unsupported.

A3 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including guards,
alignment and unused capacity. The enabled DP pool remains **544 bytes**.
The upper Session grows **792 bytes**, from 1,456 to **2,248**, including four
ARC handle slots, sizes, flags and three 256-byte ownership paths. This is already
8-byte heap aligned. MD5 still admits two handles. ARCADD ends at **$AA76**,
leaving **13,706 bytes** before the guest limit $E000 for its workspace. Its
4,646-byte staging request reserves **4,648 bytes**, alongside the ordinary
loader layout and 8,192-byte relocation bitmap. Guest backing, context storage
and native Task reservations are unchanged. The large 32,768-byte static arena
in the mutation fixtures is test-only.

```sh
python3 tools/test_sdx_arc.py --group reference-create --output build/sdx-arc/reference-create
python3 tools/test_sdx_arc.py --group reference-store --output build/sdx-arc/reference-store
python3 tools/test_sdx_arc_mutate.py --output build/sdx-arc/a3-final
python3 tools/test_sdx_arc_faults.py --output build/sdx-arc/a3-faults
python3 tools/test_sdx_arc_mutate_disk.py --output build/sdx-arc/a3-sdfs
```


## A4 coexistence and supported subset

The [A4 record](sdx-arc-a4.json) contains **156 mixed-use checks** through emitted
optimized code. MD5 hashes while ARC creates; two ARC Processes create separate
archives; a cancelled ARC preserves its original while the other ARC completes;
and a second mutator of a live archive receives native error 202. A native
compute Process deliberately never yields. Its counter advances in every pair.
Independent disk read-back decodes every resulting archive, verifies source files
and MD5 output, and checks that no temporary or backup remains.

The same fixture then launches ARC through the ordinary shell, redirects output,
checks a rejected command, successfully retries the cancelled mutation, lists
its contents and restores the prompt and console streams. Private banks, DPs,
parent-export records, handles, traps and overlay retirement are checked. Heap,
Task stack/domain guards and bank ownership return to their expected state.
This tests ordinary command dispatch and explicit prompt advancement; it is not
a physical-keyboard or complete desktop qualification.

Coexistence exposed a directory-cookie race: deleting one command's temporary
could invalidate another command's exact-name scan. Exact FOPEN/FFIRST now use
native Lock/Examine, retaining a file lock for a live exact search. An empty
exact search still owns a guest slot until FCLOSE. Wildcards retain native
ExNext semantics: concurrent directory mutation can return 202 and require a
retry. There is no hidden snapshot or suppressed filesystem error.

The expanded mutation/name/date run passes **485 checks**, including empty exact
search retirement, pre-1980 source rejection and unknown/future/invalid-month,
non-leap-day and invalid-time header rejection before U/F comparison. The
**1,350-check MD5 attribute regression** covers exact names, wildcard padding,
P/H/A selection and shell recovery on unchanged SDFS media. **15 SDX host tests**
and generated-definition/link checks pass. Date guards add no persistent state.

### Measured configuration and limits

The machine is the pinned **800XL, PAL, 65C816 ×8, 63 upper banks**, BASIC off,
shadow ROM enabled, with dedicated **AltirraOS 3.44 for 65C816**. ROM SHA-256:
`85a6e927038f401f05f0056fd41a062986cbf7e104c1ac135c248764c132c9a7`.
The emulator is Altirra 4.40 bridge revision
`52c18c89e354290199d6f1bbd98eb5048849b15c`, SHA-256
`6c5a1ee6699bfb6ac1e6f87495876faa5cf2286b3b03407e77ffd146c119cdb8`.
The complete [pin](../../toolchain/altirra-shell-paced.json) and each record's
actual configuration accompany the results. Native disk cases use writable
1,024 × 256-byte SDFS, **profile 4 / generic56k**, accurate disk timing, SIO patch
off, burst off and random delay off. Original SDX controls use `fastest`.

| Mixed command pair | Observed PAL ticks | Seconds |
| --- | ---: | ---: |
| ARC plus MD5 | 674 | 13.48 |
| Two ARC creations | 1,269 | 25.38 |
| Cancelled ARC plus successful ARC | 905 | 18.10 |
| Shared-archive rejection plus successful owner | 717 | 14.34 |

Pair timing starts before launching the Processes and ends after collecting both;
initial Image loading is outside that interval. BREAK-to-retirement observed
**199 ticks / 3.98 seconds** under concurrent disk/compute load; the fixture's
cutoff is **250 ticks / 5 seconds**. Its total completion cutoff is 24,000 PAL
frames / 480 seconds. These are measured cases and test cutoffs, not universal
latency promises. The run records **38,650 native IRQs** and **4,482 NMIs**.

All eight guest snapshots leave at least **205 bytes** untouched at the bottom
of page one. Native Task touched spans reach **614 bytes**; the minimum untouched
space above the reserved 256-byte interrupt floor is **197 bytes** (idle slot).
The kernel touched span is **277 of 1,536 bytes**, with its interrupt floor
untouched. These watermarks are observed lower bounds on stack use, accompanied
by live stack/domain guards; they do not replace P2's deeper interrupt gates.

A4 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including alignment,
guards and spare capacity. It also adds **0 persistent upper-state bytes**.
The common Session remains **2,248 bytes per loaded Image**, including MD5;
there are two guest slots, each with 131,072 backing bytes for its aligned 64 KiB
bank. The guarded DP pool remains 544 bytes; native Task reservations and the
resident SDX bridge capacity are unchanged. New helper code belongs to the
ordinary upper code image. The mixed fixture's **16,384-byte upper static arena**
and its output/counter arrays are test-only; full build reservations are recorded.

### Admitted commands and identities

Use uppercase ARC commands. `L/V` list, `X/E` extract, `A` creates/adds/replaces,
`D` deletes, `U` updates/adds and `F` freshens existing older members. `N/W` control
messages; `W` also suppresses extraction overwrite prompts. `B` retains the old
archive after mutation. The excluded switches and non-atomic replacement limits
above still apply. Hardware access, arbitrary SDX binaries and Commander remain
outside this subset. Full P0/P1/P2 and hosted-system qualification remain open.

The ARC patch manifest is **revision 4**, personality ABI **1**. Frozen original
identities (no original binaries are redistributed here):

| Module | Bytes | SHA-256 |
| --- | ---: | --- |
| `MD5.COM` | 3,488 | `833706e1cab61f52e50e3d8446b53f696d7bd22e8184a64cb1bc350038fd6f79` |
| `ARC.COM` | 3,203 | `2107dcc06b29cf6ba5a26ad8aaf167f59f5211d2d93c08253594507a7d2217dd` |
| `ARCLST.OVL` | 1,998 | `ea0b1f04ffa1c93d8b3fc69baafbb86854651665093c9ab3a091401c2946b7cd` |
| `ARCEXT.OVL` | 1,911 | `b1dd56ac4bb133bfc55150c1c17e401f74903d79a8459c6997ec0105290ad5ba` |
| `ARCADD.OVL` | 4,645 | `f0aa3ef786bc58567bd97a5b6dca58eadf1cdf8bac8bb0e6a3447a4d955d7408` |

```sh
python3 tools/test_sdx_arc_mixed.py --output build/sdx-arc/a4-mixed
python3 tools/test_sdx_arc_mutate.py --output build/sdx-arc/a4-dates
python3 tools/test_sdx_md5_acceptance.py --attributes --output build/sdx-arc/a4-md5-attributes
```

## Interactive output batching

The shared SDX output adapter combines adjacent interactive `PRINTF` and `PUTC`
fragments in its existing 256-byte buffer. It flushes at capacity, newline and
editing controls, before other guest services (including input and exit), and
on retirement. An overwrite prompt therefore reaches the console before its
read begins. Suppressed `VPRINTF` leaves pending ordinary output intact.
Redirected output still completes each original call and preserves ATASCII
bytes. Short writes and native errors use the existing completion and trap
paths; retirement preserves the first failure.

The Process output handle and interactive property are borrowed once per guest
invocation. Each loaded Image's upper Session grows from 2,248 to 2,252 bytes,
or from 2,248 to 2,256 after allocation rounding: **8 upper-heap bytes per Image**.
The buffer and static arena capacities are unchanged. Fixed, per-native-Task
and idle reserved bank-zero growth are all **0 bytes**, including guards,
alignment and unused capacity. The enabled personality retains its existing
544-byte guarded direct-page pool.

Focused emitted checks cover mixed formatted/character output, the buffer
boundary, prompt visibility before a real input read, final partial records,
error exit, discarded output, exact redirected bytes, native write failure and
resource recovery. The Session/frame probes also run raw and optimized.
The packaged graphical benchmark compares console and `NIL:` output on the
same pinned ARC listing after warming the read cache. Its passive routine
observations add no target instructions; elapsed times include preemption.

On the pinned PAL 65816 x8 graphical desktop, the warm two-member sample
listing falls from **3.333 s to 2.129 s**. Native writes, including the shell
prompt, fall from **29 to 8**; their elapsed time falls from **1.567 s to
0.297 s**. This compares one warm before sample with the median of two after
samples. Total command time includes loading ARC and its overlay; typing is
excluded. The matching `NIL:` timings are 1.688 s and 1.635 s.

```sh
python3 tools/test_sdx_output.py --output build/sdx-output/normal
python3 tools/test_sdx_output.py --write-error --output build/sdx-output/write-error
python3 tools/measure_sdx_console.py --bundle build/demo-sdx \
  --utilities path/to/sdx-utils.atr --output build/sdx-output/measure
```

These are development checks, not full hosted-system or hardware qualification.
