# Original MagiC MGVIEW port execution

[Plan](../plans/gem4xe/mgview-port-plan.md) · [GEM history](README.md) ·
[Source selection](../../ports/magic/mgview/README.md)

This is development work, not release qualification. The user requested minimal
testing: focused original-viewer/Counter checks, no release matrix and no routine
QED execution. The plan's larger acceptance inventory remains optional deeper
coverage, rather than a claim that every failure/timing case has run.

## MP1: first viewer

The pinned original MGVIEW, MGWIND and WINDOWS modules build as a disk-loaded
APP using the current argument/GEMDOS runtime. Pure C integer and event layouts,
rectangle calls, workstation/error helpers and the assembly scanner are adapted.
The common rectangle module now also serves QED; no APP/kernel ABI is added.
Loading publishes only fully allocated documents, terminates file data, supports
empty input and frees window records. Navigation initially uses full redraw.

The draw buffer uses 273 upper BSS bytes per image. Reserved bank-zero changes:
fixed 0, root 0, kernel 0, private idle 0 and every public Task 0, including
guards, alignment and unused reserved capacity.

Development checks: `build/mgview-dev/model-raw/results.json` and `model-opt/`
each pass 30 original-parser/callback/rectangle checks, with emitted WINDOW
layout 338 bytes and four-byte huge pointers. `build/mgview-dev/smoke/results.json`
passes four loaded Process lifetimes (three MGVIEW, one Counter), 25 native
checks and exact 123,200/4,096-pixel populated/empty viewports. Quoted path,
physical Ctrl-U, no-argument exit, stop, heap restoration and stack/domain guards
are covered. The largest touched 1,312-byte public pool is 816 bytes in this
fixture; it leaves 240 untouched bytes above the 256-byte interrupt floor.

The inlining-enabled C build opened a blank viewport despite correct input,
index, metrics, UPDATE and visible enumeration. Temporary observations changed
that result. The clean optimized application passes with `--no-inline` applied
uniformly to its source units, matching QED's existing
[Calypsi 5.18 restriction](../plans/gem4xe/qed-editing-design.md#memory-stack-and-evidence).
No drawing-policy or actionc change accommodates that compiler issue. The
uninstrumented APP is 27,853 serialized bytes with a 66,786-byte loaded span
and 1,020 BSS bytes at this slice; these include ordinary runtime state.
