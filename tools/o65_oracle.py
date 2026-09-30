"""Build a small adapter around the compiler's Rust oracle, outside its checkout."""
import json
from pathlib import Path
from native_program import ROOT, command


def build_oracle(toolchain):
    out = ROOT/'build/o65-reference'
    (out/'src').mkdir(parents=True, exist_ok=True)
    (out/'src/main.rs').write_text((ROOT/'tools/o65_oracle.rs').read_text())
    (out/'Cargo.toml').write_text('[package]\nname="exec816-o65-oracle"\nversion="0.1.0"\nedition="2024"\n'
                                  '[dependencies]\nactionc={path='+json.dumps(str(toolchain['directory']))+'}\nserde_json="1"\n')
    command(['cargo', 'build', '--manifest-path', out/'Cargo.toml', '--target-dir', toolchain['directory']/'target'])
    return toolchain['directory']/'target/debug/exec816-o65-oracle'


def reference(binary, file, **options):
    return json.loads(command([binary], input=json.dumps(dict(file=str(Path(file).resolve()), **options))))
