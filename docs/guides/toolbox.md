# Command toolbox

[Guides](README.md) · [Shell](shell.md) · [Writing commands](commands.md)

The demo supplies eighteen loadable commands, including CAT, WC and HELLO. Command
names and keyword names ignore case. Keywords may precede or follow positional
arguments. Quote a word that should be data rather than a keyword. Numeric
options are unsigned decimal; negative numbers and overflow are errors.

| Command | Arguments | Behavior |
| --- | --- | --- |
| CMP | `FROM TO` | Compare two files. Print the first differing zero-based byte offset, including unequal lengths. Equal files produce no output. |
| CKSUM | `[FILE]` | POSIX cksum CRC-32 and byte length, as two decimal numbers. Filename is not included in output. |
| HEXDUMP | `[FILE] [OFFSET n] [LENGTH n]` | Eight hexadecimal offset digits, up to sixteen hex bytes and printable ASCII per row. Defaults: offset zero, length up to 4,294,967,295 bytes. Offsets are skipped by reading, so pipes work. |
| HEAD | `[FILE] [LINES n]` | First ten lines by default. Zero prints nothing. Finishes without draining the rest of a pipe. |
| TAIL | `[FILE] [LINES n]` | Last ten lines by default, after reading to EOF. Supports zero through sixteen lines; zero does not read Input. |
| GREP | `PATTERN [FILE] [NOCASE] [INVERT] [NUMBER]` | Select literal matching lines; optionally fold ASCII case, invert selection, or prefix one-based line numbers. Empty pattern matches every line. |
| LIST | `[DIR or PATTERN] [NAMES]` | Enumerate a directory in disk order or match `*`/`?` in the final path component. Default output has directory markers and exact file sizes. NAMES emits bare names. |
| MORE | `[FILE]` | Forward-only pager. Space advances a page, Return one displayed row, Q finishes, and BREAK cancels. |
| COPY | `FROM TO [APPEND]` | Copy one named input to an exact destination filename. Create/truncate by default; APPEND opens or creates, then seeks to EOF. |
| TEE | `FILE [APPEND]` | Copy Input to the named file and Output. Create/truncate by default; APPEND preserves existing content. |
| DELETE | `FILE ...` | Remove one to eight exact files or empty directories in order. |
| RENAME | `FROM TO` | Rename one entry within its current directory; an existing destination is an error. |
| MAKEDIR | `NAME` | Create one directory under an existing parent. |
| ASSIGN | `[NAME:] [TARGET]` | List, set/replace or remove a system-wide logical directory name. The target must be an existing directory. |
| PRIMES | `[PASSES n]` | Search through 10,000 in a six-row lower pane. Zero or omitted PASSES runs until cancelled. |

Commands with an optional FILE borrow Input when it is absent; CAT also accepts
up to eight exact files and concatenates them in order. LIST defaults to the
current directory. Files opened by the command are closed on every exit;
inherited streams remain owned by the Process. LIST matches ASCII letters
without case: `*` matches zero or more bytes and `?` one byte. Its parent path
must be exact. An unmatched pattern reports Object not found; an exact empty
directory succeeds. The shell does not expand patterns, and CAT and DELETE use
exact names. There is no regex, recursive traversal or directory sorting.

