# Stack checks

[Contributor guide](README.md) · [Platform contract](../reference/platform.md)

Keep stack checks enabled for ordinary development and distributed images.
`stack_checks` in [kernel.json](../../config/kernel.json) defaults to true; the
demo builder explicitly selects checked output. Use the
[current compiler pin](../../toolchain/actionc.json), not a revision copied from
an older qualification report.

## Build setting and boundary

The native packager accepts `--stack-checks` / `--no-stack-checks` overrides and
its build API accepts a Boolean setting. Omission follows configuration, with a
checked default. An unchecked build requires compiler support for that setting.
The setting covers compiler entry/call reservations and handwritten assembly
reservation checks. Packaging requires the compiler image and platform setting
to agree.

Build reports record the resolved setting; the shell prints it at startup.
Disabling emitted checks does not enlarge a stack, remove physical guards,
change DP ownership or remove the interrupt reserve. Context ownership and
argument-range validation remain separate from stack-overflow checks.

A checked reservation failure takes the nonreturning fault path before the
invalid reservation. Guards and compiler checks do not prove every possible
application call depth fits and do not provide memory isolation.

## Validation

Use focused emitted-code checks when changing stack behavior, including native
and assembly reservations and guard/context restoration. The
[testing policy](testing.md) controls the scope. Historical checked/unchecked
experiments and their exact compiler inputs are preserved in the
[stack-check implementation record](../history/stack-checks.md); they do not
qualify an unchecked build made with a later pin.
