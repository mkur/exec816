# First command toolbox

[History](README.md) · [Command guide](../guides/toolbox.md) ·
[Implementation plan](../plans/command-toolbox-implementation-plan.md)

C1–C6 are implemented. CMP, CKSUM, HEXDUMP, HEAD, GREP, LIST and MORE are loadable
o65 commands alongside HELLO, CAT and WC. The Amiga-style ReadArgs parser now
supports keyword values, switches and unsigned 32-bit numbers. Buffered byte
and line readers, complete writes, directory metadata and foreground-console
access are resident services. The command ABI is version 7; all demo commands
were rebuilt with the pinned compiler, without a local override.

Pipeline aggregation gives errors priority over warnings. A successful early
consumer may cause an ordinary producer broken-pipe error without making the
combined command fail. Individual results remain available. MORE opens its
control stream from the foreground association, so piped data never supplies
keyboard controls. Its geometry query uses the existing console lifetime and
scheduler exclusion rules; this work adds no kernel gateway or interrupt policy.

The [evidence record](../development/command-toolbox.json) identifies the source
hashes, pinned compiler/ROM/emulator, build reports and distribution. Development
checks passed:

| Scope | Executed checks |
| --- | --- |
| Host and generated interfaces | 331 host tests; DOS and program generator checks. |
| ReadArgs | 88 cases in each of raw and optimized emitted code. |
| Command bodies and shared helpers | 75 cases per mode: binary boundaries and host CKSUM oracle, partial I/O, causal errors, BREAK, text limits, matching, enumeration and pager controls. |
| Console access | 25 checks per mode on a nondefault 12×4 instance, with redirected streams, invalid handles/buffers, retained ownership and cleanup. |
| Existing commands | CAT 17 and WC 16 cases per mode. |
| Real shell | Raw/optimized loaded-command and pipeline sessions; physical Space, Return, Q and BREAK; additional warning/error precedence sessions. |
| Packaged demo | Five-second autoboot with clock wrap; final-second cancellation, Forth and manual handoff; disk HELLO, CAT/WC pipeline, EXIT; BYE and occupied-IOCB exits. |

The real shell tests caught stack-local output buffers that violated DOS's
upper-RAM transfer rule. Formatting and pager scratch buffers now belong to each
loaded image, and the controlled transport rejects bank-zero writes. The shell
screen observer now reads logical rows from the existing circular console buffer.
These corrections passed the final checks above.

Reserved bank-zero change is **0 fixed bytes and 0 bytes per Task**, counting
guards, alignment and unused capacity. The existing eight-Task map, DP and stack
pools, boot staging and provider reservation are unchanged. New code, image
globals and caller-owned buffers use upper RAM. Build budgets and observed stack
headroom are recorded in the evidence; all selected guards and OS-restoration
checks passed.

`build/toolbox/demo-final/exec816-demo.zip` contains only the OF816 boot XEX,
matching system disk, pinned ROM, short guide, licenses and checksums. The archive
and its checksums were verified; the original disk geometry fits all commands.
Build intermediates and reports stay outside the distribution.

These are development checks, not release or physical-hardware qualification.
The [toolbox guide](../guides/toolbox.md) records the bounded line length,
literal-only matching, forward-only paging and other unsupported behavior.
