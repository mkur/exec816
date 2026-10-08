"""Keep optional GUI policy out of the standalone console dependency graph."""
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_console import reserve_metadata
import generate_heap
import generate_ports
from generate_memory import layout
from generate_tasks import policy_modules
from library_paths import ROOT, SUBSYSTEMS


class ConsoleLinkingTests(unittest.TestCase):
    def closure(self, generated):
        sources = {p.stem.upper(): p for group in SUBSYSTEMS
                   for p in (ROOT/'lib'/group).glob('*.act')}
        sources.update({p.stem.upper(): p for p in generated.glob('*.act')})
        seen = set()

        def imports(path):
            text = path.read_text()
            result = re.findall(r'^USE (\w+)', text, re.M)
            for name in re.findall(r'^INCLUDE "([^"]+)"', text, re.M):
                included = path.parent/name
                if included.is_file():
                    result.extend(imports(included))
            return result

        def visit(name, active):
            self.assertNotIn(name, active, 'Console module dependency cycle: '+str(active+[name]))
            if name in seen:
                return
            if name in sources:
                for child in imports(sources[name]):
                    visit(child, active+[name])
            seen.add(name)

        for root in ('CONSOLE', 'CONSOLEDRIVER', 'DOSPANE'):
            visit(root, [])
        return seen

    def test_standalone_and_desktop_link_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            for desktop in (False, True):
                with self.subTest(desktop=desktop):
                    memory = layout()
                    generate_heap.reserve_metadata(memory)
                    generate_ports.reserve_metadata(memory)
                    reserve_metadata(memory)
                    generated = policy_modules(Path(tmp), memory=memory,
                                               console=True, console_desktop=desktop)
                    modules = self.closure(generated)
                    optional = {m for m in modules if m.startswith(('DESK', 'AES', 'WIDGET'))
                                or m in ('LAYERS', 'LAYERTYPES', 'REGIONS')}
                    if desktop:
                        self.assertTrue({'DESKHOST', 'AESHOST', 'LAYERS', 'REGIONS'} <= optional)
                    else:
                        self.assertEqual(optional, set())
                    self.assertTrue({'CONSOLEHOST', 'CONSOLESCENE', 'CONSOLELOCKS',
                                     'CONSOLETILING', 'INPUT'} <= modules)


if __name__ == '__main__':
    unittest.main()
