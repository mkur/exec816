#!/usr/bin/env python3
"""Execute the hosted native-program acceptance matrix on the pinned emulator."""
import adapter_state as adapter
import argparse
import json
from pathlib import Path
import re

from native_program import (ROOT, PLATFORM_PIN, compiler, build, execute, emulator,
                            platform_files, require, verify_machine)


def global_word(bridge, image, name):
    # These are inspection labels; executable binding uses interface IDs above.
    matches = [symbol for symbol in image["data"] if symbol["kind"] == "global"
               and re.search(r"(?:^|_)"+re.escape(name)+r"(?:_|$)", symbol["name"], re.IGNORECASE)]
    require(len(matches) == 1 and matches[0]["size"] == 2, f"Ambiguous/missing CARD global: {name}")
    return int.from_bytes(bridge.memdump(matches[0]["address"], 2), "little")


def main(argv=None, toolchain=None, output=None, modes=(False, True)):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler-dir", type=Path, required=True)
    parser.add_argument("--bridge-dir", type=Path, required=True)
    parser.add_argument("--rom", type=Path, default=ROOT / "build/firmware/altirraos-816.rom")
    parser.add_argument("--case", help="Run one named case")
    args = parser.parse_args(argv)
    toolchain = compiler(args.compiler_dir) if toolchain is None else toolchain
    bridge_dir, rom = args.bridge_dir.resolve(), args.rom.resolve()
    platform_files(bridge_dir, rom)
    output = ROOT / "build/hosted-tests" if output is None else output
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    for optimize in modes:
        mode = "opt" if optimize else "raw"
        cases += [(f"hello-{mode}-i{initial_i}", "hello", optimize, 0, initial_i, False) for initial_i in (0, 4)]
        cases += [(f"transition-{point}-{mode}", "hello", optimize, point, 0, False) for point in range(1, 9)]
        cases += [(f"timer-irq-{mode}", "hello", optimize, 0, 0, True),
                  (f"console-inputs-{mode}", "console_inputs", optimize, 0, 0, False),
                  (f"console-bounds-{mode}", "console_bounds", optimize, 0, 0, False),
                  (f"stack-fault-{mode}", "stack_fault", optimize, 0, 0, False)]
    if args.case:
        cases = [case for case in cases if case[0] == args.case]
        require(cases, f"Unknown case: {args.case}")
    report = {"schema_version": 1, "platform": PLATFORM_PIN, "status": "running", "cases": []}
    report_file = output / (f"{args.case}.json" if args.case else "results.json")
    try:
        with emulator(bridge_dir, rom, output) as bridge:
            report["emulator_config"] = verify_machine(bridge, rom)
            for name, fixture, optimize, point, initial_i, timer_irq in cases:
                print(f"Running {name}...", flush=True)
                source = ROOT / ("examples/hello.act" if fixture == "hello" else f"tests/programs/{fixture}.act")
                program = build(toolchain, source, output / name, optimize, point, initial_i)
                result, screen = execute(bridge, program, 1 if fixture == "stack_fault" else 0, timer_irq)
                globals_seen = {}
                if fixture == "hello":
                    for symbol in ("status", "zeroWasClear"):
                        globals_seen[symbol] = global_word(bridge, program["image"], symbol)
                        require(globals_seen[symbol] == 1, f"Incorrect {symbol}: {globals_seen[symbol]}")
                    require(bytes(char-32 for char in b"EXEC816 NATIVE ACTION OK") in screen, "Console text absent")
                    require(result["native_nmi_count"] >= (2 if point else 1), "Native VBI did not run at test boundary")
                    require(result["clock_start"] != result["clock_end"], "OS clock did not advance")
                    if timer_irq:
                        require(result["native_irq_count"] > 0, "POKEY timer did not exercise native IRQ adapter")
                elif fixture == "console_inputs":
                    for symbol in ("banked", "outside", "crossing", "oversized", "empty"):
                        globals_seen[symbol] = global_word(bridge, program["image"], symbol)
                        require(globals_seen[symbol] == (1 if symbol == "empty" else 0xFF01),
                                f"Incorrect rejection: {symbol}={globals_seen[symbol]}")
                elif fixture == "console_bounds":
                    for symbol in ("maximal", "edge"):
                        globals_seen[symbol] = global_word(bridge, program["image"], symbol)
                        require(globals_seen[symbol] == 1, f"Valid boundary buffer rejected: {symbol}")
                    require(screen.count(33) == 253 and screen.count(34) == 1,
                            "Maximum-length/boundary console output differs")
                else:
                    globals_seen["entered"] = global_word(bridge, program["image"], "entered")
                    require(globals_seen["entered"] > 1 and result["fault_required"] > 0,
                            "Expected recursive stack overflow was not observed")
                    require(adapter.TASK0_STACK_FLOOR <= result["fault_s"] < adapter.TASK0_STACK_FLOOR+256, "Stack fault happened outside its expected bound")
                report["cases"].append({"name": name, "status": "pass", "build": program["build"],
                                        "observed": result, "globals": globals_seen})
        report["status"] = "pass"
    except Exception as error:
        report["status"] = "fail"
        report["error"] = str(error)
        raise
    finally:
        report_file.write_text(json.dumps(report, indent=2)+"\n")
    print(f"Passed {len(cases)} hosted cases; report: {report_file}")
    return report


if __name__ == "__main__":
    main()
