"""Selected donor raster core, independent pixels and reproducible inputs."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from generate_gem_raster import generate,generate_shift,PORT


class RasterCore(unittest.TestCase):
    def test_fragment_order_against_whole_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            program=Path(folder)/'visible'
            subprocess.run(['cc','-std=c99','-O2','-I',str(PORT),
                str(ROOT/'tests/programs/gem_raster_visible.c'),'-o',str(program)],
                check=True,capture_output=True)
            subprocess.run([str(program)],check=True,capture_output=True)

    def test_independent_pixels_and_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            program=Path(folder)/'raster'
            subprocess.run(['cc','-std=c99','-O2','-I',str(PORT),
                str(ROOT/'tests/programs/gem_raster_core.c'),'-o',str(program)],
                check=True,capture_output=True)
            subprocess.run([str(program)],check=True,capture_output=True)

    def test_reproduction(self):
        source=ROOT/'build/gem-raster/upstream'
        names=json.loads((PORT/'inputs.json').read_text())['files']
        if not all((source/name).exists() for name in names):self.skipTest('Fetch pinned raster sources for reproduction')
        self.assertEqual((PORT/'core.h').read_text(),generate(source))
        self.assertEqual((PORT/'shift.s').read_text(),generate_shift(source))


if __name__=='__main__':unittest.main()
