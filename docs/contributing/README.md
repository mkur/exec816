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
