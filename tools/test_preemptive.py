#!/usr/bin/env python3
"""Qualify VBI preemption and deferred delivery on the pinned AltirraOS machine."""
import argparse
import json
from pathlib import Path
import struct

from native_program import (ROOT, PLATFORM_PIN, compiler, build, execute, emulator,
                            platform_files, require, verify_machine, run_to)
from test_cooperative import data, check as check_cooperative


def check(bridge, program, fixture, result, screen):
    observed = check_cooperative(bridge, program, "", result, screen)
    def expect(name, expected, words=False):
        observed[name] = data(bridge, program["image"], name, words)
        require(observed[name] == expected, f"{name}: {observed[name]}, expected {expected}")
    if fixture == "demo":
        expect("progress", [4, 4])
        expect("totals", [132, 144], True)
        expect("outputStatus", [1, 1], True)
        for letter in (65, 66):
            positions = [screen.find(bytes([letter-32, digit-32])) for digit in range(48, 52)]
            require(all(p >= 0 for p in positions) and positions == sorted(positions),
                    f"Task {chr(letter)} output missing/out of order")
        require(result["os_calls"] == result["forwarded_cops"] == 8, "OS calls lost")
        if program["build"]["probe_flags"] == 0x100:
            require(result["gateway_calls"] == 12, "Unexpected voluntary kernel calls")
    else:
        expect("results", [0, 0, 0, 0, 2], True)
        expect("peerPhase", [2])
    require(result["switches"] >= 2 and result["vbi_dispatches"] > 0, "No interrupt dispatch")
    require(result["vbi_count"] > 0 and result["clock_start"] != result["clock_end"], "OS VBI stopped")
    flags = program["build"]["probe_flags"]
    if flags != 0x100:
        observed["probe_switch_counts"] = []
        for task in (0, 1):
            before, after = struct.unpack("<HH", bridge.memdump(0x2080+task*32+20, 4))
            require((before == after) if flags & 4 else (after > before),
                    f"Incorrect I-mask preemption: task={task}, flags={flags:x}, {before}->{after}")
            observed["probe_switch_counts"].append([before, after])
    return observed


def without_preemption(bridge, program):
    """The same no-yield program must stall when the scheduler is cooperative."""
    bridge.bp_clear_all()
    bridge.boot(str(program["xex"]))
    run_to(bridge, program["labels"]["start"])
    bridge.bp_clear_all()
    bridge.frame(8)
    progress = data(bridge, program["image"], "progress")
    state = bridge.memdump(0x2000, 64)
    require(progress == [1, 0] and state[:2] == b"\xff\xff" and state[38:40] == b"\0\0",
            "Negative control unexpectedly made peer progress")
    require(int.from_bytes(state[2:4], "little") > 0, "Negative control had no native VBI")
    return {"progress": progress, "frames": 8, "status": "waiting for unscheduled peer"}


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
    output = ROOT / "build/preemptive-tests"
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    for optimize in (False, True):
        mode = "opt" if optimize else "raw"
        for fixture in ("demo", "locks", "negative"):
            cases.append((f"{fixture}-{mode}", fixture, optimize, 0, 0x100, 0, False, False))
        for flags in (0xC9, 0xD9, 0xE9, 0xF9, 0xCD):
            cases.append((f"registers-{flags:02x}-{mode}", "demo", optimize, 0, flags, 0, False, False))
        for point in range(1, 19):
            cases.append((f"nmi-{point}-{mode}", "demo", optimize, point, 0x100, 0, False, False))
        for signature in (1, 0x7F):
            cases.append((f"forward-{signature:02x}-{mode}", "demo", optimize, 0, 0x100, signature, False, False))
        cases.append((f"timer-irq-{mode}", "demo", optimize, 0, 0x100, 0, True, False))
        cases.append((f"keyboard-{mode}", "demo", optimize, 0, 0x100, 0, False, True))
    if args.case:
        cases = [case for case in cases if case[0] == args.case]
        require(cases, f"Unknown case: {args.case}")
    report = {"schema_version": 1, "platform": PLATFORM_PIN, "status": "running", "cases": []}
    report_file = output / (f"{args.case}.json" if args.case else "results.json")
    try:
        with emulator(bridge_dir, rom, output) as bridge:
            report["emulator_config"] = verify_machine(bridge, rom)
            for name, fixture, optimize, point, flags, signature, timer_irq, keyboard in cases:
                print(f"Running {name}...", flush=True)
                source = ROOT / ("tests/programs/preemptive_locks.act" if fixture == "locks"
                                 else "examples/preemptive.act")
                program = build(toolchain, source, output / name, optimize, point, cooperative=True,
                                preemptive=fixture != "negative", probe_flags=flags,
                                forward_signature=signature)
                if fixture == "negative":
                    result, observed = without_preemption(bridge, program), {}
                else:
                    def key_stimulus(machine):
                        require(machine.memdump(0x02FC, 1) == b"\xff", "Keyboard was not initially empty")
                        machine.key("A")
                    result, screen = execute(bridge, program, timer_irq=timer_irq,
                                             before_run=key_stimulus if keyboard else None)
                    observed = check(bridge, program, fixture, result, screen)
                    if point:
                        require(result["vbi_count"] >= 8, "NMI transition checkpoint not exercised")
                    if point == 18:
                        require(result["vbi_count"] >= result["native_nmi_count"]+8,
                                "VBI inside emulation-mode OS calls was not recorded")
                    if timer_irq:
                        require(result["native_irq_count"] > 0, "No hardware IRQ observed")
                    if keyboard:
                        observed["keyboard_code"] = bridge.memdump(0x02FC, 1)[0]
                        require(observed["keyboard_code"] != 255, "OS keyboard IRQ did not deliver input")
                report["cases"].append({"name": name, "status": "pass", "build": program["build"],
                                        "observed": result, "program": observed})
        report["status"] = "pass"
    except Exception as error:
        report["status"] = "fail"
        report["error"] = str(error)
        raise
    finally:
        report_file.write_text(json.dumps(report, indent=2)+"\n")
    print(f"Passed {len(cases)} preemptive cases; report: {report_file}")


if __name__ == "__main__":
    main()
