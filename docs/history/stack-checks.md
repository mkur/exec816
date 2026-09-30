# Stack checks

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/stack-checks.md) and [history index](README.md).

The current compiler pin, `32af3e2b`, always emits stack checks. Its main branch
does not include the optional switch from `2d73c03`; `--no-stack-checks` is
therefore unsupported with the current pin and is rejected by the compiler.
The unchecked behavior and qualification below describe the earlier compiler.

`stack_checks` in [config/kernel.json](../../config/kernel.json) defaults to true.
The native packager accepts `--stack-checks` and `--no-stack-checks` as per-build
overrides. The build API accepts `stack_checks=True/False`; omission follows
the configuration, and a missing configuration key defaults to true. Nonboolean
values are rejected.

The setting applies to compiler-generated entry/call reservation checks and
the handwritten assembly reservation checks in the console, signal, memory,
port and SIO paths, including their diagnostic helpers. Compiler imports report
their actual checked/unchecked status. Image packaging rejects a compiler image
whose setting differs from the assembled platform. `build.json`, `memory.json`
and `exec-build.json` record the resolved setting.

The Python builder uses actionc's checked default by omitting `stack_checks`
from `layout.json`; an unchecked request explicitly sets it to false. The
builder passes `-D STACK_CHECKS=0` or `1` to ca65. With a compiler supporting
the optional switch, its emitter omits checks when disabled; assembly
`.if STACK_CHECKS` directives omit the
corresponding handwritten checks. The builder also generates the startup string
in `execbuild.act`. Action! source is identical in both modes, with no source
conditional compilation or runtime branch around the omitted checks. See the
[build pipeline](native-launch.md#build-pipeline) for the roles of ca65 and ld65.

The resident shell prints `exec: stack checks enabled` or
`exec: stack checks disabled` immediately after the configured task-slot count.
The [startup sequence](../guides/shell.md) retains the configured baud profile.

Disabling checks does not change stack allocation, DP ownership, the 256-byte
interrupt reserve, either 16-byte stack canary, or canary initialization. Saved
context and gateway argument-range validation remain active: these validate
ownership and call shapes rather than impending stack reservations. The test
harness still verifies canaries in both modes. No periodic runtime canary scan
is added. Reserved bank-zero storage changes by **0 bytes**, fixed and per task.

Checked builds detect an invalid impending reservation and take the existing
nonreturning stack-fault exit. Unchecked builds retain the physical ABI but
provide no stack-overflow detection guarantee. Keep checks enabled for normal
development and distributed images; the opt-out supports controlled benchmarks.

## Compiler input

The [compiler pin](../../toolchain/actionc.json) advances from `ae1f555` to
`2d73c03`, a focused change based directly on the previous pin, on actionc branch
`feature/native-stack-checks`. It adds an optional boolean `stack_checks` to the
native JSON layout. Omission enables checks. Unchecked v3 images explicitly
carry `stack_checks: false`; checked images retain the existing representation.
Frame maps, ABI constants and headroom stay unchanged. Experimental o65 remains
checked. No emitted machine-code patching is used in Exec816.

## Validation

The [qualification record](../qualification/stack-checks.json) records the tested
compiler and pinned emulator inputs, raw/optimized cases, and memory budget.
`tools/test_stack_checks.py` raises only a logical floor while retaining ample
physical space: checked compiler/assembly entries fault; unchecked entries
complete with the expected result. It restores the injected floor before the
ordinary domain audit without modifying stack/canary bytes. Natural recursion
also exercises checked overflow without corrupting the physical guards.

The resident shell entry test covers both modes through native console input,
57.6k-profile SIO, mount/list/read commands, service shutdown and OS restoration.
These emulator tests do not establish physical-hardware qualification or a
performance improvement measurement.
