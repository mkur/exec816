# Compiler upstream merge

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/building.md) and [history index](README.md).

Merge upstream `main` (`57cc927c`) into `exec816-compact-o65`, retaining all ten
local commits through `4293d5cc` and including all 62 upstream commits that were
missing from that branch. The resulting merge is `fe2a933b`. The compiler
checkout is clean; the merge is local and has not been pushed.

The merge required no textual conflict resolution. Validation found two
integration issues, resolved in the merge commit:

- Restore the native runtime test lockfile to upstream's version. The supported
  runner patches the CPU crate to its pinned VM checkout; an extra Git source
  field from the local branch prevented `--locked` builds.
- Refresh the reviewed emission snapshot for upstream `1d9873cb`. Direct
  incoming-word comparisons remove one unused store in three cases. Frames and
  guards stay unchanged; labels, fixups and instruction spans move accordingly.
  No compiler implementation changes were needed.

Development validation covers the root compiler suite (3,635 passed, 29 ignored),
27 native VM tests
(`cstring`, `o65`, `memory`, `interop`, `parameter_comparisons`), 216 Exec host
tests, and raw/optimized Exec execution: 65 ReadArgs cases and 109 resident
library/import/lifetime checks per mode. HELLO, ECHOARGS, CAT and WC also build
as compact o65 commands in both modes. Native comparison tests include IRQ/NMI
reentry and LF/CRLF inputs; Exec fixtures check guards and OS/context restoration.

The root compiler run stopped at the stale snapshot. After reviewing and fixing
it, only that target and the remaining targets were run, followed by doc tests.
Previously passing suites were not repeated. Exec and the first four VM targets
used candidate `e62536da`; the final merge differs only in the snapshot and its
test comment. The pin is promoted with an identical compiler binary hash.
Detailed results and provenance are in the
[development record](../development/compiler-upstream-merge.json).

Selected optimized file sizes with unchanged command sources:

| Command | Before merge | After merge |
| --- | ---: | ---: |
| CAT | 3,756 | 2,854 |
| WC | 3,995 | 2,875 |

The native ABI and image-format version are unchanged. Reserved bank-zero delta
is **0 fixed bytes / 0 per Task**, including guards, alignment and unused
capacity. These checks do not constitute full Exec release qualification.
The play image was not refreshed.
