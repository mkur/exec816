# Native direct-page partition

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/building.md) and [history index](README.md).

D1 is committed in actionc as `4d8e0ffa81b2b97703319a51cff2285866b4cb52`,
on top of the previous pin `ad55b414`. The [compiler patch](../../toolchain/patches/actionc-native-dp-v2.patch)
preserves that local commit for review; it has not been pushed.
The final pin is `c384bc8da9e62a280ecb4998e4d275bc6e45935f`, adding
`43b7af17`'s [compact header correction](../../toolchain/patches/actionc-native-dp-header.patch)
and a [documentation-only correction](../../toolchain/patches/actionc-native-dp-history.patch)
to retain the native-v1 context of historical compiler reports. These local
commits are retained in `build/actionc`; the patches apply in the order above.
The [implementation plan](../plans/direct-page-partition-implementation-plan.md) describes
scope. No C toolchain, wrapper or cross-language convention is included.

D2 adopts native ABI v2 and compact o65 v3 throughout Exec816. Task creation uses
compiler-generated metadata offsets; task-context memory clearing and mailbox
helpers use upper-half scratch. Domain validators separately check metadata and
reserved-zero bytes, allowing arbitrary caller workspace. COP activation-local
stack scratch retains its existing offsets. No ordinary call or switch copies
the lower half. Public COP selectors and Task layouts are unchanged.

The domain still reserves 256 bytes with the same alignment, guards and pool
stride. **Bank-zero delta: 0 fixed bytes and 0 bytes per task**, including unused
reserved capacity. Compact metadata stays at 8 + 4 bytes per import.

D2 [development evidence](../development/direct-page-d2.json):

- 217 host tests and native/Task/program/gateway generator checks passed.
- Raw and optimized two-task fixtures preserve distinct 128-byte patterns across
  caller-context allocation/clearing, resident CSTRING calls, full dispatch,
  fast Forbid/Permit/GetMsg, signal/message waits and actual VBI preemption.
  A second admission reuses the released slot and checks fresh initialization.
  A separately seeded kernel pattern, metadata, guards and OS restoration pass.
- The existing `atomic-opt` IRQ case interrupts a live kernel activation and
  rejects an IRQ-context COP while checking live upper-half compiler scratch.
- Six guard-enabled stack cases cover raw/optimized compiler and assembly guard
  failures plus natural recursion overflow. The pre-existing unchecked-layout
  option is not accepted by this compiler pin; reconciling that option remains
  outside this migration. `--checked-only` selects the relevant working checks.
- Optimized loader validation passed 1,124 assertions. Raw ABI smoke passed 23,
  including old compact-v2 descriptor/magic rejection and allocation cleanup.
  Native-v1 images are rejected at the host package boundary.

Reproduce the core checks:

```sh
python3 tools/test_dp_partition.py --mode raw --output build/dp-partition/raw
python3 tools/test_dp_partition.py --mode opt --output build/dp-partition/opt
python3 tools/test_o65_validation.py --abi-smoke --case raw --output build/dp-partition/loader-raw
python3 tools/test_stack_checks.py --checked-only --output build/dp-partition/stack
```

The records pin the compiler, ROM, emulator and machine configuration. They are
development evidence; full release qualification remains pending. Historical
qualification records retain their original ABI and inputs.

D3 rebuilds the resident image, all standalone examples, and HELLO, ECHOARGS,
CAT and WC against the final pin. Its [development record](../development/direct-page-d3.json)
contains artifact, compiler, ROM, emulator and configuration hashes. The
optimized play bundle is `build/demo/program.xex` with `build/demo/sdfs.atr`.

During integration review the compact descriptor's native revision was found
to still be 1. Both writer and loader now derive/check revision 2 from the ABI
constant; the header remains eight bytes. Focused compiler o65 and CLI checks
passed (13 and 7 cases). This is included in the final rebuilt commands.

The loaded-command fixture seeds each caller's lower DP half, then crosses
COMMAND and resident CSTRING calls. Both raw and optimized runs pass 114
assertions, including two separately relocated instances, return/error paths,
old compact-v2 rejection, stale native-revision rejection and cleanup.
The optimized Amiga ports, Tasks and Signals examples also pass with native
console output, a physical Return key, guards and OS restoration checked.
These runs used `43b7af17`; the final compiler successor changes documentation
only, with the same compiler binary, runtime and ABI inputs. The passing runs
are retained rather than repeated for documentation changes.

The final play-image smoke checks startup, HELLO, `CAT STORY.TXT | WC`, physical
BREAK during loading, subsequent HELLO, heap/ownership recovery and EXIT with
OS restoration. Other standalone examples have build-only evidence; this is
not a full example or release qualification matrix.

```sh
python3 tools/test_cstring.py --case raw --output build/dp-partition/command-raw
python3 tools/test_cstring.py --case opt --output build/dp-partition/command-opt
python3 tools/test_task_examples.py --mode opt --output build/dp-partition/examples
python3 tools/build_demo.py
python3 tools/test_demo.py --loading-smoke
```

Each slice adds **0 fixed and 0 per-task bank-zero bytes**. These slices establish
lower DP workspace preservation; they did not test a C compiler.

The subsequent [Calypsi C binding](../guides/calypsi-c.md) uses this partition for its
per-Task C runtime workspace and adds focused C integration checks. That work
is separate from the D1–D3 evidence above.
