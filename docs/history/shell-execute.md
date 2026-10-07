# Shell EXECUTE

`EXECUTE file` implements the roadmap's bounded script slice. The current syntax,
line limits and result rules live in the [shell guide](../guides/shell.md#scripts).
Source lives in [shell-execute.inc](../../examples/shell/shell-execute.inc), with
classification, dispatch and the command loop in
[shell-session.inc](../../examples/shell/shell-session.inc).

## Execution and ownership

Dispatch opens the script independently of selected Input. A small upper-RAM
record retains its source handle, unread bytes and any outer redirection. The
ordinary command line and parser workspaces are reused after each line has been
assembled. Commands never read script text through their inherited Input.

`ShellOneCommand` retains ordinary foreground handling, alias preparation,
dispatch, diagnostics and temporary-stream cleanup. `ShellCommand` invokes it
for the initial EXECUTE and subsequent script lines in a loop. There is no
recursive dispatch. WARN continues; ERROR, FAIL, read/syntax errors and BREAK
stop before another line can execute. Empty/comment lines preserve the previous
command result, including a final WARN.

An outer `EXECUTE file <input >output` lends those streams to the script's
commands. The script record holds their cleanup ownership while each line can
install and retire its own temporary override. Final cleanup settles any line
override, closes the source and restores the borrowed outer streams before
closing inherited temporary handles. Terminal Close failures consume their
wrappers once; an earlier causal error survives cleanup. ShellFinish can retry
remaining ownership if ordinary cleanup cannot finish.

Blank and indented full-line semicolon comments are skipped. LF, CR, CRLF and
ATASCII `$9B` work across read boundaries. A final unterminated command runs.
Overlong lines and NUL bytes reject the entire current line. A nested EXECUTE
fails before its redirection targets are opened. EXIT still exits the shell.
Script arguments, substitution, conditionals and nesting remain unsupported.

## Memory and validation

The script record is 86 bytes, rounded to an 88-byte heap allocation, including
a 64-byte read buffer. It exists only while EXECUTE is active. Its three-byte
global pointer uses the existing upper-RAM data arena; the 128-byte ShellState
and 2,336-byte shell allocation are unchanged. An ordinary DOS source handle
adds its existing backend/context allocation costs. No Task, direct page,
fixed buffer or stack reservation is added. Reserved bank-zero growth,
including guards, alignment and unused capacity, is **0 fixed bytes and
0 bytes per public Task**.

Matched optimized resident builds at the preceding commit and this slice grow
from 817,277 to 823,562 executable bytes: **6,285 native bytes**. This includes
the script helpers, dispatcher loop and parser/cleanup integration. Globals and
literals grow by 16 bytes within the existing 4 KiB data reservation. New local
stack peaks are 34 bytes for Open, 36 for line assembly, 14 for comment skipping,
24 for Close and 32 for the outer command loop; guard checks retain the existing
Task stack reservations. The compiler and ABI pin are unchanged.

The [development evidence](../development/shell-execute.json) records pinned
inputs, emitted code sizes and selected execution artifacts. These are
development checks, not release or physical-hardware qualification:

- The host suite and optimized emitted parser check the builtin's arity,
  quoting, nonempty filename, pipeline rejection and existing shell syntax.
- The physical-key shell loads HELLO, CAT, WC, GREP and controlled result/wait
  commands. It checks aliases and directory changes surviving scripts, pipeline
  dispatch, inherited and overridden input/output, empty/comment-only scripts,
  WARN continuation and final WARN preservation, ERROR/FAIL/syntax stops,
  nesting rejection and 255/256-byte bounds.
- Native script reads cover mixed line endings, CRLF split at the 64-byte
  boundary, one-byte partial reads, unterminated final commands and NUL rejection.
  Private source wrappers inject allocation/read failure and a lost terminal
  Close completion; they do not replace line assembly or dispatch. Cleanup
  errors preserve the earlier command cause.
- Physical BREAK targets both a loaded waiting child and a parent paused at
  source-read entry. Following output verifies restored foreground interaction;
  script EXIT unwinds inherited output before closing the shell.
- Every interactive command checks that the script pointer and redirection
  ownership are cleared and selected streams are restored. Final guard, OS
  restoration and allocation-balance assertions remain enabled. Independent
  host audits verify saved bytes and allocation ownership on native MyDOS and
  SDFS 256-byte-sector fixtures.

The guide, STORY.TXT and demo source manifest include EXECUTE. This slice does
not rebuild preview ZIPs or cartridge images.
