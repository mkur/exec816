# Build cleanup and artifact restoration

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

Cleanup date: 2026-09-20.

The local build directory shrank from 33.20 GiB to 5.29 GiB, reclaiming about
27.91 GiB of allocated space.

Removed only regenerable Rust caches from the compiler worktrees and the old
Lists diagnostic build. Compiler source worktrees and native qualification
manifests remain in their original locations.

Archived 428 older build/test directories into
`build/cleanup-2026-09-20/historical-runs.tar.gz` (about 1.05 GiB). Every archived regular file was verified by SHA-256 before
its original directory was removed. The archive also preserves directories
and symlinks. `archive-files.json` records all 110,424 archive entries;
`manifest.json` records the archive checksum, original directory names,
removed caches and retained-tool checksums. These files are beside the archive
in `build/cleanup-2026-09-20/`. The archive and manifests remain local, ignored
build artifacts; committing these instructions does not include them in a fresh
clone.

The current compiler, emulator binaries/SDKs, firmware, research repository,
compiler-audit logs and complete `build/dos-slice10` outputs remain available.
All 18 current DOS result hashes match the committed qualification record.
The pinned compiler builds successfully and its executable hash matches that
record. All 117 host tests passed after cleanup. The cleanup itself changed no tracked
repository files.

## Restore a historical run

From the Exec816 repository root, restore just the run you need, for example:

```sh
tar -xzf build/cleanup-2026-09-20/historical-runs.tar.gz -C build dos-slice9
```

This restores `build/dos-slice9` and its contents. Other original directory
names are listed in `build/cleanup-2026-09-20/archive-directories.txt`. Tools that regenerate historical
qualification records may need the corresponding run directories restored first.

Restore all archived runs if necessary:

```sh
tar -xzf build/cleanup-2026-09-20/historical-runs.tar.gz -C build
```

Rust caches rebuild through Cargo when their historical checkouts are used.
