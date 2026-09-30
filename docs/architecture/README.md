# Architecture

[Documentation home](../README.md)

Read these in order for a system-level view:

1. [Overview](overview.md): kernel, libraries, workers and applications.
2. [Runtime model](runtime.md): Tasks, execution contexts and resource lifetime.
3. [Filesystems and disk I/O](filesystems.md): one shared filesystem worker,
   per-mount state, per-file state and the separate SIO worker.

More focused explanations:

- [Task capacity](task-capacity.md): Task slots and scarce bank-zero storage.
- [Sector cache](sector-cache.md): ownership, sizing and invalidation.
- [Filesystem progress](filesystem-progress.md): the shared progress vocabulary.

Exact public interfaces belong in the [reference](../reference/README.md).
The [library map](../../lib/README.md) connects these parts to source files.

## Task creation

- [CreateTask for Action! and C](create-task.md): one public creation operation,
  automatic pool selection and safe resource reuse, shared by Action! and C.
