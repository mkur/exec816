# Bounded shell command aliases

Status: implemented. The current behavior is documented in the
[shell guide](../guides/shell.md#command-aliases). This slice adds `ALIAS` and
`UNALIAS` as resident commands without changing DOS `ASSIGN` or the program
ABI.

Each shell owns up to eight aliases. It allocates one upper-RAM table on the
first successful definition and frees it on shell retirement. Names are
case-insensitive command words of up to 15 bytes; definitions contain at most
127 printable bytes. `ALIAS name "command fixed-arguments"` sets or replaces,
`ALIAS name` shows one, `ALIAS` lists occupied slots, and `UNALIAS name`
removes. Built-in names cannot be claimed. The shell replaces the command
word once in each stage, appends that stage's original arguments, and reparses
the bounded line before opening redirections or loading programs. The
replacement cannot add shell operators or quotes. Thus pipelines and
redirection retain the ordinary shell rules, while alias chains and cycles
cannot recurse. Definitions last only for that shell session.

## Cost and checks

The table has eight 144-byte entries, or 1,152 payload bytes, plus allocator
overhead only after first use. Four previously reserved header bytes now hold
the two raw command spans; the shell session's fixed reservation does not grow.
The table pointer and count use four bytes of the existing upper image-data
area. No Task, stack reservation, direct-page region or public provider was
added. The largest new routine local stack peak is 44 bytes, within the
existing Task stacks.

The optimized 720 KiB demo is compared with the preceding ASSIGN build using
the same pinned actionc revision and no local override. The resident native
routine sum grows from 616,788 to 624,507 bytes (**+7,719 bytes**), and the
program XEX from 654,789 to 662,667 bytes (**+7,878 bytes**). The provider
set stays at 42. The bank-zero reservation map, counting guards, alignment
and unused reserved capacity, changes by **0 fixed bytes and 0 per public
Task**. The earlier two 1,536-byte larger Task stacks remain unchanged.

Focused raw and optimized emitted-code cases cover case-insensitive lookup,
fixed and passed-through arguments, both pipeline stages, redirection,
one-pass expansion, replacement at capacity, removal/reuse, a ninth entry
and a 255-byte line bound. Raw and optimized physical-key sessions cover
listing, single-entry lookup, replacement, invalid names and replacements,
pipeline execution and missing aliases. The normal host suite, demo boot and
package checks are development-tier evidence. The packaged OF816 autoboot
reached the standard shell after 249 PAL frames; the Forth-command handoff
also passed. The eleven-entry ZIP contains boot files, disks, the pinned ROM,
the short guide, notices and checksums. These checks do not claim release
qualification or physical-hardware coverage.
