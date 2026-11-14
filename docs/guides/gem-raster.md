# GEM raster-copy sample

[Guides](README.md) · [VDI contract](../reference/gem-vdi.md) ·
[Implementation record](../history/gem-raster-copy.md)

Build and launch the OF816 desktop demo:

```sh
python3 tools/build_demo.py --gem-desktop --gem-widget --release-compiler \
  --output build/gem-raster/demo
build/gem-raster/demo/launch-altirra.command
```

Leave the five-second autoboot countdown alone. From Terminal, launch
`RUN SYS:C/RASTER.APP`. The sample starts paused. Its 304×96 work area shows
numbered colour rows. Space starts or pauses scrolling; Up/Down move one row;
Left/Right shift the image one pixel; M copies the visible image into a memory
form and back. Q or the close box exits. Drag the title, overlap the window
with Terminal and bring it forward through the Windows menu to check exposure.
On an Atari keyboard, cursor keys are Control with Minus, Equals, Plus and
Asterisk.

The optional Widget build also includes `PULSE.APP`, an independent Counter
with a 100 ms timer. To run both, enter `RUN SYS:C/PULSE.APP paint`, then
`NEWSHELL`, then `RUN SYS:C/RASTER.APP`. Each shell owns one background job.
Close Raster, enter `JOBS` and `EXIT` in its shell, close Counter, then enter
`JOBS` in the original shell. The four AES client slots include Desktop and Terminal.

The [application body](../../examples/gem-raster/main.c) uses conventional GEM
calls. It walks visible rectangles inside `wind_update`, confines both ends of
each scroll to one visible fragment and paints only the exposed strip. Small
fragments are repainted in full. `WM_REDRAW` reconstructs the same row model.
The M operation uses a caller-owned packed device-format MFDB, then restores
only visible destinations. The sample allocates 14,592 bytes for that form and
frees it on exit; a paused sample waits without a timer.

## Using the call

Include `<gem.h>` and rebuild against APP ABI 39. Coordinates are inclusive:

```c
WORD pxy[8]={x,y+8,x+w-1,y+h-1,x,y,x+w-1,y+h-9};
vro_cpyfm(vdi,S_ONLY,pxy,NULL,NULL);
```

This moves the source up eight pixels. It needs a private workstation and
UPDATE ownership. Walk visible rectangles and clip the destination before
drawing, as the sample does; the source is the actual screen image.
Paint the exposed bottom eight rows from the application model afterward.
`vro_cpyfm` returns synchronously. Errors from this void call are available
through `ExecAESDiagnostic()`.

Null forms denote the screen. Memory forms use `fd_stand=0`, `fd_nplanes=4`
and a sufficient `fd_wdwidth`, with packed hardware pixels and high nibble
first. These bytes describe Exec's device format; they are not portable ST
standard-planar image data. All sixteen logical modes are supported. See the
[current contract](../reference/gem-vdi.md#conventional-raster-copy) for clipping,
overlap, memory-only calls and unsupported formats.

Reproduce packaged development acceptance with:

```sh
python3 tools/test_gem_raster_sample.py --bundle build/gem-raster/demo \
  --output build/gem-raster/sample
```

The runner checks actual pixels against an independent row model, normal
coexistence and shutdown. It records aligned and different-parity completion
and checked scanout observations. A second run adds passive call CPU/elapsed
attribution using the verified relocated call markers from the first:

```sh
python3 tools/test_gem_raster_sample.py --bundle build/gem-raster/demo \
  --trace-from build/gem-raster/sample/results.json \
  --output build/gem-raster/sample-timing
```

These are development measurements, not a MagiC speed comparison or release
qualification. The runner checks the package hash and loaded call bytes before
using saved addresses. Upper-bank calls are observed passively; bank-zero
rendezvous points provide the debugger stops.
