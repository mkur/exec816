# Reclaiming the CPU from an emulation-mode guest

[Documentation index](../README.md) ·
[SDX implementation plan](../plans/spartados-personality-implementation-plan.md) ·
[Recorded result](emulation-preemption.json)

On 18 October 2026, a standalone machine-code probe completed **64 NMI-driven
round trips from a 65816 emulation-mode guest into native code and back**.
The guest kept `SEI` set and executed an ordinary 6502 `JMP` loop without calls
or yields. NMI reclaimed the CPU without guest cooperation. This is development
evidence for the mode bridge, not an Exec Task or SDX compatibility result.

## Setup and checks

The [probe](../../probes/emulation-preemption/probe.s) uses the unmodified
AltirraOS 3.44 65816 ROM and the
[paced emulator pin](../../toolchain/altirra-shell-paced.json): 800XL, PAL,
65816 at 8x, 64 KiB base RAM, 63 upper banks, shadow ROM enabled, BASIC and
DLI disabled. The runner verifies ROM/emulator hashes, mapped ROM bytes and
machine settings. ca65/ld65 2.18 assemble the fixture; no Action! compiler,
compiler override or raw/optimized build distinction is involved.

| Check | Observed result |
| --- | --- |
| Aligned `D=$2200`, `X=$FE`, `LDA $BC,X`, emulation mode | Reads `$22BA`, value `$69` |
| Identical instruction and register setup, native mode | Reads `$23BA`, value `$96` |
| Guest with NMI disabled for at least four frames | Upper-bank loop runs; native counters remain zero |
| Hardware VBI NMI enabled by the host controller | 64 native worker calls, counter reaches 448 |
| Guest context at first entry and after every return | All 65 snapshots match exactly |
| Page one overwritten with `$5A` during native work | Full 256-byte snapshot restored; live guest bytes and interrupt frame match |
| Native worker waits for a further hardware VBI | One nested native NMI; worker registers, D and S restored |
| DP/shadow boundary and native stack guards | Intact |

The guest context is `E=1`, full `A=$ABCD` including hidden B, `X=$5A`,
`Y=$A6`, `S=$01ED`, `D=$2200`, `DBR=$03`, `PBR=$02`. Its flags include
decimal mode and `I=1`; hardware-stacked P is `$ED`. The low PC is checked
against the assembled loop address. Successful execution back in bank `$02`
establishes code-bank restoration; PBR is not present in the emulation frame.

The native worker has D at `$2400` and S at `$47ED` inside its subroutine.
It increments a private direct-page counter, overwrites page one, and on its
first invocation waits for a nested NMI. It is a subroutine of the probe's
interrupt bridge, not a separately scheduled Exec Task. The guest loop and
native counter are deterministic context checks, not an MD5 workload.

## Mechanism and ROM constraint

The emulation NMI vector enters the ROM in bank zero. Hardware pushes a
three-byte frame; the ROM pushes A/X/Y and dispatches through `VVBLKI`.
The hook executes `CLC / XCE`, saves the complete guest context, switches to
a private native stack and DP, and copies all of page one before native work.
On return it restores that page, D, DBR, S and hidden B, re-enters emulation
mode, and performs a long jump to an adapter trampoline in the guest bank.
That trampoline pulls Y/X/A and executes emulation-mode `RTI`.

The long jump matters: an emulation interrupt clears PBR without stacking it,
and emulation `RTI` does not pull PBR. A bank-zero `RTI` alone would resume
at the right 16-bit address in the wrong bank. Here the adapter knows the
single guest's code bank. The CPU behavior and the aligned-D wrapping rule
are described in sections 7.2 and 7.11 of the
[W65C816S data sheet](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf).

