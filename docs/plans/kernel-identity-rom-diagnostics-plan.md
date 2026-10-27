# Kernel identity and ROM diagnostics implementation plan

[Implementation plans](README.md) · [Platform contract](../reference/platform.md) ·
[Firmware admission](../reference/sdx-firmware.md)

Status: KD0–KD3 implemented at the development tier.
[Execution record](../history/kernel-rom-diagnostics.md).
Print the Exec version and source identity at the start
of admitted kernel initialization, then report the captured ROM checksum and
SDX admission result before console startup. A photograph of a failed boot must
identify the running kernel and explain the failure without reaching `VER`.

## Starting point and firmware inputs

The [native entry](../../platform/altirraos/hosted.s) claims its state, establishes
kernel DP/stack and reports memory adoption and Task/heap initialization.
`KERNEL READY=$0000` precedes SDX shadow installation. An installation error
passes directly to terminal reporting; `VBI/IRQ=OK` appears only after success.
Before KD0, the shell printed the generated Exec identity later, after console
startup, so that identity is unavailable in this failure screen.

The [catalog](../../platform/altirraos/sdx-firmware.json) names the original
AltirraOS 3.44/65816 and stock XLOS816F 2.48/2.49 images. Their CPU-visible
CRC-32 values are `$687583A4`, `$FA947133` and `$0A383964`, respectively.
The CRC covers `$C000–$CFFF` followed by `$D800–$FFFF`, excluding the I/O gap;
it is not a checksum of the complete ROM file. Original emulation NMI/IRQ
destinations must also match for an exact profile label. Per the platform
decision, firmware outside these exact identities is assumed to be XLOS and
continues with the captured actual vectors; its checksum is diagnostic.

Earlier OF816 experiments used local XLOS `-DSKINV` images for Altirra's default
XEX loader. The [0.2.2 inputs](../development/release-0.2.2.json) use stock F
images; XLOS XEX fixtures select Disk Boot instead. Keep those experiments
distinct. The former unknown-ROM `$0002` rejection is removed by this change.

## Visible behavior

Print one compact identity line before the existing `BOOT MEMLO` line and before
memory adoption or Task/heap initialization. Generate it from the same identity
record as the shell banner, including the version and clean release tag or
commit/dirty state. Show it even when technical boot verbosity is disabled.
The unclaimed-state rejection before this safe reporting boundary remains a
separate loader/admission path.

After SDX installation returns, verbose successful startup includes:

```text
Exec816 0.2.2 (v0.2.2)
BOOT MEMLO    =$0700
...
KERNEL READY  =$0000
ROM CRC32     =$FA947133
ROM PROFILE   =XLOS816F 2.48
SDX ROM       =OK
VBI/IRQ       =OK
```

The version above illustrates the format; always embed the actual build identity.
Retain the existing shell banner. Assumed XLOS prints its profile, full checksum,
original NMI/IRQ vectors and section CRCs even in quiet mode, then continues.
A failed installation prints its detail block even in quiet mode, followed by
the existing `System halted: $hhhh` line:

| Install result | Diagnostic |
| --- | --- |
| `$0001` | Mapping mismatch; print PIA `PBCTL` and `PORTB`, with checksum/profile marked unavailable. |
| `$0003` | Already installed; mark this attempt's checksum/profile unavailable. |

Keep the numeric result alongside its meaning. A checksum match with unexpected
vectors selects assumed XLOS and exposes those actual vectors. Never print zero
as a substitute for an unavailable checksum, or read values left by a previous
attempt. Use eight uppercase hexadecimal digits, including leading zeroes.

All lines must fit the 40-column OS screen. Keep the diagnostic block short
enough that identity, checksum, rejection detail and final halt remain visible
together, including when loading began near the bottom of the screen.

## KD0 Share and print the early kernel identity

Extend [build identity generation](../../tools/generate_build_info.py) to emit
an assembler input from the same captured version/revision/tag/dirty record as
`execbuild.act` and `exec-build.json`. Pass that record into native assembly;
do not run another Git query after generated outputs have changed the tree.
Keep the generated text in each build directory and carry its input/hash in
the build record. Test clean-tag, clean-commit and dirty-commit formatting,
and split an overlong identity across bounded lines without losing its identity.

Call an early reporter once the state, OS_BUSY protocol and kernel DP/stack
are established, before `MEMORY_INIT` and the first inventory line. Reuse the
existing OS-screen output and context-preservation protocol. Check standalone
fixtures as well as full kernel builds; no new required Action! module or
invalid include may leak into builds without general Tasks.

Acceptance: emitted kernel identity precedes memory adoption and exactly matches
the build record and eventual shell `VER`, in verbose and quiet boot modes.

