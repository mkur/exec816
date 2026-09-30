# Independent SDFS fixtures

Regenerate with `python3 tools/make_sdfs_fixtures.py`. The pinned Altirra
filesystem library creates the initial volumes and independently extracts all
files. A 6502 verifier reads known bytes through original SpartaDOS X 4.50 CIO.
The cartridge is downloaded into `build/`, never distributed here.

`reference.json` records original-system results, producer/source hashes and
each fixture hash. Revision 2.0 fixtures are explicitly identified derivatives
of 2.1: the revision byte and 2.1 extension fields change; the common directory
and map structures do not. Both are read back through SpartaDOS itself.

Fixtures have three short boot sectors and 2,000 sectors total. Data includes
empty, partial, binary/ATASCII, fragmented, sparse and 70,003-byte files, nested
directories, and 300 files in one directory. Directory records and file data
cross sector/map boundaries. Host mutation helpers identify exact fields for
malformed-media tests; reference images remain immutable during those tests.

`namespace-128.atr` and `namespace-256.atr` add 1,110 deleted records before the
last MANY entry. The directory crosses a map page in either geometry while
retaining all 300 live files. Regenerate with `python3 tools/sdfs_namespace_fixtures.py`.
`namespace-reference.json` records source hashes, allocated map/data sectors,
independent Altirra validation and complete byte-identical extraction. These
are explicit derivatives, not another original-SDX execution record.
