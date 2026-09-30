# Small command argument parser

Status: implemented in program ABI version 5. See the
[implementation plan](../plans/command-arguments-implementation-plan.md) for validation and costs.

Replace command-local parsers such as CAT's `Filename()` with one resident DOS
helper, exposed through `COMMAND.ReadArgs()`. Commands describe their arguments
and decide what to do with them. `Open()` continues to resolve file paths.

## Amiga model, reduced scope

AmigaDOS [ReadArgs](https://developer.amigaos3.net/autodocs/dos.library/ReadArgs.html)
uses a comma-separated template and one result slot per field. `/A` marks a
required field. Its broader interface can allocate storage released by
[FreeArgs](https://developer.amigaos3.net/autodocs/dos.library/FreeArgs.html).

Keep the template idea, but initially support only positional string fields:

| Template | Meaning |
| --- | --- |
| `c"FILE"` | One optional filename, suitable for CAT. |
| `c"FROM/A,TO/A"` | Two required strings. |
| `c""` | No arguments, suitable for the current WC. |

Labels contain ASCII letters, digits and underscore, beginning with a letter or
underscore. `/A` is case insensitive. Spaces inside templates are unsupported.

Fields fill left to right; names label slots without keyword lookup. Omitted
optional values are null; missing required or extra arguments are errors.
A quoted empty string is present. CAT still rejects an empty filename.

Defer keywords, aliases, switches, numbers, multiple-value/rest-of-line fields,
interactive help and argument-file expansion. Unsupported templates fail
explicitly. This is an Amiga-inspired subset.

## Interface and storage

Public native interface:

```action
LONGINT FUNC ReadArgs(CSTRING template ADDRESS POINTER values CARD valueCapacity
                     BYTE POINTER storage CARD storageCapacity)
```

- `template` is a CSTRING. Parse `GetArgStr()`, never `Input()`:
  redirected input belongs to the command's work.
- `values` is a caller-owned ADDRESS array: three bytes per string address.
  The pinned compiler does not support CSTRING POINTER. View a populated slot
  as `CSTRING(BYTE POINTER(values(0)))` when a CSTRING is needed. Results point
  into caller-owned `storage`, with quotes removed, escapes decoded and NUL
  terminators added.
- `valueCapacity` counts slots (0–8); `storageCapacity` counts bytes, including
  terminators. Nonzero capacities require valid writable pointers. Source,
  template, result slots and storage must not overlap. Source and template are
  unchanged. Invalid slot pointer/capacity pairs return ERROR_BAD_NUMBER without
  touching the slots; otherwise every supplied slot is cleared on failure.
- Return `-1` on success and `0` on failure. Clear `IoErr()` on success; on failure
  set a shared DOS argument/buffer error and leave all result slots null.
  Partially written storage is unspecified. Validate the template before parsing.
- Results last until storage is reused or released. No allocation, `FreeArgs()`,
  global scratch buffer or persistent parser object.

Bound the first version to eight fields and a 255-byte template. Argument text
already has the Process's 255-byte limit. A 256-byte storage buffer suffices for
all decoded strings and terminators with the grammar below. Smaller buffers are
allowed; insufficient capacity is an error, never silent truncation.

CAT reuses its 256-byte path buffer and adds one result pointer. An empty template
permits null arrays/storage with zero capacities. ECHOARGS keeps `GetArgStr()`
for the original text.

## Text rules and shell boundary

Use a bounded private scanner, following the role of Amiga's
[ReadItem](https://developer.amigaos3.net/autodocs/dos.library/ReadItem.html),
with spaces/tabs separating arguments and double quotes enclosing a whole
argument. A closing quote requires a separator or end of string.

For this first version retain Exec's existing quoted escapes: `**` becomes `*`
and `*"` becomes `"`. Backslash is literal. Reject other quoted escapes,
unterminated quotes and quotes inside unquoted tokens. The broader Amiga escape
rules are deferred. These are command-line rules, separate from Action's
compile-time `c"..."` literal escapes.

The shell still handles command selection, redirection and pipes, and preserves
the original argument spelling. Keep its validation consistent with this helper;
reuse the scanner where practical. Received punctuation remains argument data.

Shared errors are generated from `abi/dos.json`:

| Condition | IoErr |
| --- | --- |
| Malformed/unsupported template | ERROR_BAD_TEMPLATE (114) |
| Invalid pointer/capacity pair | ERROR_BAD_NUMBER (115) |
| Missing required positional field | ERROR_REQUIRED_ARG_MISSING (116) |
| Excess arguments | ERROR_TOO_MANY_ARGS (118) |
| Unterminated quote or dangling quoted escape | ERROR_UNMATCHED_QUOTES (119) |
| Argument text longer than 255 bytes | ERROR_LINE_TOO_LONG (120) |
| Insufficient slots or decoding storage | ERROR_BUFFER_OVERFLOW (303) |
| Embedded quote, quote suffix or unsupported escape | ERROR_BAD_ARGUMENTS (311) |

Template validation precedes argument decoding; the first decoding error wins.
A null template is a bad template; null source text is bad arguments. CAT rejects
an empty filename with ERROR_INVALID_COMPONENT_NAME (210).

## Integration and cost

Exec816 owns the implementation in `lib/dos`, published as one checked resident
`ReadArgs` provider. There is no new kernel call. CAT and WC use it; other
built-ins remain outside this slice.

Reserved bank-zero change: **0 fixed bytes / 0 bytes per Task**, including
guards, alignment and unused capacity. Result slots occupy three bytes each;
text buffers belong to callers. Code, ABI metadata and stack measurements are
recorded in the [implementation plan](../plans/command-arguments-implementation-plan.md).

Focused raw/optimized checks cover empty/required/extra arguments, quotes and
escapes, exact/short buffers, unchanged source text and independent callers.
The shell handoff check feeds CAT's template with the real shell argument tail.
Follow the [development testing policy](../contributing/testing.md); these checks do not qualify
the whole hosted system.
