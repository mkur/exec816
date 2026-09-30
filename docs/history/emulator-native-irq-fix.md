# Native interrupt masking in the pinned emulator

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/platform.md) and [history index](README.md).

The Task integration tests exposed a CPU-emulation defect in the previous
AltirraBridge pin, `61b65720c2dc9a4d1826bffb55055bb31457091e`. A timer IRQ at
the boundary after SEI could repeatedly enter the native interrupt vector
with I already set, before executing its first instruction. Four-byte interrupt
frames eventually overwrote bank-zero RAM. The same emitted Task image could
pass or fail depending on interrupt timing.

Altirra tracks the delayed effect of SEI/SEP/PLP using
`kIntFlag_IRQSetPending`. Its emulation-mode IRQ/NMI entry consumed that flag;
native 65816 entry did not. The correction clears it in
`kState816_SetI_ClearD`, alongside setting I and clearing D. Exec's interrupt
protocol and the Action! compiler are unchanged by this correction.

The emulator change is committed locally as
`52c18c89e354290199d6f1bbd98eb5048849b15c`. The repository includes the
[complete source patch](../../toolchain/patches/altirra-native-irq-mask.patch),
including focused CPU tests, so it does not depend on publication of that
commit. The [build record](../../toolchain/altirra-build.json) records the source
base, patch hash, build options, compiler and tested binary hash. Both
[64K](../../toolchain/altirra.json) and [1 MiB](../../toolchain/altirra-1m.json)
profiles select the corrected binary. ROM bytes and machine settings are
unchanged. Earlier qualification records retain their original emulator pins.

## Focused regression

The test executes real CPU cycles starting at SEI, with a pending IRQ and,
in alternate cases, an NMI at the same boundary. It covers four native M/X
combinations and an emulation-mode control. After 64 cycles, exactly one handler
must have run, I must be set, and the stack must contain exactly one interrupt
frame. It also checks native entry from a nonzero program bank.

The original CPU implementation failed all eight native cases while both
emulation controls passed. The corrected implementation passes all ten. Exact
before/after output is in the build record. Hosted Task tests additionally
exercise real POKEY timer IRQs, VBI scheduling and guarded stack transitions.
The [integration replay record](../qualification/emulator-native-irq-fix.json)
contains the original failure and three passing fresh boots of its unchanged
emitted image on the corrected binary, with timer IRQs active and guards intact.

## Independent actionc-vm comparison

The independent X65-derived CPU in actionc-vm corroborates the corrected
interrupt-entry behavior. No CPU implementation changes were needed. The
[comparison record](../qualification/native-irq-vm-comparison.json) pins the VM
revision, CPU/test source hashes, compiler, fixture bytes and results. Its new
regression is `crates/w65c816/tests/interrupt_entry_mask.rs` in actionc-vm.
It uses the production Rust core directly, with no Altirra, OS ROM, Exec816,
Action! compiler or peripheral model involved.

The boundary fixture uses the same literal `SEI; NOP; BRA self` program and
`INC counter; BRA self` handlers as the Altirra test. It starts with I clear,
asserts IRQ at the SEI fetch and keeps IRQ asserted for all 64 clocks. Half
the cases assert and hold NMI at the same time. All four native M/X combinations
start in program bank 3; emulation mode starts in bank 0. The test checks
handler counters, exact frame write count, vector reads, I, program bank and
stack guards. Boundary cases also check that the saved PC is `$8001` and the
stacked I bit is set: SEI completed before interrupt entry.

| Probe | Cases per build | Result |
| --- | ---: | --- |
| SEI boundary, IRQ alone or simultaneous NMI | 10 | One handler, one frame; no repeated IRQ entry |
| Assertion timing sweep, IRQ alone or simultaneous NMI | 70 | Accepted IRQs enter once; later IRQs remain masked; NMI still enters |
| No-interrupt controls | 5 | No vector reads or stack writes |

All 85 cases passed in both debug and release (170 executions), with identical
results. Native entry leaves S at `$3FFC` from `$4000`, with four stack writes;
emulation entry leaves S at `$01ED` from `$01F0`, with three. Every accepted
case reads exactly one two-byte vector and increments only the selected
handler's counter once. Guards remain intact.

