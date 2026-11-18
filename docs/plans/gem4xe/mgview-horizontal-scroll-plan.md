# MGVIEW horizontal scroll repaint

[GEM plans](README.md) · [MGVIEW port](mgview-port-plan.md) ·
[Content-first scroll evidence](../../history/mgview-content-first.md)

**Status** — implemented. MGVIEW prepares the glyphs intersecting each damage
rectangle and bounds line lookup using its existing index. The matched arrow
runs, vertical control and covered-window checks are recorded in the
[development comparison](../../history/mgview-horizontal-scroll.md).

## Scope

MGVIEW already shifts overlapping pixels with `vro_cpyfm` and passes the
exposed rectangle to its draw callback. In the unobscured 616×200 viewport, a
one-column scroll copies 608×200 pixels and exposes an 8×200 strip. The copy uses
the same-parity VBXE path with a single display grant. `_my_draw` finds, expands and submits a
string for every intersecting row, then VDI clips it. The existing left/right
checks establish pixel correctness. The timing baseline covers up/down.
[Copy implementation](../../history/gem-copy-grant.md) · [Scroll tests](../../../tools/test_mgview.py#L150)

Keep MagiC's caller-owned UPDATE, visible-rectangle traversal and copy-then-draw
flow. Use the existing MGVIEW draw callback and standard `vs_clip`, `vr_recfl`
and `v_gtext` bindings. Compute the text needed for the supplied rectangle in
the viewer, where the document, tab width and line index are available. Make
the change in the recorded port patch and regenerate the build sources.
[MGVIEW source patch](../../../ports/magic/mgview/native.patch)

## 1. Measure left and right

- Reuse the existing optimized MGVIEW-only image with the 2 kHz mouse changes.
  Extend the existing MGVIEW observer to select horizontal motion and compare
  the full viewport against an oracle with a column offset. Use the same
  document, window geometry, mouse profile and emulator configuration for
  before and after. Drive both scrollbar arrows with short matched clicks and
  return to the starting column. Take one detailed trace pair and a few
  untraced timing pairs.
- Separate `vro_cpyfm`, line lookup and tab expansion, `v_gtext` conversion and
  drawing, background fills, thumb update and END_UPDATE. Count glyphs prepared
  and submitted, row text calls, display grants, and blitter lists. Record CPU
  charge and elapsed time separately. Report both the viewport and thumb
  scanout brackets at the observer's actual resolution.
- Keep one down/up pair as a control. Record the APP and resident image hashes
  with the results. Use the measurements to decide whether to pursue line
  lookup as well as string preparation.

## 2. Prepare only the intersecting glyphs

- In `_my_draw`, derive the first and past-last document columns from the
  damage rectangle, current horizontal shift and glyph width. Include a glyph
  cut by either edge, then let the current VDI clip limit its pixels. Clamp
  the interval to the 272-column display limit. Start the text call at the
  screen X of the first selected glyph and retain the existing row Y alignment.
- For each intersecting row, advance tabs from document column zero, write
  only glyphs in the selected interval to the existing scratch buffer, and
  stop expanding once the interval ends. A strip that begins inside an
  expanded tab starts with the appropriate spaces. Preserve literal tabs
  at width zero and embedded NUL as space. Due to tab alignment, the scan may
  still need the prefix before the first glyph. For a cell-aligned one-column
  strip, each nonempty text call should submit a single glyph.
- Clear the damaged rectangle with the existing background fill and skip rows
  with an empty glyph span. Check the redundant row-tail fills against the
  already cleared rectangle and remove them if the pixel oracle confirms the
  same result. Preserve behavior for ordinary redraw, covered fragments,
  page-sized jumps and viewport-before-thumb completion.
- If the remaining trace shows significant line-end lookup cost, use the
  existing next-line pointer or file end as the bound in a separate slice.
  Strip the terminating CR, LF or CRLF within that bound. Keep the existing
  line index representation and cover empty and unterminated final lines.

## 3. Verify and compare

- Rebuild only `MGVIEW.APP` and reuse the resident provider and native image.
  Require pixel-exact viewports and correct thumb position for left/right,
  the down/up control, and a page-sized jump. Include a short-line and tab
  fixture with tabs crossing both clip edges, tab width zero, embedded NUL,
  a long capped line and a partial-cell clip from a covered rectangle.
  Verify the exposed blank pixels and adjacent pixels outside the clip.
- Compare the same right/left timing pairs. Require fewer prepared glyphs
  and lower exposed-strip CPU cost. Report any difference in viewport or
  thumb scanout latency separately. Check clean exit, ordinary stack guards
  and reserved bank-zero bytes, including per-Task reservations. The expected
  reservation change is zero.
- If repeated row draws still dominate, record the measured cost before
  proposing a shared renderer change. GEM4XE's existing text-run optimization
  combines glyphs along one row. A multi-row primitive would need a separate
  architectural decision and a general consumer contract. Keep this pass at
  the focused development tier with MGVIEW alone.
  [GEM4XE text runs](https://github.com/slaapliedje/gem4xe/blob/2bf10f6788372dcfa94f6d9416e4b957eb4ce394/src/vdi/dev_vbxe.c#L1263-L1294)
