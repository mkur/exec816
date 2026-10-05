# Small command argument parser

Status: implemented; bounded `/M` was added in program ABI version 10. See the
[command usability record](../history/command-usability.md) and
[multiple-file implementation record](../history/multiple-file-patterns.md).

`COMMAND.ReadArgs()` exposes one shared resident DOS parser. Commands describe their arguments
and decide what to do with them. `Open()` continues to resolve file paths.

## Amiga model, reduced scope

AmigaDOS [ReadArgs](https://developer.amigaos3.net/autodocs/dos.library/ReadArgs.html)
uses a comma-separated template and one result slot per field. `/A` marks a
required field. Its broader interface can allocate storage released by
[FreeArgs](https://developer.amigaos3.net/autodocs/dos.library/FreeArgs.html).

Templates support positional strings, required fields, keywords, switches and
unsigned decimal numbers:

| Template | Meaning |
| --- | --- |
| `c"FILE"` | One optional filename, suitable for CAT. |
| `c"FROM/A,TO/A"` | Two required strings. |
| `c""` | No arguments, as used by WC and HELLO. |
| `c"FILE,LINES/K/N"` | Optional file and keyword-only unsigned line count. |
| `c"PATTERN/A,FILE,NOCASE/S"` | Required pattern, optional file and Boolean switch. |
| `c"FILE/M/A"` | One to eight positional strings, used by DELETE. |

Labels contain ASCII letters, digits and underscore, beginning with a letter or
underscore. Labels and modifiers ignore ASCII case; duplicate labels, duplicate
modifiers and spaces in templates are errors. `/A`, `/K` and `/N` may combine;
`/S` must stand alone. `/M` may combine only with `/A`; at most one `/M` field
is allowed and it must be the last positional field. Keyword and switch fields
may follow it. Positional fields fill left to right, skipping keyword and
switch fields. Required fields must be present, including required keywords.

Only `/K` and `/S` fields recognize their labels in argument text. `LINES 20` and
`LINES=20` set the same keyword; `LINES` or `LINES=` without a value fails. Use
`NAME "two words"` for a quoted keyword value. A quoted keyword token is literal
positional data. Duplicate keywords/switches fail; switches do not accept values.
A keyword's following token is its value even if it spells another keyword.

String slots contain addresses into caller storage. `/S` slots contain numeric
0 or 1. `/N` slots contain addresses of four-byte LONGCARD values in caller
storage; zero is distinct from an omitted number. Numbers accept decimal digits
only, from 0 through 4,294,967,295. Empty values, signs, trailing characters and
overflow fail with ERROR_BAD_NUMBER. Defaults belong to each command.

A populated `/M` slot points to a NUL-terminated array of three-byte ADDRESS
values in caller storage. Each nonzero entry points to a decoded NUL-terminated
string in that storage. Cast the slot to `ADDRESS POINTER` and iterate until a
zero entry. At most eight entries are accepted; `/A/M` requires at least one.
Quoted empty strings count as entries. No allocations or extra result slots are
needed. The table is reserved only when the first item is parsed, so an omitted
optional `/M` field succeeds even with zero storage capacity.

Omitted optional slots are zero. A quoted empty string is present; a command may
reject it as an invalid filename. Extra positional arguments are errors. Aliases,
rest-of-line fields, wildcard expansion and argument files remain unsupported.
This is a bounded Amiga-inspired subset, not full Amiga ReadArgs.

## Interface and storage

Public native interface:

```action
LONGINT FUNC ReadArgs(CSTRING template ADDRESS POINTER values CARD valueCapacity
                     BYTE POINTER storage CARD storageCapacity)
```

- `template` is a CSTRING. Parse `GetArgStr()`, never `Input()`:
  redirected input belongs to the command's work.
- `values` is a caller-owned ADDRESS array: three bytes per address or switch value.
  The pinned compiler does not support CSTRING POINTER. View a populated slot
  as `CSTRING(BYTE POINTER(values(0)))` when a CSTRING is needed. Results point
  into caller-owned `storage`. Strings have quotes removed, escapes decoded and
  NUL terminators added; numeric storage is four bytes, not address-width data.
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

Templates are bounded to eight fields and a 255-byte template. Argument text
already has the Process's 255-byte limit. The generated
`COMMAND.ARGS_STORAGE_BYTES` is 315: 256 bytes for decoded
text/terminators, up to eight four-byte numeric values and a nine-entry
three-byte `/M` table. It suffices for every
supported template and argument tail. Numeric values may be unaligned. Smaller
buffers are allowed; insufficient capacity is an error, never silent truncation.

CAT and DELETE use the generated storage bound and one result pointer. An empty template
permits null arrays/storage with zero capacities. ECHOARGS keeps `GetArgStr()`
for the original text.

## Text rules and shell boundary

Use a bounded private scanner, following the role of Amiga's
[ReadItem](https://developer.amigaos3.net/autodocs/dos.library/ReadItem.html),
with spaces/tabs separating arguments and double quotes enclosing a whole
argument. A closing quote requires a separator or end of string.

Retain Exec's existing quoted escapes: `**` becomes `*`
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
| Invalid pointer/capacity pair or invalid numeric value | ERROR_BAD_NUMBER (115) |
| Missing required field or keyword value | ERROR_REQUIRED_ARG_MISSING (116) |
| Excess arguments, including a ninth `/M` item | ERROR_TOO_MANY_ARGS (118) |
| Unterminated quote or dangling quoted escape | ERROR_UNMATCHED_QUOTES (119) |
| Argument text longer than 255 bytes | ERROR_LINE_TOO_LONG (120) |
| Insufficient slots or decoding storage | ERROR_BUFFER_OVERFLOW (303) |
| Duplicate option, switch value, embedded quote, quote suffix or unsupported escape | ERROR_BAD_ARGUMENTS (311) |

Template validation precedes argument decoding; the first decoding error wins.
A null template is a bad template; null source text is bad arguments. CAT and
DELETE reject an empty filename with ERROR_INVALID_COMPONENT_NAME (210) before
opening or deleting any files.

## Integration and cost

### Optional command help

`COMMAND.ReadArgsOrHelp(template, values, valueCapacity, storage, storageCapacity)`
uses the same descriptors and storage contract as ReadArgs, with three distinct
results: `ARGS_ERROR=0`, `ARGS_PARSED=1`, `ARGS_HELP=2`. Only PARSED permits command
work. HELP returns with IoErr zero; ERROR retains the causal error. ReadArgs
remains the ordinary Boolean parser with no console activity.

A sole unquoted `?` in the raw Process tail requests help; surrounding spaces/tabs
are allowed. Quoted or embedded question marks and `?` among other arguments are
parsed normally. Before help, validate the template, slot count and pointer/storage
contract and clear supplied slots. Required values are not required for help.

Help opens an owned foreground console, writes `Arguments: <template>` plus LF,
and closes it. The empty template displays `(none)`. It never consumes Input,
opens a data file, writes selected Output or waits for more arguments. Missing
console, failed write/close and BREAK return ERROR with their original cause.
Ordinary parse failures may also display the template; diagnostic failures do
not replace the parse error. The shell owns the final fault explanation.

All sixteen supplied commands use this wrapper. The implementation in DOSCOMMAND is
shared by the checked COMMAND provider; it adds no per-Process state or allocation
except the temporary console handle. Source/template and storage remain caller
owned and must be valid and non-overlapping throughout the call.

### Shared parser

Exec816 owns the implementation in `lib/dos`, published as one checked resident
`ReadArgs` provider. There is no new kernel call. CAT, WC and the
[toolbox commands](../guides/toolbox.md) use it; shell
built-ins retain their existing parser.

Reserved bank-zero change: **0 fixed bytes / 0 bytes per Task**, including
guards, alignment and unused capacity. Result slots occupy three bytes each;
text buffers belong to callers. Code, ABI metadata and stack measurements are
recorded in the [command usability record](../history/command-usability.md).

Focused raw/optimized checks cover empty/required/extra arguments, quotes and
escapes, exact/short buffers, unchanged source text and independent callers.
The shell handoff check feeds CAT's template with the real shell argument tail.
Follow the [development testing policy](../contributing/testing.md); these checks do not qualify
the whole hosted system.
