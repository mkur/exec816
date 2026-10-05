# Command toolbox

[Guides](README.md) · [Shell](shell.md) · [Writing commands](commands.md)

The demo supplies seven loadable commands alongside CAT, WC and HELLO. Command
names and keyword names ignore case. Keywords may precede or follow positional
arguments. Quote a word that should be data rather than a keyword. Numeric
options are unsigned decimal; negative numbers and overflow are errors.

| Command | Arguments | Behavior |
| --- | --- | --- |
| CMP | `FROM TO` | Compare two files. Print the first differing zero-based byte offset, including unequal lengths. Equal files produce no output. |
| CKSUM | `[FILE]` | POSIX cksum CRC-32 and byte length, as two decimal numbers. Filename is not included in output. |
| HEXDUMP | `[FILE] [OFFSET n] [LENGTH n]` | Eight hexadecimal offset digits, up to sixteen hex bytes and printable ASCII per row. Defaults: offset zero, length up to 4,294,967,295 bytes. Offsets are skipped by reading, so pipes work. |
| HEAD | `[FILE] [LINES n]` | First ten lines by default. Zero prints nothing. Finishes without draining the rest of a pipe. |
| GREP | `PATTERN [FILE] [NOCASE] [INVERT] [NUMBER]` | Select literal matching lines; optionally fold ASCII case, invert selection, or prefix one-based line numbers. Empty pattern matches every line. |
| LIST | `[DIR] [NAMES]` | Enumerate a directory in disk order. Default output has directory markers and exact file sizes. NAMES emits bare names, one per line. |
| MORE | `[FILE]` | Forward-only pager. Space advances a page, Return one displayed row, Q finishes, and BREAK cancels. |

Commands with an optional FILE borrow Input when it is absent. LIST defaults to
the current directory. Files opened by the command are closed on every exit;
inherited streams remain owned by the Process. There is no wildcard expansion,
regex, multiple-file processing, recursive traversal or directory sorting.

Examples, using the current two-stage pipeline:

```text
HEAD STORY.TXT LINES 5
CAT STORY.TXT | GREP shell NOCASE
GREP shell STORY.TXT NUMBER
LIST NAMES | GREP .TXT
HEXDUMP STORY.TXT OFFSET=16 LENGTH=32
CKSUM <STORY.TXT
CMP STORY.TXT STORY.TXT
CAT LONG.TXT | MORE
```

The shell's default [PATH](shell.md#path) searches the current directory and then
SYS:, so commands remain available after CD. Qualified paths such as `SYS:HEAD`
bypass search.

## Bytes, text and limits

CMP, CKSUM and HEXDUMP process exact bytes. CKSUM uses polynomial `$04C11DB7`, an
initial zero CRC, least-significant length bytes and a final complement; it is
not the common reflected ZIP CRC variant. Byte counts are checked unsigned
32-bit values. HEXDUMP represents nonprintable ASCII bytes as dots.

HEAD, GREP and MORE recognize LF, CR, CRLF and ATASCII `$9B` as line endings.
They emit LF for a present delimiter and preserve an unterminated final line.
CRLF remains one delimiter across buffered reads. HEAD/GREP preserve embedded
NUL and other payload bytes; use TYPE or MORE for a sanitized console view.
A line may contain at most 1,024 payload bytes, excluding its delimiter. An
excess fails with ERROR_LINE_TOO_LONG instead of truncating or splitting it.
Shared input buffering uses 512 bytes per reader and does not read whole files.

MORE on interactive Output uses the associated foreground console for keys,
even with redirected or piped Input. It uses Output's actual dimensions, expands
tabs to eight-column stops and replaces other nonprintable bytes with dots.
Full rows wrap once; an immediately following line ending does not add a blank
row. The last display row is reserved for `--More--`. Consoles narrower than two
columns or shorter than two rows are unsupported. A prompt is shown only when
another display row exists. The initial implementation supports widths up to
80 columns. Input must be noninteractive, including an explicitly named source.
With noninteractive Output, MORE emits normalized text without prompts, key reads
or sanitizing payload bytes.

## Results and diagnostics

OK (0) means success. WARN (5), with IoErr zero, means CMP found a difference or
GREP selected no lines. ERROR (10) includes malformed arguments, I/O failures,
excessive text lines and BREAK. The shell retains primary and secondary results;
its [pipeline aggregation](shell.md#pipes) handles successful early consumers.

All ten commands accept a sole unquoted `?` for template help. For example,
`HEAD ? <STORY.TXT >NIL:` prints help on the console and consumes no data.
`GREP "?" STORY.TXT` searches for a literal question mark. An empty template,
as used by WC and HELLO, is displayed as `Arguments: (none)`.

On malformed arguments commands print their argument template to the
foreground console, independently of redirected Output. Headless callers still
receive the parser error through IoErr. `/A` marks required arguments, `/K`
keyword-only values, `/N` unsigned decimal values, and `/S` switches. The parser
has no dependency on the command's data Input. The shell then prints one error
explanation, such as `HEAD: Object not found (205)`, without changing the result.

These are bounded Exec816 commands inspired by Unix and AmigaDOS, not claims of
POSIX or Amiga command-line compatibility.