The sweep inserts two NOPs before SEI, putting its nominal fetch at tick 4.
Interrupt assertion ranges from two ticks before that fetch to four ticks
after it. In this VM, IRQ assertions at offsets -2, -1 and 0 are accepted;
offsets +1 through +4 remain masked. Simultaneous NMI selects the NMI handler
at every offset, with no subsequent IRQ entry while the lines remain asserted.
These are measured VM results, not a new claim about electrical sampling times.

The pinned patched Altirra binary was rerun and its SHA-256 verified against
the build record. All ten boundary cases passed and matched the VM's handler
counters, final S and final P. The unpatched failures above remain historical
evidence; the unpatched binary was not rerun in this comparison.

This is an architectural outcome comparison. Altirra's `AssertIRQ(-2)` and the
VM's raw cycle inputs use different timing interfaces; no one-to-one cycle
alignment or matching bus trace is claimed. The sweep ran on the VM only.
Physical 65816 timing and the full Atari system remain separate qualification.
There is no change to Exec816's reserved bank-zero memory.

To rerun from the actionc-vm repository:

```sh
cargo test --manifest-path crates/w65c816/Cargo.toml \
  --test interrupt_entry_mask -- --nocapture --test-threads=1
cargo test --manifest-path crates/w65c816/Cargo.toml --release \
  --test interrupt_entry_mask -- --nocapture --test-threads=1
```

Suggested addition to the forum report:

> We also tested an independent X65-derived 65816 core in actionc-vm, without
> changing its CPU implementation. All ten equivalent SEI-boundary cases
> matched patched Altirra's handler counters, stack pointer and status. A
> further 70 assertion-timing cases and five no-interrupt controls passed in
> both debug and release. Accepted interrupts entered once; holding IRQ
> asserted did not cause repeated entry with I set. This corroborates the
> masking behavior, although the two harnesses do not establish identical
> cycle timing and we have not verified the boundary on physical hardware.

## Rebuild

Use a separate source checkout. From the Exec816 repository root:

```sh
git clone https://github.com/ilmenit/AltirraSDL.git build/altirra-irq-fix
git -C build/altirra-irq-fix checkout --detach 61b65720c2dc9a4d1826bffb55055bb31457091e
git -C build/altirra-irq-fix apply ../../toolchain/patches/altirra-native-irq-mask.patch
cmake -S build/altirra-irq-fix -B build/altirra-irq-fix/build/irq-fix \
  -DCMAKE_BUILD_TYPE=Release -DALTIRRA_BRIDGE_SERVER=ON \
  -DALTIRRA_STATIC_SDL3=OFF -DALTIRRA_SKIP_SDL3_IMAGE=ON \
  -DENABLE_LIBRASHADER=OFF -DALTIRRA_CPU_TESTS=ON
cmake --build build/altirra-irq-fix/build/irq-fix --target AltirraBridgeServer -j 8
build/altirra-irq-fix/build/irq-fix/src/AltirraBridgeServer/AltirraBridgeServer \
  --cpu-test-interrupt-mask
```

The tested macOS build used system SDL3 and an existing ImGui source cache;
the explicit cache override is recorded. The headless executable links only
Apple system libraries. The upstream configure step still requires its SDL3
and ImGui dependencies; skipping SDL3_image affects the unused GUI target.

Place the resulting `AltirraBridgeServer` alongside the unchanged original
bridge distribution's `sdk` directory, or use symlinks in a separate directory.
The checkout's `src/AltirraSDL/AltirraBridge/sdk` is also suitable: all 23 Python
package source files match the SDK used for qualification byte for byte.
This session uses `build/altirra-irq-bridge`. Pass that directory as
`--bridge-dir` to the Exec test tools. The original bridge installation was
left intact.

The binary pin identifies the actual tested artifact. Builds embed timestamp
and revision information, so rebuilding is not guaranteed to reproduce its
hash. Record a rebuilt binary and its source provenance in both platform pins
and rerun qualification before making compatibility claims for that artifact.
