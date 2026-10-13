import subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class DesktopDragLifecycle(unittest.TestCase):
    def test_actual_gesture_code_with_failed_and_cancelled_publication(self):
        with tempfile.TemporaryDirectory(prefix='exec816-drag-') as tmp:
            binary=Path(tmp)/'lifecycle'
            result=subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                '-D__CALYPSI_CORE_65816__','-D__CALYPSI_DATA_MODEL_HUGE__',
                '-D__CALYPSI_CODE_MODEL_LARGE__','-D__simple_call=','-D__far24=',
                '-I',str(ROOT/'c/include'),str(ROOT/'tests/programs/desktop_drag_lifecycle.c'),
                '-o',str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            subprocess.run([str(binary)],check=True,capture_output=True,text=True)
