# Shell append redirection

The shell accepts `>>destination` through the same command preparation and
cleanup used by `>`. The current syntax and stream behavior are documented in
the [shell guide](../guides/shell.md#quoting-and-redirection).

Append opens with `MODE_READWRITE`, creating a missing file without truncating
an existing one, then calls `Seek(handle,0,OFFSET_END)` before selecting either
temporary stream. A failed Open or Seek prevents execution. The normal cleanup
releases any input or output already opened and preserves the causal error.
`>` continues to use `MODE_NEWFILE`. There is no new DOS mode or filesystem API.

The two greater-than characters must be adjacent, at an existing word boundary.
Spaces after them and a quoted target are allowed. One input and one output
redirection fit the existing sixteen-word limit. Duplicate output operators,
`>>>`, missing targets and output redirection on a pipeline's left stage are
rejected before opening files. Quoted operators remain ordinary argument text.
Aliases and RUN reparse through the same parser; the pipeline's right stage
inherits the positioned output handle. Append is a single initial seek and
ordinary writes, without a concurrent-writer append guarantee. Nonseekable
streams are unsupported append targets.

## Memory cost

The flag replaces one reserved byte in `ShellState`; its emitted size remains
128 bytes. The session allocation remains 2,336 bytes in upper RAM. No handle,
buffer, Task, direct-page reservation or stack reservation is added. Reserved
bank-zero growth, including guards, alignment and unused capacity, is **0 fixed
bytes and 0 bytes per public Task**.

Compared with the preceding SB5 standard shell build, optimized `ShellParse`
grows from 4,524 to 4,641 native bytes and `ShellRedirect` from 2,883 to 3,250:
**484 native bytes total**. Their local stack peaks are 42 and 38 bytes;
`ShellRedirect` previously used 28. The extra ten temporary stack bytes fit the
existing reservations.

## Development checks

The [evidence record](../development/shell-append-redirection.json) identifies
the pinned compiler, ROM, emulator, artifacts and execution scope. These checks
are development evidence, not release or physical-hardware qualification.

- The host suite passes all 396 checks.
- Raw and optimized emitted parser fixtures check syntax, argument tails,
  pipeline placement, word limits, the append flag resetting between commands,
  the unchanged 128-byte record, guards and allocation cleanup. Their byte
  oracle resides at `$30e000`, beyond the larger raw resident image.
- The optimized physical-key shell case uses disposable native MyDOS and SDFS
  256-byte-sector fixtures at profile 4, with generic56k emulation and accurate
  disk timing disabled. It checks creation, repeated and multi-sector append,
  aliases, redirected input, pipelines, preservation after a missing command,
  and subsequent truncation by `>`.
- Verified-write hooks deliver BREAK after a physical write. The shell retains
  the original file prefix and the accepted append prefix, stops consuming
  input and allows a later append. Lost Close completions report FAIL/error 6
  after successful data writes. Each command checks restored selected streams
  and cleared temporary ownership; following console output and final shell
  retirement exercise recovery and allocation balance.
- Independent host audits check the ejected disks' complete file bytes and
  allocation ownership, including all pre-existing files.
