# MyDOS read-only format

[Reference index](README.md) · [DOS API](dos.md)


Use the authors' technical documentation and source as the format reference,
not filename extensions or a newly invented filesystem. The technical guide
describes boot sectors 1–3, VTOC at 360 growing toward lower sector numbers,
root directory sectors 361–368, and a maximum 65,535 sectors of 256 bytes.
[MyDOS 4.50 Technical User Guide, section VII](https://lira.epac.to/DOCS-TECH/Retro%20Archives/ATARI%20Archive/MyDOS%204.50%20-%20Technical%20Manual.pdf)

The details below were checked against the
[authors' MyDOS 4.51 source archive](https://atariwiki.org/wiki/attach/MyDOS/Mydos451.zip):
`MDOS2.ASM` (`INITYP`, formatting, `MKDIR`), `MDOS3.ASM` (`SFDIR`, `CHASE`,
`BSECDS`, `MAPIOC`) and `MDOS4.ASM` (`FNDBIT`). Archive SHA-256:
`ca9a6ef43d6e12c44c965faf31ec092001c15c2eefcff2c45a62faea1ffb5724`.
Implementation fixtures must record their producing MyDOS version and hashes;
do not generalize this evidence to every patched MyDOS derivative.

### Directories and names

Each directory occupies eight consecutive sectors, with eight 16-byte entries
in the first 128 bytes of each sector: **64 entries**, including on 256-byte
media. The unused second half is not another eight entries. Subdirectory start
sectors come from their parent entries; directories are not ordinary linked
file chains. They do not contain a Unix-style on-disk `..` record.

| Entry bytes | Meaning |
| --- | --- |
| 0 | Status flags. |
| 1–2 | Sector count, little-endian; not a byte length. |
| 3–4 | First sector, little-endian. |
| 5–12, 13–15 | Space-padded eight-character basename and three-character extension. |

Interpret zero status as end of entries, `$80` as deleted, `$01` as an unclosed
file, `$10` as a subdirectory and `$20` as write protection. Normal closed DOS 2
and MyDOS files commonly have `$42` and `$46` respectively; a directory can
have status `$10` alone. Therefore testing `$40` as a universal existence bit
would lose directories. Accept only the documented combinations in the chosen
format profile; skip deleted/unclosed files and reject unsupported live types.
DOS 2.5's special enhanced-density flags require their own decoder and are
outside this milestone.

For a subdirectory validate count eight, its complete contiguous extent and
non-overlap with fixed metadata and ancestor directory extents. Resolve paths
iteratively, retaining the ancestor extents in upper RAM, with a 16-directory
depth bound. Detect repeated/overlapping ancestors instead of recursing until
the worker exhausts its small native stack.

Path resolution and current-directory behavior follow the [DOS contract](dos.md)
and [shell guide](../guides/shell.md). Components remain bounded 8.3 names; paths
are limited to 255 bytes excluding NUL. Wildcards and MyDOS CIO's colon/greater-than
subdirectory aliases are unsupported.

Preserve legal stored name bytes, including the original parser's `@`, `_` and
backtick characters. Prefer an exact byte match, then an ASCII case-insensitive
match for ordinary names. Reject an ambiguous folded match rather than selecting
one of two distinct stored entries arbitrarily. Enumeration returns stored case.
Unsupported/nonprintable names get an explicit name/format error. `Read` returns
unchanged bytes: ATASCII `$9B` is not translated to a host newline.

### File chains, size and seeking

For sector size `S`, the last three bytes are link-high, link-low and the number
of valid payload bytes. Maximum payload is 125 or 253. The next-sector encoding
is high-byte first, unlike the directory's little-endian first-sector field:

```text
entry flag $04 set: next = (link_high << 8) | link_low
entry flag $04 clear: next = ((link_high & 3) << 8) | link_low
                     require (link_high >> 2) == directory_entry_index
```

Choose this mode **per file**, not from sector size or the VTOC marker alone.
MyDOS can create a sixteen-bit-link file even on a small disk. Zero next-sector
means EOF; it does not make the last sector's payload empty. The directory entry
index is 0–63 within that file's parent directory, not its disk sector number.

Validate each sector before copying: number in range, outside fixed/known
directory metadata, valid byte count no greater than `S-3`, and correct file
number in ten-bit mode. Derive exact file length by summing validated payload
counts along the chain; multiplying the directory count by 125/253 is not an
exact length. Permit a final sector with zero payload for an empty file. Also
accept a canonical zero-count/zero-start empty entry. Nonzero count with zero
start, inconsistent EOF/count, out-of-range links and unsupported trailer formats
are corruption, not ordinary EOF.

Retain a traversal hop count and constant-space cycle detector per file cursor
across successive Reads. Every walk has a sector-count bound as well. This must
not reset on each small Read and thereby let a cyclic file produce bytes forever.
Backward seeks restart from the first sector with a fresh bounded traversal;
forward seeks can continue a validated cursor. Compute `OFFSET_END` by a bounded
walk when exact size is not yet known. Validate the directory sector count when
EOF is reached. Do not eagerly read an entire large file merely to open it.

Do not report these checks as a complete filesystem check: unrelated files may
cross-link, and corruption later in a chain may be discovered only after earlier
successful Reads. Whole-volume allocation audits and repair remain separate.

### VTOC and larger volumes

Read sector 360 when mounting and validate the selected format against supplied
geometry. For marker 2, the supported DOS 2-compatible layout uses one VTOC
sector. For MyDOS markers `m >= 3`, the bitmap occupies `m-2` logical 256-byte
pages, stored in descending sector order: one physical sector per page on
256-byte media, two on 128-byte media. Its first page includes a ten-byte header.
Reject an extent whose capacity cannot describe the configured volume or whose
reserved sectors overlap boot/root storage. Decode all arithmetic in 32 bits,
including bitmap positions for sectors near `$FFFF`.

The allocation bit for sector `n` is at logical bitmap byte `10 + n/8`, with
mask `$80 >> (n & 7)`; a set bit means free. VTOC bytes 1–2 describe the formatted
allocatable total and 3–4 the current free count, not the physical sector count.
No MyDOS bitmap update is needed to read files. Check header/range consistency
and reserve the complete VTOC extent in parser checks, but do not load the whole
bitmap permanently or require a full free-space audit before every Open.

Support links beyond sector 1023 and capacity up to the sixteen-bit sector
limit in the parser and block contract. Actual mountable geometries remain
limited to qualified peripheral profiles. An enhanced-density MyDOS volume is
not interchangeable with a DOS 2.5 enhanced-density volume just because both
have 128-byte sectors. Explicit `MYDOS` mount type and structural validation are
required; a marker or boot signature alone cannot identify every related format.