`PRIMES PASSES 1` finishes after one pass: 1,229 primes, ending at 9,973.
`PRIMES` runs in the foreground and physical BREAK stops it. `RUN PRIMES`
returns the prompt while calculation continues below it. Use JOBS to find its
identity, then `BREAK identity` to stop it. Closing the pane restores the full
shell display, including an edited line. See [background jobs](shell.md#one-background-job).

Examples, using the current two-stage pipeline:

```text
HEAD STORY.TXT LINES 5
CAT STORY.TXT | TAIL LINES 3
CAT STORY.TXT | GREP shell NOCASE
GREP shell STORY.TXT NUMBER
LIST NAMES | GREP .TXT
HEXDUMP STORY.TXT OFFSET=16 LENGTH=32
CKSUM <STORY.TXT
CMP STORY.TXT STORY.TXT
CAT LONG.TXT | MORE
CAT SYS:STORY.TXT SYS:STORY.TXT | WC
LIST SYS:*.TXT NAMES
```

The shell's default [PATH](shell.md#path) searches the current directory and then
C: (assigned to SYS:C at startup), so commands remain available after CD.
Qualified paths such as `C:HEAD` or `SYS:C/HEAD`
bypass search.

`ASSIGN DATA: WORK:DATA` lets commands use `DATA:FILE` independently of the
physical volume name. `ASSIGN DATA:` removes it, and `ASSIGN` lists current
mappings, including the boot C: assignment. Reassigning C: redirects the default
command search. See the [ASSIGN contract](../reference/assigns.md) for limits.

## Bytes, text and limits

CMP, CKSUM and HEXDUMP process exact bytes. CKSUM uses polynomial `$04C11DB7`, an
initial zero CRC, least-significant length bytes and a final complement; it is
not the common reflected ZIP CRC variant. Byte counts are checked unsigned
32-bit values. HEXDUMP represents nonprintable ASCII bytes as dots.

HEAD, TAIL, GREP and MORE recognize LF, CR, CRLF and ATASCII `$9B` as line endings.
They emit LF for a present delimiter and preserve an unterminated final line.
CRLF remains one delimiter across buffered reads. HEAD/TAIL/GREP preserve embedded
NUL and other payload bytes; use TYPE or MORE for a sanitized console view.
A line may contain at most 1,024 payload bytes, excluding its delimiter. An
excess fails with ERROR_LINE_TOO_LONG instead of truncating or splitting it.
Shared input buffering uses 512 bytes per reader and does not read whole files.

TAIL retains up to sixteen lines in a fixed ring in the loaded command's upper
RAM. It reads the whole input before emitting the selected suffix and produces
no suffix if reading fails or BREAK interrupts it. A read error remains an error
even when buffered bytes precede it. `LINES` above sixteen is an error.

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

## Writable files

Mount a writable volume such as the demo's disposable WORK: disk. SYS: remains
read-only. For example:

```text
MAKEDIR WORK:NOTES
COPY SYS:STORY.TXT WORK:NOTES/ONE.TXT
RENAME WORK:NOTES/ONE.TXT WORK:NOTES/TWO.TXT
CMP SYS:STORY.TXT WORK:NOTES/TWO.TXT
HELLO | TEE WORK:LOG.TXT
HELLO | TEE WORK:LOG.TXT APPEND
DELETE WORK:NOTES/TWO.TXT WORK:LOG.TXT
DELETE WORK:NOTES
```

COPY and TEE preserve exact bytes, including NUL and ATASCII. COPY uses a
16 KiB transfer buffer in the loaded command's upper-RAM BSS; TEE uses 512 bytes.
COPY opens its source before its output;
a missing source or a destination alias of the same open file cannot truncate
that file. Directory targets are errors: supply the complete destination name.
APPEND is an update open followed by an EOF seek; it also creates a missing file.

TEE writes each chunk to its file before forwarding it to Output. If either
write fails, it stops; the two destinations can contain different prefixes.
Both transfer commands honor BREAK and retain the first read, write or cleanup
error. Failed Close consumes its owned handle. Partial files can remain after
failure, and an earlier truncation is not undone.

DELETE validates every filename before its first deletion, then stops at the
first error or BREAK; earlier deletions remain. A quoted empty filename is an
error, and `*`/`?` are not expanded for mutations. MAKEDIR does not create
missing parents. DELETE does not recurse. RENAME does
not move entries between directories or volumes, or replace a destination.
These commands do not preserve copied metadata or provide atomic replacement.
See the [filesystem write contract](../reference/filesystem-writes.md) for disk
formats, sharing and recovery limits. No filesystem scan is added to mounting.

## Results and diagnostics

OK (0) means success. WARN (5), with IoErr zero, means CMP found a difference or
GREP selected no lines. ERROR (10) includes malformed arguments, I/O failures,
excessive text lines and BREAK. The shell retains primary and secondary results;
its [pipeline aggregation](shell.md#pipes) handles successful early consumers.

All supplied commands accept a sole unquoted `?` for template help. For example,
`HEAD ? <STORY.TXT >NIL:` prints help on the console and consumes no data.
`GREP "?" STORY.TXT` searches for a literal question mark. An empty template,
as used by WC and HELLO, is displayed as `Arguments: (none)`.

On malformed arguments commands print their argument template to the
foreground console, independently of redirected Output. Headless callers still
receive the parser error through IoErr. `/A` marks required arguments, `/K`
keyword-only values, `/N` unsigned decimal values, `/S` switches, and `/M`
collects up to eight positional strings. The parser
has no dependency on the command's data Input. The shell then prints one error
explanation, such as `HEAD: Object not found (205)`, without changing the result.

These are bounded Exec816 commands inspired by Unix and AmigaDOS, not claims of
POSIX or Amiga command-line compatibility.
