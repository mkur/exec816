# SDX loader and Process development

The P3 native record decoder passes development checks on the pinned
AltirraOS/65816 platform. P3 synthetic Process admission also passes; P4 services remain in progress.
[Plan](../plans/spartados-personality-implementation-plan.md) ·
[Execution record](sdx-loader.json)

`SDXFILE.Load` decodes conventional `$FFFE` blocks, `$FFFD` relocations,
`$FFFB` imports and `$FFFC` exports into an unpublished caller-owned bank.
It supports forward references, nonzero assembled origins, page alignment and
BSS. Limits are 16 blocks, 32 exports and 65,536 serialized bytes. The staged
input remains immutable and must outlive the returned layout. Releasing the
layout does not release the caller's bank.

Unknown imports, duplicate blocks/exports, malformed or overlapping fixups,
fixups into BSS, invalid exports and placement overflow fail explicitly.
Absolute and extended-memory records are unsupported. Failure can change the
unpublished destination; the caller must discard it. This decoder grants no
permission to execute a third-party module.

The optimized run passes 61 checks, comparing every placed byte of all five
pinned MD5/ARC modules at `$2000` and `$4100` against the independent host
parser/relocator. It also tests forward references, alignment, BSS and malformed
records. The focused raw build passes 20 checks with MD5 at one placement and
the small structural cases. Both run as emitted native code, preserve platform
stack guards and restore the memory ownership table at shutdown.

```sh
python3 tools/test_sdx_loader.py --output build/sdx-loader/opt
python3 tools/test_sdx_loader.py --case raw --output build/sdx-loader/raw
```

Reserved bank-zero change: **0 fixed bytes, 0 per Task**. The bounded layout
and transient 8,192-byte relocation bitmap use the upper heap. The bitmap is
released before a successful return; error paths release both allocations.
These are development component results, not hosted-system qualification.

## P3 Process admission

The opt-in `native_program.build(..., sdx=True)` personality admits the
source-audited [synthetic command](../../compat/sdx/probes/process.s). The build
records its complete SDX file size, CRC32 and SHA-256; the target selects exact
size/CRC32, decodes/binds the records, checks and patches its `SEI`, then
publishes an SDX Image. The pinned third-party MD5/ARC files remain unsupported
for execution pending their application gates.

`PROGRAMFILE.Load`, `PROGRAM.Load`, `PROCESS.StartLoaded`, owner unload and
wait/collection use the ordinary Image reference and Process retirement paths.
An Image retains one guest slot until its last reference is released. Failed
load/start transactions release their resources. Each launch establishes a
fresh stack/direct page; a retained Image can be launched again after collection.
The two private guest banks come from aligned upper-heap allocations.

The shared [bridge](../../platform/altirraos/sdx-runtime-probe.s) uses the retained
bank in its context instead of fixed guest banks. The owner publishes the bank
before restoring page one; scheduling remains excluded until detachment. Native
NMI classification compares the saved PBR with that bank, including the final
return trampoline. Diagnostic P2 builds use the same bridge. ROM shadowing is
installed at startup before device activity and removed after device retirement.

Four optimized emitted-code runs pass **72 checks each**: normal execution,
NMI at the final pending check, after restoring A, and inside the guest bank
before re-entering emulation mode. They cover two simultaneous guests, native
Process output, a third load failing while both slots are occupied, invalid
launch rollback, owner unload during execution, collection/reuse, retained-Image
relaunch, input corruption/truncation and complete heap recovery. Platform and
DP-pool guards survive. The native decoder separately rejects unknown imports
and malformed records before publication. P3 output supports literal `PRINTF`;
formatted output and the other service implementations belong to P4.

Enabled builds reserve **544 additional fixed bank-zero bytes**, including two
aligned 256-byte guest pages and two 16-byte outer guards. The generated
post-adoption map chooses `$6300`/`$6400` in the current profile; the entire
reservation is `$62F0–$650F`. The loading map is unchanged. Native Tasks, root,
kernel and idle have **0 additional reserved bank-zero bytes**. Bridge/startup
code fits existing reservations.

Upper reservations are one complete 65,536-byte resident bank (ROM image,
underlay backup, context/host-stack images, code and unused capacity) and
131,072 rounded backing bytes per guest Image. The enabled build also reserves
4,096 bytes for compiled static data, 2,048 more than the default profile; this
is upper RAM. Native Image/Session records and the transient decoder allocations
are separately heap-owned and recovered by the tests.

```sh
python3 tools/test_sdx_process.py --output build/sdx-process/opt
python3 tools/test_sdx_process.py --return-probe 1 --output build/sdx-process/return-1
python3 tools/test_sdx_process.py --return-probe 7 --output build/sdx-process/return-7
python3 tools/test_sdx_process.py --return-probe 8 --output build/sdx-process/return-8
python3 -m unittest discover -s tests -p 'test_sdx*.py'
```

The unchanged native Process wait/completion scenario also passes with SDX
disabled. Its explicit test profile uses a 4,096-byte upper static-data arena
because the current console-linked program exceeds the default 2,048 bytes.
This profile override adds no bank-zero reservation. The original smaller
profile failed during image layout validation, before execution.