## KD1 Report the captured ROM and installation result

Use the CRC/profile already retained in the existing SDX snapshot scratch.
Select the XLOS fallback instead of rejecting an unrecognized CRC/vector pair.
Compute section CRCs for `$C000–$CFFF`, `$D800–$DFFF` and `$E000–$FFFF` only
for the assumed profile, using the captured snapshot and private DP scratch.
Report the result after `sdx_probe_install` has returned and before enabling
normal Task/device activity. Keep capture, CRC computation, vector publication
and shadow copying free of ROM output calls. Use the existing direct screen
writer for every ROM diagnostic, including invalid mapping. Keep NMI disabled
throughout the block; only success resumes VBI. Preserve the install return value
across every diagnostic call so failure reaches `finish` unchanged.

Add explicit formatting for 32-bit CRC values and named profiles/results.
Extend [machine-readable diagnostic definitions](../../abi/boot-diagnostics.json)
and their [generator](../../tools/generate_boot_diagnostics.py), preserving
existing event numbers. Keep forced failure reporting explicit; appended
success events must not become unconditional through the failure-event range.
Preserve column-14 alignment for technical labels and the existing first-cause
and terminal screen-restoration behavior.

Use bounded private formatting storage and audit all changed stack offsets and
headroom. Formatting must preserve native registers, widths, D/DBR/S, interrupt
state, IOCB0 and OS margins. Allocate nothing and introduce no new scheduling,
interrupt or device-ownership policy. Put generated strings/code in existing
upper arenas; check their capacity and report emitted-size changes.

Acceptance: known ROMs show their exact eight-digit CRC and selected profile;
other ROMs show their actual CRC/vectors as assumed XLOS and continue. Mapping and
state failures show their distinct reason without stale ROM data.

## KD2 Exercise the emitted startup and failure paths

Use development-tier checks with the pinned compiler and exact ROM/emulator
configuration recorded for every case. Update focused boot observers that rely
on line positions or the current COP-based output rendezvous; observe the real
reporter rather than reintroducing an emulator-specific firmware call path.

Host checks cover generated identities/labels, bounded line lengths, full-width
CRC formatting, profile labels and the assumed-XLOS fallback. Native checks
exercise the actual output bytes and visible OS screen:

- Successful optimized boot on AltirraOS and both stock XLOS F images, with the
  expected CRC/profile and ordered transition to `VBI/IRQ=OK` and the shell.
- A changed staged ROM and a deliberately mismatched private comparison table:
  classification selects assumed XLOS and shadow installation/removal succeeds.
  A separate vector-mismatch fixture covers the vector part of identification.
- Mapping mismatch and repeated installation: distinct status/meaning and no
  stale checksum. Keep these component faults separate from production boots.
- Quiet-mode assumed XLOS still showing identity, checksum, section CRCs and vectors;
  successful quiet boot shows identity while routine inventory remains quiet.
- Boot beginning near the last OS text row, with nondefault margins and real
  VBI activity: scrolling preserves the diagnostic block and guards/context.
- An existing pre-console fatal fault and normal return: preserve first-cause
  behavior, terminal display restoration and the absence of a false halt.

Use small raw/optimized emitted cases for any changed register/argument-width
boundary. Keep the full startup cases optimized. Capture physical screenshots
and exact source/ROM/emulator/media hashes. These checks establish the selected
diagnostic behavior, not full hosted-system or real-hardware qualification.

## KD3 Document and deliver matching demo media

Update the platform/firmware contracts and troubleshooting guide with the early
identity, exact CRC ranges, result meanings and the distinction between stock
ROMs and the old XEX-loader patches. Request the visible identity/checksum and
actual boot medium when diagnosing a report.

Rebuild with `tools/build_demo.py`, retaining OF816, its five-second autoboot,
the combined writable system ATR, matching XEX/Atarimax images and ported tools.
Boot the exact packaged combined ATR on stock XLOS and check the identity/CRC;
check a matching cartridge route and the baseline AltirraOS XEX route. Verify
the ZIP contents/checksums and equality of early identity, `VER` and build record.
Keep XLOS ROMs, manifests and test output outside the distribution. Preserve the
published 0.2.2 tag/assets; any later release uses its own clean tag/build.

Each implementation slice reports reserved bank-zero growth, including guards,
alignment and spare capacity. The target is **0 fixed/root/kernel bytes,
0 bytes for each of twelve public Tasks and 0 idle bytes**. Private temporary
stack use is budgeted against existing reservations. All slices meet this
reservation target. The execution record separates emitted upper-code growth
from transient use of the existing stack reservations.
