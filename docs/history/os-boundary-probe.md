# AltirraOS 65816 boundary probe

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/platform.md) and [history index](README.md).

This is step 2 of the initial platform bring-up: characterize the OS boundary
before implementing the native loader and adapter. It is **not roadmap
milestone 2**, the cooperative-task kernel.

The assembly [probe](../../probes/os-boundary/probe.s) executes under the actual
AltirraOS ROM through the emulator's XEX loader. It establishes which native
contexts the ROM supports directly and which require an Exec adapter. It does
not implement task switching, the COP `$50` gateway, or a production adapter.

## Reproduce

Requirements: Python 3.9+, ca65 and ld65 (tested with 2.18), and the macOS arm64
AltirraBridge distribution from revision
`61b65720c2dc9a4d1826bffb55055bb31457091e`, including its `sdk/python` directory.
The [platform pin](../../toolchain/altirra.json) records the executable and ROM
SHA-256 hashes. A different binary requires an explicit pin update and another
qualification run; the runner rejects it. This is currently a macOS execution
qualification, not a cross-platform emulator claim.

Build the dedicated 65816 ROM using MADS (tested with 2.1.8) and 7zz/7z:

```sh
python3 tools/build_rom.py
```

This downloads the official Altirra 4.40 source archive, verifies its hash,
extracts the kernel sources, and builds the unmodified source with
`_KERNEL_XLXE=1`, `_KERNEL_816=1`, and binary origin `$C000`. The resulting
AltirraOS **3.44 for 65C816** ROM must match the pinned hash. The assembler emits
an upstream `cio816.s` register-change warning; the verified ROM still matches.
Source notices, labels, listing, and provenance are retained under
`build/firmware/`. To use an already downloaded archive:

```sh
python3 tools/build_rom.py --archive /path/to/Altirra-4.40-src.7z
```

Build and execute the probes, supplying the installed bridge distribution:

```sh
python3 tools/os_boundary.py --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
```

Use `--rom /path/to/altirraos-816.rom` for a different location of the same pinned
ROM, `--build-only` to assemble/package without an emulator, or
`--case cop-route-50` to run one experiment. No actionc build is needed for this
assembly-only boundary test.

The runner writes XEX files, assembly listings, binary observations, console
screen RAM, and `results.json` to `build/os-boundary/`. Any assertion, unexpected
ROM/configuration, socket timeout, or failure to reach a checkpoint exits
nonzero. Full runs and single-case runs have separate JSON report names.

Every run starts its own headless emulator with a temporary settings directory:
800XL, 65C816 at 1x, 64K RAM, no high banks, PAL, BASIC off, and no add-on devices.
The runner does not read or change the GUI emulator's settings or mounted
images. It verifies the mapped ROM bytes outside the hardware/self-test window.
Socket requests and checkpoints are bounded by 15 seconds; launch is also
limited to 360 emulated frames and each experiment to 60. Breakpoints use
`RESUME` with bounded polling: this bridge revision's `FRAME` command can leave
its frame counter pending when a breakpoint stops execution early.

## Results

The [recorded run](../qualification/os-boundary.json) passed all **14 experiments**.
Passing a negative experiment means the expected unsupported boundary was
observed at a controlled stop, not that the unsafe call returned successfully.

| Experiments | Observed result | Consequence |
| --- | --- | --- |
| Eight native VBI cases: four M/X combinations, each with I clear/set | A including hidden B, X/Y, S, D, DBR, P, and native mode restored; OS clock advances | Direct ROM VBI works for the tested page-one stack contexts, including NMI with I set |
| VBI with S starting at `$47EF` | OS VBI enters emulation mode with D=0, DBR=0, S in page one; native interrupt frame is still at `$47EC` | Exec must change stacks before chaining the ROM VBI |
| COP `$00` to CIOV on a page-one stack | `EXEC816 OS BOUNDARY OK` appears in screen RAM, CIO status=1; native S/D/DBR restored, OS VBI completes | The ROM console bridge is usable in its required stack domain |
| COP `$00` with a private stack | Execution reaches the ROM's `SEC/XCE`; the native target word remains at `$47EE` | Native COP0 also requires a page-one stack adapter |
| COP `$00`, `$50`, `$7F` routing | All three call `VCOP0`; the replacement `VCOPU` handler is never called | Exec must intercept `$50` at `VCOPN`; setting `VCOPU` alone is insufficient on this ROM |

The VBI tests set D=`$2200`, DBR=`$12`, A=`$ABCD`, and X/Y=`$1234`/`$5678`
(truncated to their low bytes when X=1). They seed N/V/D/Z/C and verify the
entire restored status byte. A small `VVBLKI` observation hook records the OS
domain, then chains to the original OS VBI in the positive cases. DLI is
disabled. Thus these are tests of the ROM VBI plus a bounded observation hook,
not tests of arbitrary DLI or third-party VBI handlers.

The negative VBI case stops in that hook before the ROM attempts to unwind from
the wrong stack. The negative COP0 case stops immediately after the pinned ROM's
`SEC/XCE`, before it fetches the target. The bridge exposes only the low byte of
S, so the COP0 report combines the probe's full native S, the retained target
word, the observed ROM checkpoint/stack low byte, and the verified `SEC/XCE`
bytes. It does not claim a full post-transition S register read from the bridge.
No timeout or crash is counted as an expected negative result.

The routing experiments temporarily replace only `VCOP0` and `VCOPU` with
harmless `RTL` handlers, leaving the ROM's dispatcher untouched. They do not
invoke the real COP0 service with an invalid signature. The ROM's low nonzero
signature path falls through to `dispatch_0`; the source's `dispatch_u` label
does not establish a working dispatch path. WDC-reserved `$80-$FF` signatures
are not used by these experiments.

## Memory and lifetime

These are disposable diagnostic XEX programs. They check `MEMLO <= $2000` and
`MEMTOP >= $4810`, establish a known stack, and park at a host breakpoint. They
do not return to DOS or implement a general allocator or memory reservation
protocol. Each experiment cold-boots through the XEX loader, so negative cases
cannot leak modified vectors or stack state into later tests.

| Bank-zero range | Purpose |
| --- | --- |
| `$0100-$010F` | Lower OS-stack guard; OS stack starts at `$01EF` |
| `$2000-$203F` | Result record and saved vectors |
| `$21F0-$230F` | Private DP domain at `$2200` and surrounding guards |
| `$3000-$3FFF` | Code and constant data, bounded by linker configuration |
| `$4700-$470F` | Private-stack lower guard |
| `$4710-$47EF` | Private stack, initial S=`$47EF` |
| `$47F0-$480F` | Private-stack upper guards |

The complete private DP domain and its guards must remain unchanged. Both
private-stack boundaries and the lower OS-stack guard are checked after every
experiment. Console output is verified as Atari screen codes in screen RAM;
this does not depend on the bridge's screenshot command.

## Qualification boundary

This establishes the required stack/domain boundary and actual COP routing for
one pinned ROM/machine. It does not qualify asynchronous stack transitions,
interrupt nesting, IRQ/DLI handlers, NTSC or accelerated configurations, banked
RAM, keyboard/disk I/O, worst-case stack headroom, native Action startup, or
preemptive scheduling. Raw/optimized compiler coverage belongs to the later
compiled-program acceptance; this probe does not use compiler output.

The next implementation slice is the native-image loader and serialized OS
console adapter, with a protocol for NMI at every stack/domain transition.
The later gateway must inspect `$50` before forwarding other signatures to the
saved OS dispatcher. The ROM itself remains unmodified.
