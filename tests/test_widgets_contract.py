"""Admission tests compile the selected donor code, not a second model."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from extract_gem_aes import extract,PORT
from generate_widgets import files,layout
from native_program import ROOT

class Widgets(unittest.TestCase):
    def test_generated_layout(self):
        for path,content in files().items():
            self.assertEqual(path.read_text(),content,str(path))
        self.assertEqual(layout()['Object']['size'],24)
        self.assertLessEqual(layout()['Tree']['size'],2048)

    def test_donor_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)
            a=extract(out/'a');b=extract(out/'b')
            self.assertEqual(a,b)
            command=['cc','-std=c99','-DWIDGET_HOST_TEST','-I'+str(ROOT/'c/include'),
                '-I'+str(PORT),'-I'+str(out/'a'),
                str(PORT/'widgets-model.c'),str(PORT/'widgets-graf.c'),
                *(str(out/'a'/n) for n in ('aes-objects.c','aes-graf.c','aes-form.c')),
                str(ROOT/'tests/programs/widgets_model.c'),'-o',str(out/'test')]
            subprocess.run(command,check=True,capture_output=True)
            result=subprocess.run([out/'test'],check=True,capture_output=True,text=True)
            self.assertIn('0 failures',result.stdout)

    def test_retained_transactions(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary);extract(out/'selected')
            command=['cc','-std=c99','-DWIDGET_STATE_HOST_TEST','-DWIDGET_STATE_TESTS','-I'+str(ROOT/'c/include'),
                '-I'+str(PORT),'-I'+str(out/'selected'),
                *(str(PORT/n) for n in ('widgets-model.c','widgets-state.c','widgets-graf.c')),
                *(str(out/'selected'/n) for n in ('aes-objects.c','aes-graf.c','aes-form.c')),
                str(ROOT/'tests/programs/widgets_state.c'),'-o',str(out/'test')]
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run([out/'test'],check=True,capture_output=True)