The pinned ROM also executes absolute `BIT $D40F` and `STA $D40F` before
reaching `VVBLKI`, without clearing DBR. With this guest's DBR, those access
**`$03D40F`, not ANTIC in bank zero**. The fixture initializes and clears that
private byte to keep its sign bit clear, and the hook explicitly acknowledges
the real ANTIC through a bank-zero long store. The ROM's write otherwise leaves
the guest's A value there; a negative value could misroute the next NMI as DLI.
This is a platform integration requirement, not an invisible ROM service.

Native NMI uses a separate `VNMIN` hook which saves/restores the interrupted
native context and ticks a counter. It never starts another guest switch.
The tested nested entry occurs in native work after the page-one snapshot.
This does not cover every instruction boundary during entry/return; DLI and
other NMI sources are excluded. Both hooks replace normal VBI processing in
this disposable fixture. It does not exercise the OS VBI body or return to DOS.

## Consequences for MD5

Emulation mode is a viable candidate for preserving the audited MD5 binary's
indexed zero-page wrapping while still allowing asynchronous native entry.
The current implementation plan adopts `E=1` with audited binary patches and
separate production integration gates. This experiment does not change the
production scheduler or admit MD5.

Integration still needs ownership and switching of physical page one, a saved
guest code bank, OS service entry/return, a scheduler rule for guest `I=1`,
IRQ/NMI coordination across every transition, and coexistence with the normal
OS interrupt path. Native code must enable device IRQs only in an appropriate
native context: NMI preemption by itself does not undo the guest's IRQ mask.
Absolute references to zero page or page one remain distinct from relocated
direct-page addressing or the physical emulation stack and require an audit.
Only one stack depth and one guest bank pair were tested. Physical hardware,
other ROMs, two guests, blocking services and actual MD5 execution remain untested.

## Reproduction and validation scope

```sh
python3 tools/test_emulation_preemption.py
```

The [runner](../../tools/test_emulation_preemption.py) generates the XEX, listing,
labels, state/context/page-one dumps and JSON under `build/emulation-preemption`.
It uses real ANTIC VBIs. The host enables NMI after the negative control and
observes completion; it does not inject an interrupt, change E, or repair CPU
registers or guest memory during execution. The final 65th guest entry records
the result and stops in native mode after the preceding 64 completed returns.

Development checks: the assembled probe passed. The repository host suite ran
498 tests: 492 passed, four historical audits skipped, and two failed. Both
failures reproduce in a clean archive of commit
`42bc8a5ceabb220af61624934bc6c7347959feb9`, with the same compiler artifacts:
the C package fixture expects ABI 19 but receives 20; the provider manifest
fixture expects 1,807 bytes but receives 1,844. These existing assertions were
left unchanged. Documentation links and whitespace were checked. No release
qualification matrix or demo rebuild was run.

## Memory accounting

Production reservations change by **0 fixed and 0 per-Task bank-zero bytes**,
including guards, alignment and unused capacity. The standalone experiment
does not use the production memory profile. Its explicitly reserved ranges are:

| Bank-zero range | Reserved bytes | Purpose |
| --- | ---: | --- |
| `$0100–$01FF` | 256 | Existing OS page one, temporarily owned by the guest |
| `$2000–$203F` | 64 | State, including unused capacity |
| `$21F0–$250F` | 800 | Guest DP, stack shadow, native DP and 32 guard bytes |
| `$2600–$2A1F` | 1,056 | 65 context records and 16 unused bytes |
| `$3000–$3FFF` | 4,096 | Resident probe code, including linker padding |
| `$4000–$40FF` | 256 | Guest payload staging, including unused capacity |
| `$4700–$480F` | 272 | 224-byte native stack and 48 guard bytes |

That is 6,544 fixture bytes above the OS area plus 256 bytes of existing page
one. The upper guest code slot is 256 bytes at `$023000`; `$03D40F` is the
controlled ROM-entry byte. These are fixture allocations, not a proposed
per-Task budget. A real guest needs a 256-byte page-one image, which could live
in upper RAM; the fixture keeps its image in bank zero for simple inspection.
