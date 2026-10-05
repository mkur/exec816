# Two-tier testing policy

Use development checks by default. Full qualification is a separate release
activity; ordinary edits and commits do not trigger the complete matrices.
This policy changes when tests run, not their assertions or acceptance limits.

| Tier | When | Scope |
| --- | --- | --- |
| Development | After a coherent code change, before committing | Host checks, affected generated definitions, and focused emitted-code regressions for changed behavior. Documentation-only changes need content/link checks. |
| Release qualification | On the release candidate, before publishing new platform qualification, or when explicitly requested | Complete applicable functional, failure, placement, concurrency, timing and observation/replay matrices on frozen inputs. |

## Development checks

Run the host suite for code changes:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

The public Git history starts with a source snapshot. Host tests still validate
the retained qualification records and their failure cases, but skip four source
audits when the pre-publication commits are unavailable. Maintainers with the
private development archive can also run those audits:

```sh
EXEC816_HISTORY_REPO=/path/to/exec816-private \
  python3 -m unittest discover -s tests -p 'test_*.py'
```

An explicitly selected archive must contain the required commits; missing or
mismatched inputs fail the audit. These historical checks do not qualify the
current build.

Run the relevant generators with `--check` when their ABI inputs or generated
outputs change. Select the smallest existing native fixture that exercises the
changed behavior and its important failure/cleanup path. Preserve raw/optimized
coverage for compiler-facing behavior and the fixture's stack/domain, ownership
and OS-restoration checks. Use the default pinned machine and kernel bank;
alternate banks, sector sizes and baud profiles belong to release qualification
unless the change specifically affects them.

Examples of focused selection, not a mandatory suite for every change:

| Changed behavior | Development coverage |
| --- | --- |
| Desktop windows, clients and interaction | `test_desktop.py`, `test_desktop_presentation.py`, `test_desktop_apps.py` (raw/optimized); physical `test_desktop_drag.py`, `measure_desktop.py`; selected startup/fault tests in `test_desktop_startup.py` and `test_desktop_fault.py`. `test_demo.py --boot-smoke` cold-boots the exact `build_demo.py --desktop` package. See [desktop evidence](../history/desktop.md) for actual coverage and open timing targets. |
| Layers/region geometry and drawing lifetimes | `tools/test_layers.py --mode raw/opt --output DIR`: independent region and scene pixel oracles, incremental software painting/copy fallback, stale/busy/exhausted transactions, bank-crossing scene storage, guards and OS return. This does not exercise VBXE window presentation. |
| Retained console cells or controls | `tools/test_console_core.py` in raw/optimized mode. |
| Bulk bitmap output | `tools/test_console_batch_core.py`, `tools/test_console_bitmap_scroll.py --batch`, and `tools/test_console_batch_lifetime.py` in raw/optimized mode; selected bitmap fault/control and fairness cases. `tools/measure_bitmap_cat.py` and `tools/measure_console_batch_load.py` record performance separately. |
| Screen presentation or cursor | `tools/test_console_display.py`; add `tools/test_console_scroll.py` when changing scrolling or its cost. |
| Cooked line state | `tools/test_cooked_line.py`; a physical CON: case when device integration changes. |
| Shell input/session integration | `tools/test_shell_core.py --smoke`; the affected command, redirection or lifetime scenario for the specific change. |
| Console windows | `tools/test_console_windows.py` for lifetime; `tools/test_console_focus.py` for display/routing; the bounded `tools/test_console_fairness.py` case when worker scheduling changes. |
| Foreground cancellation | The affected console/filesystem cancellation fixture or one `tools/test_shell_break.py` scenario; expand when the failure crosses those boundaries. |
| Resident Process lifetime | `tools/test_process_lifetime.py` in raw/optimized mode: arguments/results, setup rollback, slot leases, collection and reuse. |
| Task retention or resident notification | `tools/test_task_lifetime.py --mode raw/opt`: copied/stale leases, removal holds, producer lifetime and last-application notification; one image per mode. |
| SIO worker lifetime | `tools/test_sio_lifetime.py --mode raw/opt`: concurrent opens, startup/teardown holds, stop/open, restart and last-application shutdown. Add the startup rollback cases from `test_sio_recovery.py` when admission or binding changes. |
| Process inheritance and teardown | `tools/test_process_inheritance.py` in raw/optimized mode: shared streams/directory, foreground handoff, eight live Tasks, exact cancellation and retained ownership on cleanup failure. The same built image exercises all six scenarios. |
| o65 validation or relocation | The affected cases in `tools/test_o65_validation.py` or `tools/test_o65_execution.py`, in raw/optimized mode. |
| Disk command or shell dispatch | `tools/test_o65_shell.py` in raw/optimized mode for physical input, arguments, redirection, errors and foreground BREAK. The optimized case also runs CAT-to-WC; the raw instrumented image lacks heap space for two aligned Images. Both use the pinned paced emulator. This full physical session is a longer focused regression. |
| WC counting | `tools/test_wc.py` in raw/optimized mode uses controlled streams for text boundaries, wide counts, errors and BREAK. `tools/test_wc_shell.py` is a short disk-loaded smoke test; `--kernel-build` can reuse an unchanged `test_o65_shell.py` kernel build. |
| Command toolbox | `tools/test_read_args.py`, `tools/test_toolbox.py` and `tools/test_toolbox_console.py` with `--case raw/opt`; controlled emitted command bodies plus real nondefault-console lifetime checks. `tools/test_toolbox_shell.py` covers loaded commands, warnings, early consumers and physical MORE controls; `--outcomes-only` selects error precedence and `--pager-key` selects one control. `--reuse` requires an unchanged recorded kernel build. |
| Command usability | `tools/test_command_path.py`, `tools/test_command_faults.py` and `tools/test_command_fault_io.py` with `--case raw/opt` cover lookup/mutation and formatting/I/O boundaries. `tools/test_command_usability_shell.py` checks real PATH, help, redirection, pipeline diagnostics and recovery; `tools/test_of816.py` checks the packaged acceptance interaction on D1 and D2. |
| IRQ/NMI, scheduling, SIO, ABI or allocation/ownership | The direct regression plus a targeted interrupt/coexistence or lifetime case that exercises the affected boundary. |
| Calypsi C binding | `tools/test_calypsi.py --mode raw/opt --context` for emitted C layouts, COP marshalling, active C preemption, DP preservation and cleanup; the optimized standalone message example for its console flow. |
| Hosted GEM C subset | `tools/test_gem_vdi.py --slice g1 --mode raw/opt` for extraction, emitted C entry/layout, recording callbacks, two large Tasks, VBI context and cleanup. The linked VBXE backend remains inactive. |
| Hosted GEM drawing | `tools/test_gem_render.py --mode raw/opt --output DIR`: real service/VDI/device pixels, independent/upstream models, font/palette/scanout, clipping/coordinate limits, bank-boundary packets, batch rejection and device-fault reopening. `--production-control` uses original hardware status reads with the documented snapshot observers. |
| Hosted GEM service | `tools/test_gem_vdi.py --slice g2 --mode raw/opt` for emitted wire layouts, IPC, batch validation, sequence/session limits, Task retention, queued/active stop and allocation rollback. Uses a fixture backend; no graphics is linked. |
| Hosted VBXE adapter | `tools/test_gem_display.py --mode raw/opt --output DIR` for display leases, VRAM/CPU readback, physical SIO, NMI mapping boundaries, independent busy/VCOUNT timeouts, wrap and reset-required recovery; see [scope](../../platform/altirraos/vbxe.md). |
| OF816 XEX boot monitor | `tools/test_of816.py`: five-second autoboot and clock wrap, final-second cancellation, Forth input, guarded handoff to the standard shell, disk HELLO and CAT/WC pipeline, EXIT/ownership/OS restoration, BYE and occupied-IOCB exits. An explicitly selected Calypsi bundle retains its C-message smoke scope. |
| Sector cache | `tools/test_block_io.py` raw/optimized fixture plus allocation rollback and one real SIO case; warm `test_filesystem_active_cancel.py --suite middle --warm`; `test_dos_offline.py --case opt` for cached data behind an unavailable bus. `measure_sector_cache.py --prepare` and `measure_cache_commands.py` measure the selected read/command working sets. |
| Filesystem writes | `tools/test_filesystem_write.py`, `test_filesystem_write_edges.py` and `test_filesystem_write_lifetime.py` select public operations, local rejection and commit/finalization boundaries. `test_filesystem_native_interop.py` and `test_filesystem_roundtrip.py` verify persisted files through original DOS and back in Exec. `test_filesystem_write_shell.py` covers redirection and late Close failures on both formats. See the [development record](../history/filesystem-write-implementation.md) for exact selected cases and observer scope. |
| Boot service settings | `tools/test_boot_config.py --mode raw/opt --output ...`: one build per mode, exercising default/overridden/invalid records through the real loader and captured settings independent of retired boot storage. |

