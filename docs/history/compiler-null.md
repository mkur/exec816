# Compiler-supported NULL

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/building.md) and [history index](README.md).

The compiler pin is `ad55b414`, adding a contextual `NULL` pointer value to
modern Action!. The change is committed locally in actionc and exported as
[a compiler patch](../../toolchain/patches/actionc-null.patch); it has not been
pushed. It builds on the [upstream merge](compiler-upstream-merge.md).

The shell now uses `NULL` for its 36 previously explicit typed-zero casts:

```action
file=NULL
IF file=NULL THEN
  RETURN(NULL)
FI
```

An assignment, typed parameter, pointer return, annotated `LET`, explicit
pointer cast or equality comparison supplies the pointer type. This covers
record, data and callable pointers, plus `CSTRING`. Static pointer initializers
use `[NULL]`. Untyped `LET value=NULL`, numeric uses and ordering comparisons
are rejected. Existing declarations named `NULL` keep their meaning.

Semantic lowering produces the existing typed zero representation. There is no
runtime helper, new ABI or image-format change. Reserved bank-zero delta is
**0 fixed bytes / 0 per Task**, including guards, alignment and unused capacity.

Validation passed:

- Shared compiler suite: 3,639 passed, 29 ignored, including NIR snapshots;
  the NIR sweep passed all 51 fixtures.
- Two additional public compiler tests cover classic/MIR6502 compilation and
  module pointer identity through all backends, with raw/optimized NIR.
- Native 65816 execution: 24 runs across raw/optimized code, IRQ-mask states
  and pointer values, including pointers whose only nonzero byte is the bank.
  Exact three-byte stores, call evaluation count, context/stack guards and
  equivalent LF/CRLF input are checked.
- 216 Exec host tests and one optimized hosted shell entry test with physical
  keyboard input, filesystem commands, redirection, guards and OS restoration.

The hosted run recorded the compiler as an explicit working-tree override.
Promotion to the clean pin verified identical compiler binary and ABI hashes;
the original test evidence retains its original provenance. Details are in the
[development record](../development/compiler-null.json). This is focused hosted
development coverage; the play image and full Exec release matrix were not rebuilt.
