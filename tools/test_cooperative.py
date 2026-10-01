#!/usr/bin/env python3
"""Qualify two cooperative tasks using actual emitted bytes on pinned AltirraOS."""
import adapter_state as adapter
import argparse
import json
from pathlib import Path
import re
import struct

from native_program import (ROOT, PLATFORM_PIN, compiler, build, execute, emulator,
                            platform_files, require, verify_machine)


def data(bridge, image, name, words=False):
    matches = [s for s in image["data"] if s["kind"] == "global"
               and re.search(r"(?:^|_)"+re.escape(name)+r"(?:_|$)", s["name"], re.IGNORECASE)]
    require(len(matches) == 1, f"Missing/ambiguous inspection symbol: {name}")
    symbol = matches[0]
    raw = bytes(bridge.eval_expr(f'db(${symbol["address"]+i:x})') & 255
                for i in range(symbol["size"])) if symbol["address"] >= 65536 else \
        bridge.memdump(symbol["address"], symbol["size"])
    return list(struct.unpack("<"+"H"*(len(raw)//2), raw)) if words else list(raw)


def check(bridge, program, fixture, result, screen):
    observed = {}
    def expect(name, expected, words=False):
        observed[name] = data(bridge, program["image"], name, words)
        require(observed[name] == expected, f"{name}: {observed[name]}, expected {expected}")
    if fixture == "demo":
        expect("totals", [132, 144], True)
        expect("versions", [0x100, 0x100], True)
        expect("order", [0, 1]*4+[0]*4)
        expect("count", [8])
        lines = [bytes([letter-32, digit-32]) for digit in range(48, 52) for letter in (65, 66)]
        positions = [screen.find(line) for line in lines]
        require(all(p >= 0 for p in positions) and positions == sorted(positions), "Console order differs")
        require(result["switches"] >= 33 and result["os_calls"] == result["forwarded_cops"] == 8,
                "Missing switches or forwarded OS calls")
        require(result["native_nmi_count"] > 0 and result["clock_start"] != result["clock_end"],
                "OS VBI did not advance")
        require((result["return_s"], result["return_d"]) == (0x57FE, 0x2400), "Last task return mismatch")
        require(result["tasks"][8:10] == result["tasks"][24:26] == [0, 0], "Implicit task exit failed")
    elif fixture == "locks":
        expect("results", [0xFF12, 0, 0, 0, 0, 0, 0, 2], True)
        expect("peerPhase", [2])
        require(result["tasks"][8] == 42 and result["tasks"][24] == 99, "Explicit exit codes lost")
        require(result["switches"] == 3, "Nested locks did not defer/deliver exactly one switch")
    elif fixture == "pending":
        expect("overflow", [0xFF12], True)
        expect("peerPhase", [2])
        expect("writeStatus", [1], True)
        require(result["tasks"][8] == 2 and result["os_calls"] == 1, "OS return did not deliver pending yield")
    flags = program["build"]["probe_flags"]
    if flags != 0x100:
        snapshots = []
        for task in (0, 1):
            raw = bridge.memdump(adapter.PROBE0+task*32, 20)
            expected = struct.pack("<BHHHHBHHHHH", 0x12, 0x2200+task*0x200,
                                   0x78 if flags & 0x10 else 0x5678,
                                   0x34 if flags & 0x10 else 0x1234, 0xAB01, flags,
                                   0x47F8+task*0x1000, 0xBEEF, 0xFF10, 0xFF11, 0xFF12)
            require(raw == expected, f"Task {task} context: {raw.hex()}, expected {expected.hex()}")
            snapshots.append(raw.hex())
        observed["contexts"] = snapshots
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler-dir", type=Path, required=True)
    parser.add_argument("--bridge-dir", type=Path, required=True)
    parser.add_argument("--rom", type=Path, default=ROOT / "build/firmware/altirraos-816.rom")
    parser.add_argument("--case", help="Run one named case")
    args = parser.parse_args()
    toolchain = compiler(args.compiler_dir)
    bridge_dir, rom = args.bridge_dir.resolve(), args.rom.resolve()
    platform_files(bridge_dir, rom)
    output = ROOT / "build/cooperative-tests"
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    for optimize in (False, True):
        mode = "opt" if optimize else "raw"
        for fixture in ("demo", "locks", "pending"):
            cases.append((f"{fixture}-{mode}", fixture, optimize, 0, 0x100, 0, False))
        for flags in (0xC9, 0xD9, 0xE9, 0xF9, 0xCD):
            cases.append((f"registers-{flags:02x}-{mode}", "demo", optimize, 0, flags, 0, False))
        for point in range(1, 13):
            cases.append((f"nmi-{point}-{mode}", "demo", optimize, point, 0xF9 if point >= 9 else 0x100, 0, False))
        for signature in (1, 0x7F):
            cases.append((f"forward-{signature:02x}-{mode}", "demo", optimize, 0, 0x100, signature, False))
        cases.append((f"timer-irq-{mode}", "demo", optimize, 0, 0x100, 0, True))
    if args.case:
        cases = [case for case in cases if case[0] == args.case]
        require(cases, f"Unknown case: {args.case}")
    report = {"schema_version": 1, "platform": PLATFORM_PIN, "status": "running", "cases": []}
    report_file = output / (f"{args.case}.json" if args.case else "results.json")
    try:
        with emulator(bridge_dir, rom, output) as bridge:
            report["emulator_config"] = verify_machine(bridge, rom)
            for name, fixture, optimize, point, flags, signature, timer_irq in cases:
                print(f"Running {name}...", flush=True)
                source = ROOT / ("examples/cooperative.act" if fixture == "demo"
                                 else f"tests/programs/cooperative_{fixture}.act")
                program = build(toolchain, source, output / name, optimize, point,
                                cooperative=True, probe_flags=flags, forward_signature=signature)
                result, screen = execute(bridge, program, timer_irq=timer_irq)
                observed = check(bridge, program, fixture, result, screen)
                if point:
                    require(result["native_nmi_count"] >= 8, "NMI transition checkpoint not exercised")
                if timer_irq:
                    require(result["native_irq_count"] > 0, "No hardware IRQ observed")
                report["cases"].append({"name": name, "status": "pass", "build": program["build"],
                                        "observed": result, "program": observed})
        report["status"] = "pass"
    except Exception as error:
        report["status"] = "fail"
        report["error"] = str(error)
        raise
    finally:
        report_file.write_text(json.dumps(report, indent=2)+"\n")
    print(f"Passed {len(cases)} cooperative cases; report: {report_file}")


if __name__ == "__main__":
    main()