The development tier should take seconds to a few minutes, rather than launching
an exhaustive matrix. That is a workflow target, not a measured time guarantee
or permission to skip a required regression. If a change needs a long targeted
case, explain why and run that case without automatically expanding every axis.
Avoid large trace-based fixtures for changes that a smaller native test covers.

During iteration, rerun the failing or affected case first. Once it passes,
finish the selected development checks. Do not repeat passing checks unless
their inputs changed, a failure revealed broader impact, or a concern remains
unresolved. A documentation update after successful code checks requires only
the documentation checks.

## Release qualification

Freeze the source, compiler, ROM, emulator, configuration, media and observer
inputs before the complete applicable matrix. Include the existing raw/optimized
and alternate-placement coverage, allocation/failure and lifetime cases,
eight simultaneously live Tasks, full-file workloads, supported transport
profiles, timing limits and identical-image/input replay where required.
Do not substitute smoke results for any required qualification case.

Publish qualification records only after their complete coverage and freshness
checks pass. Reuse an execution result only when all relevant inputs match;
historical records retain their original scope and do not qualify changed code.
An ordinary implementation commit may state "development checks passed;
release qualification pending." It must not mark a timing/platform acceptance
gate qualified until the corresponding deeper tests pass. Existing acceptance
matrices in implementation plans specify qualification, not an instruction to
rerun every case after each intermediate commit.

The o65 L4 matrix uses `tools/test_o65_integrated.py --trace`: one measured
concurrent-I/O workload, its identical-image replay without tracing, and a full
functional run covering admission/allocation failures, cancellation and reuse.
Build raw and optimized 128-byte FASTEST125 bases once. Use `--from-build` for
256-byte FASTEST125, 256-byte profile 4 (57.6 kbaud), and 128-byte profile 2
(STOCK810); this changes only the serialized mount descriptor, preserving emitted
code and provider addresses. Bank-3 functional cases need their own builds.
`tools/test_o65_large.py` covers multi-bank placement and loaded stack overflow
for raw and optimized commands on the optimized resident kernel. This leaves
the four contiguous heap banks needed by its two-placement fixture; raw-loader
coverage remains in the validation and execution fixtures.
`tools/test_o65_disk_fault.py --phase seek` and `--phase read` cover real peripheral
errors before the length seek and after staging allocation.
`tools/record_o65_qualification.py` rejects incomplete matrices or changed native
inputs before assembling their evidence. These are release checks, not routine
requirements for every loader edit.

## Cost and reporting

Keep routine development outputs separate from qualification artifacts. Prefer
bounded fixtures and tracing only where the selected test needs it; do not
disable observers that an existing timing oracle requires. Report the selected
tier, case count, result and unresolved coverage briefly, and inspect detailed
logs for failures rather than printing successful traces into the conversation.
Record elapsed time and artifact size when assessing which fixtures need a
smaller development variant. Existing artifacts are not deleted by this policy;
disk cleanup remains separate work.

This policy adds no target code, worker or memory reservation. Fixed and per-Task
reserved bank-zero deltas are both zero.
