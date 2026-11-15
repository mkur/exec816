# Contributing

[Documentation home](../README.md)

- [Build from source](building.md): prerequisites, pins and output files.
- [Style guide](style.md): readable Action! code and routine comments.
- [Testing policy](testing.md): focused development checks and release qualification.
- [Stack checks](stack-checks.md): checked builds and recorded build settings.
- [Contributor instructions](../../AGENTS.md): repository ownership and platform rules.
- [Licensing](../../LICENSING.md): GPL OS code, MIT interfaces/examples and third-party notices.
- [Roadmap](../roadmap.md) and [implementation plans](../plans/README.md).

Contributions follow the licence assigned to the affected files. Keep public
binding declarations and generated interface outputs under MIT; OS
implementation remains GPL-3.0-only. Update the licence map when adding a new
public binding outside an existing MIT directory. Preserve third-party notices.

## GEM architecture guidance

**Port MagiC's GUI structure and flow onto Exec; use GEM4XE as the primary
graphics code quarry.** This is the user's governing direction for the whole
GUI, including application state, windows, menus, forms, objects, resources,
workstations, input/events, ownership, operation boundaries and cleanup.
MagiC is the architectural baseline. Existing Exec GUI structure is implementation
inventory to assess against that baseline.

Exec supplies Tasks, signals, ports, native semaphores, timers, memory, DOS,
loading and device I/O. Preserve its normal Task preemption, platform ABI and
IRQ/NMI contracts. Start graphics work from existing GEM4XE implementations,
algorithms and artwork; adapt them to MagiC's structure and Exec's platform
contracts. Inspect the donor before writing a replacement. Keep donor revisions,
provenance and license obligations explicit.

Every architectural departure from MagiC must be brought to the user before
implementation. Prepare a concrete proposal that identifies the pinned MagiC
path, the required platform constraint, the affected semantics/flow, alternatives
and memory/coordination costs. Distinguish measured costs from estimates. A
written rationale is not itself approval. Existing code or a completed test
does not establish architectural necessity. Honor prior explicit user decisions
without requesting them again; routine choices and mechanical ABI adaptations
within the agreed model can proceed.

If a needed platform service is missing, report the capability and required
semantics, the existing public Exec services considered, and why they do not
suffice. Discuss a general platform-service proposal with the user before
implementation. Do not build a GUI-specific substitute, duplicate an Exec
mechanism in AES, or silently add a new platform service. AES still implements
GEM-specific application/window policy above those mechanisms. A mismatch in
the current GUI design is not, by itself, evidence of a missing Exec service.
The [reported platform gaps](../architecture/magic-exec-mapping.md#reported-platform-service-gaps)
track known lifecycle limitations without adopting GUI-specific substitutes.

The [current deviations to review](../architecture/magic-exec-mapping.md#current-deviations-to-review)
start with broad scene admission, the combined presenter, deferred simple frame
painting and additional paint/cache protocols. Their presence is not an adopted
porting decision. Current public contracts continue to describe supported
behavior until executable migration slices replace it. Keep slices small,
commit each passing slice, and use focused development checks rather than a
release matrix.

Consult the [MagiC source model](../architecture/magic.md) and
[MagiC-to-Exec mapping](../architecture/magic-exec-mapping.md). The
[mouse cross-check](../history/gem-mouse-magic-review.md) shows how this principle
changes a GEM4XE adaptation's ownership, bookkeeping and cleanup.

## Maintaining the documentation

Put instructions in guides, explanations in architecture, and current contracts
in reference. Link to the authoritative description rather than copying it.
Keep compiler revisions in the toolchain pins and build-specific sizes in build
reports; prose should link to those records.

Plans belong in `docs/plans`. Keep completed design discussions and measurements
in `docs/history`, with a link to the current contract where one exists. Preserve
qualification JSON and its original hashes and paths as historical evidence.
Changing a document does not update the qualification of the software.

Update the relevant section index when adding or moving a page. Check local
links, anchors, referenced build inputs and copied documentation assets after a
move. Documentation-only changes need content and link checks, not a system build.
