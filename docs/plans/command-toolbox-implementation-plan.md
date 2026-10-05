# First command toolbox

Status: C1–C6 implemented; development checks passed. Release qualification remains
separate. Follow the [roadmap](../roadmap.md), [testing policy](../contributing/testing.md)
and [platform budget](../reference/platform.md#bank-zero-memory-budget).

## Outcome and scope

Ship loadable CMP, CKSUM, HEXDUMP, HEAD, GREP, LIST and MORE beside HELLO, CAT and
WC. Use shared DOS services and the current pinned compiler. Keep disks read-only,
the two-stage foreground pipeline, and the five-second OF816 standard-demo boot.
PATH/ASSIGN, scripts, background jobs, writable filesystems, TAIL, FIND, regex and
multiple-file arguments are follow-on work, not prerequisites for this toolbox.

Commands use Amiga-style keyword arguments and Unix-style streams. Templates
remain bounded and allocation-free. Binary commands preserve bytes; text commands
recognize LF, CR, CRLF and ATASCII EOL, and output LF. Embedded NUL stays counted
data. Limits and non-error outcomes must be visible in the guide.

## C1: arguments and common stream operations

- Extend the resident ReadArgs parser with /K keywords, /S switches and /N
  unsigned decimal numbers, composable with /A where meaningful. Keywords ignore
  ASCII case; quoted keywords remain positional data. Support KEY value and
  KEY=value, reject duplicate options, missing values, signs, invalid digits and
  overflow. Preserve existing quoting and positional behavior.
- Keep ADDRESS result slots: strings and numbers point into caller-owned storage;
  switches contain 0 or 1. Numeric values occupy four bytes, never a truncated
  address-width scalar. Publish enough storage for decoded text and eight numbers.
  Numeric decoding here is part of DOS argument semantics; do not introduce a
  competing generic compiler runtime conversion library.
- Add a resident WriteAll operation with explicit partial-transfer/error handling
  and BREAK polling. Add a caller-owned buffered reader/text scanner with no
  global mutable state, no per-byte DOS crossings, and no hidden allocation.
  Text lines have a published limit and fail explicitly rather than truncate.
- Add RETURN_WARN=5 for a successful comparison with differences or search with
  no matches. Preserve IoErr=0 for these outcomes.
- Update ABI inputs and generated bindings together; rebuild every command.

Acceptance: raw/optimized emitted parser and stream tests cover malformed
templates, quotes, option ordering, duplicates, numeric boundaries, exact/short
buffers, CRLF across reads, embedded NUL, partial transfers, causal errors, BREAK
and independent caller state. Existing CAT/WC argument regressions remain valid.

## C2: binary utilities

- CMP FROM/A,TO/A compares independent file streams. Equal files return OK;
  first differing byte or unequal length returns WARN with a byte offset.
- CKSUM FILE computes the POSIX cksum CRC-32 and length (single optional file or
  selected Input), checked against an independent host oracle and known vectors.
- HEXDUMP FILE,OFFSET/K/N,LENGTH/K/N prints hexadecimal offsets, sixteen bytes
  per row and printable ASCII. Skip offsets by streaming so pipes work too.
- All utilities use counted buffers, preserve the first causal I/O error and
  close only handles they own. Overflow fails rather than wraps.

Acceptance: raw/optimized actual command bodies exercise empty, binary, partial
and bank/16-bit boundaries, argument failures and cleanup. Build checked o65
commands and exercise real loader imports on the pinned system.

## C3: text filters and pipeline outcomes

- HEAD FILE,LINES/K/N defaults to ten lines, supports zero, and exits after the
  selected prefix without reading the whole upstream stream.
- GREP PATTERN/A,FILE,NOCASE/S,INVERT/S,NUMBER/S uses literal counted matching;
  ASCII-only case folding. No regex or filename expansion. Empty pattern matches
  every line. No selected lines returns WARN; errors remain ERROR.
- Define pipeline aggregation: report the first ERROR/FAIL in command order,
  otherwise WARN if either stage warns. A left ERROR_BROKEN_PIPE caused by a
  successful right stage (OK or WARN) is an expected early-consumer outcome;
  preserve individual results but omit it from the combined failure decision.
  Never hide another producer error or an unsuccessful consumer.

Acceptance: raw/optimized line-boundary/long-line cases, no-match and inversion,
case folding, early HEAD and pipeline retirement, cancellation and error priority.

## C4: external directory listing

- Publish existing DOS Lock/UnLock/Examine/ExNext operations and the generated
  FileInfoBlock layout through checked command imports. Keep handles opaque;
  commands never inspect private lock or filesystem records.
- LIST DIR,NAMES/S lists the named/current directory in disk order. Default
  output gives names, directory markers and file sizes; NAMES emits one bare name
  per line for filters. An empty directory succeeds. Do not claim unavailable
  metadata or add sorting/recursion in this slice.

Acceptance: emitted tests for empty/mixed directories, enumeration error versus
normal EOF, invalid paths, BREAK and lock cleanup; disk-loaded LIST | GREP smoke.

## C5: foreground console access and pager

- Expose IsInteractive and a reusable DOS operation opening an owned RAW handle
  to the caller's active foreground console, independent of Input/Output.
  Missing foreground association fails explicitly. Do not fall back to unit zero.
- Expose a bounded console-size query on an owned console handle. Resolve stable
  endpoint identity under the established lifetime rules; no raw private pointers
  cross the command ABI and no new worker or kernel gateway operation is needed.
- MORE FILE pages text on interactive Output using its actual width/height.
  Space advances a page, Return a row, Q quits successfully; BREAK cancels.
  Keyboard controls use the associated RAW handle, never the data stream.
  Noninteractive Output copies the text without prompts or keyboard waits.
  Initial pager is forward-only; tabs/wrapping and control-byte display policy
  are explicit. Reject interactive data Input without a filename.

Acceptance: raw/optimized pager algorithm checks and focused real-console tests
for a nondefault instance, redirected/piped Input, page/line/Q/BREAK controls,
geometry, redirected Output, ownership cleanup and OS restoration.

## C6: integration, distribution and documentation

- Include all commands in tools/build_demo.py; keep build reports outside media
  and the distributable ZIP. If disk capacity needs adjustment, use a supported
  geometry and update its configuration/guide rather than silently omit commands.
- Refresh command and argument guides, API references, relevant indexes, demo
  help text and this plan's completion record. Record unsupported behavior.
- Run the host suite, affected generator --check checks, focused raw/optimized
  emitted tests, loaded-command/pipeline smoke and OF816 packaged-demo smoke.
  Keep the pinned ROM/emulator and record compiler overrides only if necessary.
- Report actual development scope and artifacts; do not claim release or hardware
  qualification. Commit coherent implementation slices after their checks.

## Memory and ownership constraints

Target reserved bank-zero delta for every slice: **0 fixed bytes, 0 bytes per
Task**, counting guards, alignment and unused reserved capacity. Commands consume
existing Task/DP/stack slots; buffers, parser results and command images live in
upper RAM. Measure final build maps and stack bounds before claiming this target.
Shared helpers run in the caller, with caller-owned state and existing DOS
ownership/cancellation. No per-command private kernel services or new IRQ/NMI
protocols. If a compiler defect appears, fix it in actionc with a focused
regression and record the revised toolchain input; do not special-case commands.

## Execution record

Plan committed before implementation as `0633032`. All six slices are complete;
the [implementation record](../history/command-toolbox.md) and
[development evidence](../development/command-toolbox.json) identify the checked
inputs, reports, memory costs and distribution. The existing disk geometry fits
all ten commands. No compiler override or kernel gateway change was needed.

Validation covered 331 host checks; raw/optimized parser, command, console and
CAT/WC regressions; physical loaded-command/pipeline/pager sessions; and both
packaged OF816 handoff routes. Fixed and per-Task reserved bank-zero deltas are
both zero, including guards, alignment and unused capacity. The guide records
the 1,024-byte text-line bound, literal-only GREP and forward-only MORE limits.
