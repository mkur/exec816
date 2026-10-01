#!/usr/bin/env python3
"""Build and run bounded ROM boundary experiments through AltirraBridge."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT / "toolchain/altirra.json").read_text())
OUT = ROOT / "build/os-boundary"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(name, case, flags=0xCB, signature=0x50):
    prefix = OUT / name
    subprocess.run([
        "ca65", "-D", f"CASE={case}", "-D", f"FLAGS={flags}",
        "-D", f"SIGNATURE={signature}", "-l", str(prefix.with_suffix(".lst")),
        "-o", str(prefix.with_suffix(".o")),
        str(ROOT / "probes/os-boundary/probe.s"),
    ], check=True, timeout=30)
    subprocess.run([
        "ld65", "-C", str(ROOT / "probes/os-boundary/probe.cfg"),
        "-o", str(prefix.with_suffix(".bin")), "-Ln", str(prefix.with_suffix(".lbl")),
        str(prefix.with_suffix(".o")),
    ], check=True, timeout=30)
    labels = {}
    for line in prefix.with_suffix(".lbl").read_text().splitlines():
        _, address, label = line.split()
        labels[label.lstrip(".")] = int(address, 16)
    payload = prefix.with_suffix(".bin").read_bytes()
    xex = prefix.with_suffix(".xex")
    xex.write_bytes(struct.pack("<HHH", 0xFFFF, 0x3000, 0x3000+len(payload)-1)
                    + payload + struct.pack("<HHH", 0x02E0, 0x02E1, labels["start"]))
    return {"name": name, "case": case, "flags": flags, "signature": signature,
            "xex": xex, "labels": labels}


def settings(rom, pin=PIN):
    # Match Altirra's path-based external firmware identifier. No user profile
    # or mounted images are read, changed, or shared with the GUI emulator.
    firmware_id = 14695981039346656037
    for char in str(rom).lower():
        firmware_id = ((firmware_id ^ ord(char)) * 1099511628211) & ((1 << 64)-1)
    firmware_id |= 1 << 63
    return rf'''[User\AltirraSDL\Profiles]
"Defaults inited" = 1
"Current profile" = 964089481
[User\AltirraSDL\Profiles\Defaults]
"XL" = 964089481
[User\AltirraSDL\Profiles\3976D689]
"_Name" = "Exec816 probe"
"_Visible" = 1
"_Category Mask" = "hardware,firmware"
"_Saved Category Mask" = "hardware,firmware"
"Hardware mode" = 1
"PAL mode" = 1
"SECAM mode" = 0
"Mixed video mode" = 0
"Memory mode" = 2
"Memory: High banks" = {pin['machine']['high_banks']}
"Memory: MapRAM" = 0
"Memory: Ultimate1MB" = 0
"CPU: Chip type" = 2
"CPU: Clock multiplier" = {pin['machine']['clock_multiplier']}
"CPU: Shadow ROMs" = {int(pin['machine'].get('shadow_rom', False))}
"Kernel path" = "{rom}"
"Kernel type" = "kernelxl"
[User\AltirraSDL\Profiles\00000000]
"Kernel: Floating-point patch enabled" = 0
"Kernel: Fast boot enabled" = 0
"Devices: CIO burst transfers enabled" = 0
"CPU: Stop on BRK" = 0
"Memory: Randomize on EXE load" = 0
[User\AltirraSDL\Firmware\Available\{firmware_id:016X}]
"Name" = "Exec816 pinned AltirraOS 65816"
"Path" = "{rom}"
"Type" = "kernelxl"
"Flags" = 0
'''


@contextmanager
def emulator(bridge_dir, rom, output_dir=OUT, pin=PIN):
    sys.path.insert(0, str(bridge_dir / "sdk/python"))
    from altirra_bridge import AltirraBridge
    with tempfile.TemporaryDirectory(prefix="exec816-probe-") as temp:
        config = Path(temp) / "altirra"
        config.mkdir()
        (config / "settings.ini").write_text(settings(rom, pin))
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "emulator.log"
        with log_path.open("w") as log:
            process = subprocess.Popen([
                str(bridge_dir / "AltirraBridgeServer"), "--bridge=tcp:127.0.0.1:0",
                "--no-basic", "--machine=800XL", "--memory=64K", "--debugbrkrun",
            ], env={**os.environ, "XDG_CONFIG_HOME": temp}, stdout=log, stderr=log)
            bridge = None
            try:
                deadline = time.monotonic() + 15
                while True:
                    require(process.poll() is None, f"Emulator exited; see {log_path}")
                    match = re.search(r"token-file:\s*(\S+)", log_path.read_text())
                    if match:
                        break
                    require(time.monotonic() < deadline, "Emulator startup timed out")
                    time.sleep(0.05)
                previous_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(15)
                try:
                    bridge = AltirraBridge.from_token_file(match[1])
                finally:
                    socket.setdefaulttimeout(previous_timeout)
                bridge.pause()
                from bridge_memory import install
                install(bridge)
                # Only explicit platform pins request devices. Device insertion
                # may cold-reset the machine; finish it before loading any XEX.
                for device in pin.get('devices', []):
                    bridge.device_set(device['tag'], **device['settings'])
                    bridge.pause()
                for key, value in pin.get('startup_configuration', {}).items():
                    bridge.config(key, value)
                bridge.pause()
                yield bridge
            finally:
                if bridge:
                    bridge.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def run_to(bridge, address, frame_limit=360, timeout=15, condition=None):
    # This pinned bridge exposes only the 16-bit PC, including in native mode.
    # Stop at resident bank-zero rendezvous points; qualify PBR by the saved
    # native frame and by returning from code in a distinct bank.
    require(0 <= address <= 0xffff, 'Bridge PC cannot qualify an upper-bank breakpoint')
    # FRAME on this pinned server waits forever if a debugger breakpoint stops
    # before its counter expires. RESUME + bounded polling also works at stops.
    initial_frame = bridge.eval_expr("@frame")
    deadline = time.monotonic() + timeout
    bridge.resume()
    while time.monotonic() < deadline:
        regs = bridge.regs()
        # REGS can sample a running upper-bank instruction with this same low
        # word. A caller-supplied condition qualifies a rendezvous independently
        # of the truncated PC; do not pause/accept an unqualified sample.
        if (int(regs["PC"].lstrip("$"), 16) == address
                and (condition is None or bridge.eval_expr(condition))):
            bridge.pause()
            return regs
        if bridge.eval_expr("@frame") - initial_frame > frame_limit:
            break
        time.sleep(0.02)
    bridge.pause()
    raise RuntimeError(f"No breakpoint at ${address:04x} within {frame_limit} frames; {regs}")


def decode(data):
    word = lambda offset: int.from_bytes(data[offset:offset+2], "little")
    return {"a": word(0), "x": word(2), "y": word(4), "s": word(6), "d": word(8),
            "dbr": data[10], "p": data[11], "e": data[12],
            "os_s": word(16), "os_d": word(18), "os_dbr": data[20], "os_e": data[21],
            "vbi_count": data[22], "cop_route": data[23], "cio_status": data[24],
            "clock_before": data[25], "clock_after": data[26], "completion": data[63]}


def check(bridge, experiment, rom_bytes):
    name, case = experiment["name"], experiment["case"]
    labels = experiment["labels"]
    bridge.bp_clear_all()
    bridge.boot(str(experiment["xex"]))
    run_to(bridge, labels["start"])
    require(bridge.regs()["mode"] == "65C816", "Wrong CPU selected")
    # The I/O window and self-test RAM overlay prevent a single 16K ROM read.
    require(bridge.memdump(0xC000, 0x1000) == rom_bytes[:0x1000], "Wrong mapped kernel")
    require(bridge.memdump(0xD800, 0x2800) == rom_bytes[0x1800:], "Wrong mapped upper kernel")
    stop = PIN["rom"]["cop0_after_xce"] if case == 3 else labels["done"]
    bridge.bp_set(stop)
    regs = run_to(bridge, stop, 60)
    data = bridge.memdump(0x2000, 64)
    (OUT / f"{name}.result.bin").write_bytes(data)
    state = decode(data)
    require(state["completion"] != 0xEE, "Probe overlaps OS allocations")
    require(bridge.memdump(0x21F0, 0x120) == bytes([0xA5])*0x120, "Private DP domain changed")
    require(bridge.memdump(0x0100, 16) == bytes([0xA5])*16, "OS stack bottom guard changed")
    for address in (0x4700, 0x47F0, 0x4800):
        require(bridge.memdump(address, 16) == bytes([0xA5])*16, f"Stack guard changed: ${address:04x}")
    if case != 3:
        require(state["completion"] == 0xFF, "Missing completion marker")
    if case == 0:
        flags = experiment["flags"]
        expected = {"a": 0xABCD, "x": 0x34 if flags & 0x10 else 0x1234,
                    "y": 0x78 if flags & 0x10 else 0x5678, "s": 0x01EF,
                    "d": 0x2200, "dbr": 0x12, "p": flags, "e": 0}
        for key, value in expected.items():
            require(state[key] == value, f"{name}: {key}=${state[key]:x}, expected ${value:x}")
        require(state["vbi_count"] >= 1, "No VBI observed")
        require(state["clock_after"] != state["clock_before"], "OS VBI clock did not advance")
    if case in (0, 1):
        require(state["os_e"] == 1 and state["os_d"] == 0 and state["os_dbr"] == 0,
                f"Unexpected VBI domain: {state}")
        require(0x0110 <= state["os_s"] < 0x01EF, "VBI did not enter page-one stack")
    if case == 1:
        # Native interrupt return PC/PBR remains on the private stack. The ROM
        # has switched S to page one; stop in our VBI hook BEFORE unsafe RTI.
        frame = bridge.memdump(0x47EC, 4)
        require(frame[1:4] == struct.pack("<HB", labels["after_wait"], 0),
                f"Missing native return frame on private stack: {frame.hex()}")
        state["private_interrupt_frame"] = frame.hex()
        state["finding"] = "VBI enters page one while native return frame remains at $47ec"
        state = {key: state[key] for key in ("os_s", "os_d", "os_dbr", "os_e", "vbi_count",
                                            "private_interrupt_frame", "finding")}
    if case == 2:
        require(state["cio_status"] == 1, f"CIO failed: {state}")
        require((state["s"], state["d"], state["dbr"], state["e"]) == (0x01EF, 0x2200, 0x12, 0),
                f"COP0 did not restore caller domain: {state}")
        screen_address = int.from_bytes(bridge.memdump(0x58, 2), "little")
        screen = bridge.memdump(screen_address, 960)
        (OUT / f"{name}.screen.bin").write_bytes(screen)
        expected = bytes(c-32 for c in b"EXEC816 OS BOUNDARY OK")
        require(expected in screen, "Expected console text absent from screen RAM")
        state["console"] = "EXEC816 OS BOUNDARY OK"
        require(state["vbi_count"] >= 1 and state["clock_after"] != state["clock_before"],
                "No completed OS VBI during console experiment")
    if case == 3:
        require(rom_bytes[stop-0xC000-2:stop-0xC000] == bytes([0x38, 0xFB]),
                "Pinned COP0 entry is not SEC/XCE")
        target = bridge.memdump(0x47EE, 2)
        require(int.from_bytes(target, "little") == labels["done"], "Missing private COP0 target")
        require(state["s"] == 0x47ED, "Incorrect native stack before COP0")
        stack_low = int(regs["S"].lstrip("$"), 16)
        require(stack_low == 0xE3, "Unexpected stack depth at ROM COP0 transition")
        state = {"native_s_before_cop": state["s"], "stop_pc": stop,
                 "stack_low_after_xce": stack_low, "private_target": target.hex(),
                 "finding": "Stopped immediately after ROM SEC/XCE, before fetching target from wrong stack"}
    if case == 4:
        require(state["cop_route"] == 1, f"ROM routing changed: {state}")
        require((state["a"], state["x"], state["y"], state["s"], state["d"], state["dbr"]) ==
                (0xABCD, 0x1234, 0x5678, 0x01EF, 0x2200, 0x12), f"COP dispatcher corrupted context: {state}")
        state["finding"] = f"COP #${experiment['signature']:02x} routed to VCOP0"
    return {"name": name, "status": "pass", "image_sha256": sha256(experiment["xex"]),
            "guards": "private DP and both stack boundaries intact", "observed": state}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-dir", type=Path, help="AltirraBridge distribution, including sdk/python")
    parser.add_argument("--rom", type=Path, default=ROOT / "build/firmware/altirraos-816.rom")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--case", help="Run just one named experiment")
    args = parser.parse_args()
    for command in ("ca65", "ld65"):
        require(shutil.which(command), f"Required assembler tool missing: {command}")
    OUT.mkdir(parents=True, exist_ok=True)
    experiments = []
    for widths in (0, 0x10, 0x20, 0x30):
        for masked in (0, 4):
            flags = 0xCB | widths | masked
            experiments.append((f"vbi-p{flags:02x}", 0, flags, 0))
    experiments += [("vbi-private-stack", 1, 0xCB, 0), ("cop0-console", 2, 0, 0),
                    ("cop0-private-stack", 3, 0, 0)]
    experiments += [(f"cop-route-{signature:02x}", 4, 0, signature) for signature in (0, 0x50, 0x7F)]
    if args.case:
        experiments = [case for case in experiments if case[0] == args.case]
        require(experiments, f"Unknown experiment: {args.case}")
    built = [build(*experiment) for experiment in experiments]
    if args.build_only:
        print(f"Built {len(built)} probe images in {OUT}")
        return
    require(args.bridge_dir is not None, "Provide --bridge-dir or use --build-only")
    bridge_dir, rom = args.bridge_dir.resolve(), args.rom.resolve()
    require(sha256(rom) == PIN["rom"]["sha256"], "ROM hash differs from toolchain/altirra.json")
    require(sha256(bridge_dir / "AltirraBridgeServer") == PIN["emulator"]["sha256"],
            "Emulator hash differs from toolchain/altirra.json; qualify new pins explicitly")
    report = {"schema_version": 1, "platform": PIN, "status": "running",
              "probe_source_sha256": sha256(ROOT / "probes/os-boundary/probe.s"),
              "experiments": []}
    report_path = OUT / (f"{args.case}.json" if args.case else "results.json")
    try:
        with emulator(bridge_dir, rom) as bridge:
            report["emulator_config"] = bridge.config()
            for key, value in {"machine": "800XL", "memory": "64K", "video": "pal",
                               "basic": False, "highbanks": 0, "addons": "off"}.items():
                require(report["emulator_config"].get(key) == value, f"Incorrect machine setting: {key}")
            for experiment in built:
                print(f"Running {experiment['name']}...", flush=True)
                report["experiments"].append(check(bridge, experiment, rom.read_bytes()))
        report["status"] = "pass"
    except Exception as error:
        report["status"] = "fail"
        report["error"] = str(error)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Passed {len(built)} experiments; report: {report_path}")


if __name__ == "__main__":
    main()
