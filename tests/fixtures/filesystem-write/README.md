# Native filesystem write fixtures

These four ATRs contain only generated test data. Original MyDOS 4.50 and
SpartaDOS X 4.50 perform create, append, in-place update, truncate, same-directory
rename, file deletion, directory creation/removal and nested-file creation.
The same native program reopens every remaining file and compares its bytes
against independently generated expected data. The host then verifies the
persisted ATR's allocation and exact contents.

[reference.json](reference.json) pins every image, original DOS binary,
verification program, ROM/emulator configuration and expected file hash.
[make_write_fixtures.py](../../../tools/make_write_fixtures.py) creates disposable
boot/media copies; no Exec816 filesystem implementation participates. Its SDFS
boot/empty-volume builder uses the pinned independent Altirra writer. Native
SpartaDOS performs all target-volume file mutations.

The producer binaries and their source URLs are pinned in
[mydos_producer.py](../../../tools/mydos_producer.py) and
[make_sdfs_fixtures.py](../../../tools/make_sdfs_fixtures.py). They are downloaded
only into build directories and are not included in these test-data ATRs.
SDFS directory operations use XIO 42/43, as documented in sections 6.3.11–12 of
the [SpartaDOS X guide](https://atariwiki.org/wiki/attach/SpartaDOS/SpartaDOS%20X%204.48%20User%20Guide.pdf).

Both native producers retain an allocation for an empty file: one MyDOS data
sector with zero used bytes, or one SDFS map with all data pointers zero.
The existing readers also accept their documented zero-start empty forms.
Keep originals immutable; all implementation tests mutate copies. These images
establish native format behavior, not Exec816 write qualification.
