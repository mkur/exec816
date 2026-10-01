#!/usr/bin/env python3
"""Compile a native Action! image and package it with the hosted XEX launcher."""
import adapter_state as adapter
from library_paths import module_args, read_source
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess

from os_boundary import ROOT, PIN as PLATFORM_PIN, emulator, require, run_to, sha256

COMPILER_PIN = json.loads((ROOT / "toolchain/actionc.json").read_text())
APP_BASE, APP_LIMIT = 0x6000, 0x9000
MAX_IMAGE_JSON = 4 * 1024 * 1024


def command(args, **kwargs):
    kwargs.setdefault('timeout', 120)
    return subprocess.run([str(arg) for arg in args], check=True, text=True,
                          stdout=subprocess.PIPE, **kwargs).stdout


def read_build(output):
    """Replay an explicitly selected, hash-verified native build without emission."""
    output = Path(output).resolve()
    record = json.loads((output/'build.json').read_text())
    require(sha256(output/'program.xex') == record['xex_sha256'], 'Changed replay XEX')
    require(sha256(output/'program.a816.json') == record['image_sha256'], 'Changed replay image')
    labels = {}
    for name in ('hosted.lbl', 'loader.lbl'):
        for line in (output/name).read_text().splitlines():
            fields = line.split()
            labels[fields[2].lstrip('.')] = int(fields[1], 16)
    return dict(output=output, build=record, labels=labels, xex=output/'program.xex',
                image=json.loads((output/'program.a816.json').read_text()))


def compiler(directory, allow_override=False, pin=None):
    pin = COMPILER_PIN if pin is None else pin
    directory = directory.resolve()
    revision = command(["git", "-C", directory, "rev-parse", "HEAD"]).strip()
    changes = command(["git", "-C", directory, "status", "--porcelain"]).splitlines()
    require(allow_override or (pin == COMPILER_PIN and revision == COMPILER_PIN["revision"] and not changes),
            "Compiler checkout must match the clean pin; use --allow-compiler-override to record an override")
    require(pin['target'] == COMPILER_PIN['target'] and pin['abi'] == COMPILER_PIN['abi'],
            'Compiler candidate requires an explicit target/ABI migration')
    require(pin['image_format_version'] in (2, 3), 'Unsupported compiler image contract')
    # An explicit target directory prevents inherited CARGO_TARGET_DIR from
    # selecting an unrelated binary. Build before hashing or invoking it.
    target = directory / "target"
    command(["cargo", "build", "--locked", "--manifest-path", directory / "Cargo.toml",
             "--target-dir", target, "--bin", "actionc-65816"])
    binary = target / "debug/actionc-65816"
    from generate_native_abi import generate as native_definitions
    for path, content in native_definitions(directory).items():
        require(path.read_text() == content, "Stale native ABI consumer: " + str(path))
    abi = json.loads((directory / pin["abi_json"]).read_text())
    require(abi["abi"] == pin["abi"], "Compiler ABI identity mismatch")
    exec_abi = json.loads((ROOT / "abi/exec816-v1.json").read_text())
    fields = {field["name"]: field["offset"] for field in abi["saved_frame"]["fields"]}
    require(all(fields.get(name) == offset for name, offset in exec_abi["compiler_frame"].items()),
            "Exec policy's saved-frame offsets differ from the compiler ABI")
    return {"directory": directory, "binary": binary, "revision": revision, "changes": changes,
            "override": pin != COMPILER_PIN or revision != COMPILER_PIN["revision"] or bool(changes),
            "compiler_contract": pin,
            "image_format_version": pin['image_format_version'],
            "binary_sha256": sha256(binary),
            "abi_sha256": sha256(directory / pin["abi_json"]),
            "memory_runtime_inputs": {name: sha256(directory/'runtime/65816'/name)
                                      for name in ('a816memory.act', 'memory.s', 'memory.json')},
            "abi_assembly_sha256": sha256(directory / pin["abi_assembly"])}


def assemble(toolchain, output, entry, probe_nmi=0, initial_i=0, cooperative=False,
             dispatch=APP_BASE, probe_flags=0x100, forward_signature=0, preemptive=False,
             memory=None, kernel_init=0, tasks=False, task_init=0, policy_probe=0, irq_probe=0, manual_wake=False, pump_count=256, heap_shutdown=0, heap_allocate=0, heap_deallocate=0, heap_probe=False, ports_create=0, ports_delete=0, io_create=0, io_delete=0, io_wait=0, io_do=0, io_open=0, console_test=False, console_enabled=False, console_start=0, stack_checks=True, io_close=0, io_begin=0, io_send=0, io_abort=0):
    command(["ca65", "-I", output, "-I", toolchain["directory"] / "docs/abi",
             "-I", toolchain["directory"] / "runtime/65816",
             "-I", ROOT / "platform/altirraos", "-D", f"PROGRAM_ENTRY={entry}",
             "-D", f"STACK_CHECKS={int(stack_checks)}",
             "-D", f"PROBE_NMI={probe_nmi}", "-D", f"INITIAL_I={initial_i}",
             "-D", f"PREEMPTIVE={int(preemptive)}",
             "-D", f"GENERAL_TASKS={int(tasks)}", "-D", f"TASK_INIT={task_init}", "-D", f"HEAP_SHUTDOWN={heap_shutdown}", "-D", f"HEAP_ALLOCATE={heap_allocate}", "-D", f"HEAP_DEALLOCATE={heap_deallocate}", "-D", f"HEAP_PROBE={int(heap_probe)}",
             "-D", f"PORTS_CREATE={ports_create}", "-D", f"PORTS_DELETE={ports_delete}",
             "-D", f"IO_CREATE={io_create}", "-D", f"IO_DELETE={io_delete}",
             "-D", f"IO_OPEN={io_open}", "-D", f"IO_WAIT={io_wait}", "-D", f"IO_DO={io_do}",
             "-D", f"IO_CLOSE={io_close}", "-D", f"IO_BEGIN={io_begin}", "-D", f"IO_SEND={io_send}", "-D", f"IO_ABORT={io_abort}",
             "-D", f"SIGNAL_PROBE={policy_probe}", "-D", f"SIGNAL_IRQ_PROBE={irq_probe}", "-D", f"SIGNAL_AUTO={int(not manual_wake)}", "-D", f"PUMP_COUNT={pump_count}",
             "-D", f"CONSOLE_NATIVE={int(console_test)}", "-D", f"CONSOLE_STARTUP={int(console_enabled)}", "-D", f"CONSOLE_START={console_start}",
             "-D", f"COOPERATIVE={int(cooperative)}", "-D", f"DISPATCH_ENTRY={dispatch}",
             "-D", f"BANKED={int(memory is not None)}", "-D", f"MEMORY_INIT={kernel_init}",
             "-D", f"PROBE_FLAGS={probe_flags}",
             "-D", f"FORWARD_SIGNATURE={forward_signature}",
             "-l", output / "hosted.lst", "-o", output / "hosted.o",
             ROOT / "platform/altirraos/hosted.s"])
    cfg = ROOT/'platform/altirraos/hosted.cfg'
    config = cfg.read_text().replace('\r\n', '\n')
    require(config == adapter.hosted_config(memory['profile'] if memory else None),
            'Stale generated resident linker layout')
    if tasks:
        from generate_tasks import storage
        from generate_sio_adapter import ABI as sio_adapter
        binding_size = 58
        binding_base = storage(memory)['ENTRY_COUNT']
        signal_base = storage(memory)['BASE']+sio_adapter['native_offset']
        config = config.replace('MEMORY {',f'MEMORY {{ SIGNALS: start=${signal_base:x}, size=${sio_adapter["native_reserved_bytes"]:x}, file="%O.signals";').replace('SEGMENTS {','SEGMENTS { SIGNAL_CODE: load=SIGNALS,type=ro;')
        config = config.replace('MEMORY {', f'MEMORY {{ BINDINGS: start=${binding_base:x}, size=${binding_size:x}, file="%O.tasks";').replace(
            'SEGMENTS {', 'SEGMENTS { TASK_BINDINGS: load=BINDINGS, type=ro;')
    if memory and probe_flags != 0x100:
        probe_base = 0x20000
        if tasks:
            require(len(memory['usable_banks']) >= 2, 'Register probe needs a separate upper bank')
            probe_base = sorted(memory['usable_banks'])[-2] << 16
        config = config.replace('MEMORY {', f'MEMORY {{ BANKPROBE: start=${probe_base:x}, size=$1000, file="%O.probe";').replace(
            'SEGMENTS {', 'SEGMENTS { BANKPROBE: load=BANKPROBE, type=ro;')
    if tasks or (memory and probe_flags != 0x100):
        cfg = output/'hosted-generated.cfg'
        cfg.write_text(config)
    command(["ld65", "-C", cfg,
             "-o", output / "hosted.bin", "-Ln", output / "hosted.lbl", output / "hosted.o"])
    labels = {}
    for line in (output / "hosted.lbl").read_text().splitlines():
        _, address, label = line.split()
        labels[label.lstrip(".")] = int(address, 16)
    return labels


def integer(value, label):
    require(type(value) is int, f"{label} must be an integer")
    return value


def image_regions(image, labels, imports, memory=None, image_version=None, stack_checks=True):
    """Reject unsupported/malformed placement before writing any XEX output.

    The compiler verifies semantic maps; this consumer independently checks
    every byte the XEX loader can write and the platform entry/import contract.
    """
    keys = {"format", "version", "target", "abi", "entry", "stack_overflow",
            "task_headroom", "irq_headroom", "segments", "zero_fill", "routines", "data", "imports"}
    image_version = COMPILER_PIN['image_format_version'] if image_version is None else image_version
    require(image_version in (2, 3), 'Unsupported native image contract')
    if isinstance(image, dict) and image.get('version') == 4 and image_version == 3:
        keys.add('arithmetic_fault')
        require(type(image.get('arithmetic_fault')) is int and
                image['arithmetic_fault'] == labels.get('arithmetic_fault') and
                image['arithmetic_fault'] != labels['stack_overflow'], 'Invalid arithmetic fault binding')
        image_version = 4
    require(isinstance(image, dict) and set(image) in (keys, keys | {"stack_checks"}), "Unsupported native image fields")
    require(type(image.get("stack_checks", True)) is bool and image.get("stack_checks", True) == stack_checks,
            "Image stack checks differ from assembled platform")
    for key, value in {"format": "actionc-65816-image", "version": image_version,
                       "target": COMPILER_PIN["target"], "abi": COMPILER_PIN["abi"],
                       "stack_overflow": labels["stack_overflow"],
                       "task_headroom": 26, "irq_headroom": 13}.items():
        require(image[key] == value, f"Unsupported image {key}")
    require(image["imports"] == imports, "Image imports differ from assembled bindings")
    if image_version >= 3:
        from native_frame_maps import validate
        validate(image['routines'])
    regions, executable = [], []
    for segment in image["segments"]:
        require(set(segment) == {"address", "bytes", "writable", "executable"}, "Invalid segment fields")
        raw = segment["bytes"]
        require(isinstance(raw, list) and len(raw) <= (0x1000000 if memory else APP_LIMIT-APP_BASE), "Invalid payload size")
        require(all(type(byte) is int and 0 <= byte <= 255 for byte in raw), "Invalid payload bytes")
        require(type(segment["writable"]) is bool and type(segment["executable"]) is bool,
                "Invalid segment permissions")
        require(not (segment["writable"] and segment["executable"]), "Writable code is unsupported")
        address = integer(segment["address"], "segment address")
        regions.append((address, bytes(raw)))
        if segment["executable"]:
            executable.append((address, address+len(raw)))
    for zero in image["zero_fill"]:
        require(set(zero) == {"address", "size", "writable"}, "Invalid zero-fill fields")
        size = integer(zero["size"], "zero-fill size")
        require(0 < size <= (0x1000000 if memory else APP_LIMIT-APP_BASE)
                and type(zero["writable"]) is bool, "Invalid zero-fill")
        address = integer(zero["address"], "zero-fill address")
        if not memory:
            regions.append((address, bytes(size)))
    if memory:
        from banked_image import extents
        extents(image, memory)
    else:
        for address, payload in regions:
            require(payload and APP_BASE <= address < address+len(payload) <= APP_LIMIT,
                    f"Image region outside reserved bank-zero arena: ${address:x}+{len(payload)}")
    regions.sort(key=lambda item: item[0])
    require(all(a+len(data) <= b for (a, data), (b, _) in zip(regions, regions[1:])),
            "Overlapping image or zero-fill regions")
    entry = integer(image["entry"], "entry")
    require(any(start <= entry < end for start, end in executable), "Entry is outside executable memory")
    entries = [routine for routine in image["routines"] if routine["address"] == entry]
    require(len(entries) == 1 and entries[0]["arguments"] == [] and entries[0]["result_bytes"] == 0,
            "Program entry must be a zero-argument procedure")
    return regions


def xex_segment(address, data):
    require(data and 0 <= address < address+len(data) <= 0x10000, "Invalid XEX extent")
    return struct.pack("<HH", address, address+len(data)-1) + data


def require_executable(image, address):
    require(type(address) is int and any(s['executable'] and
            s['address'] <= address < s['address']+len(s['bytes']) for s in image['segments']),
            'Kernel entry is outside executable image memory')


def kernel_source(text, source_dir=None):
    """Link internal memory policy into a named root module, preserving LF/CRLF meaning."""
    text = text.replace('\r\n', '\n')
    if source_dir is not None:
        # The generated root lives beside the per-build memory definitions.
        # Preserve INCLUDE resolution relative to the user's original source.
        def include(match):
            path = Path(match[2])
            return match[1] + '"' + str((source_dir / path).resolve()) + '"'
        text = re.sub(r'(?mi)^([ \t]*INCLUDE[ \t]+)"([^"\n]+)"', include, text)
    require(re.search(r'(?mi)^MODULE\s+[A-Za-z_][\w.]*', text), 'Banked program needs a named module')
    if not re.search(r'(?mi)^USE\s+EXECMEMORY\s*(?:;[^\n]*)?$', text):
        text = re.sub(r'(?mi)^(MODULE\s+[A-Za-z_][\w.]*)', r'\1\nUSE EXECMEMORY', text, count=1)
    return text


def build(toolchain, source, output, optimize=True, probe_nmi=0, initial_i=0, cooperative=False,
          probe_flags=0x100, forward_signature=0, preemptive=False, banked=False,
          max_banks=None, memory_profile=None, kernel_config=None, kernel_init_name='EXECMEMORY.Init', tasks=False, image_data=(), policy_probe=0, irq_probe=0, manual_wake=False, pump_count=256, kernel_bank=None, task_capacity=4, worker_stack=None, idle_stack=None, heap_probe=False, io_test_device=False, dos_test=False, dos_mounts=(), console_test=False, console=None, stack_checks=None, sio_request_probe=False, sio_lifetime_probe=False, foreign_image=None, system_mount=None):
    configuration=json.loads(Path(kernel_config or ROOT/'config/kernel.json').read_text())
    stack_checks_enabled=configuration.get('stack_checks',True) if stack_checks is None else stack_checks
    require(type(stack_checks_enabled) is bool,'Stack checks option must be boolean')
    console_enabled=configuration.get('console',False) if console is None else console
    require(type(console_enabled) is bool and type(console_test) is bool,'Console build options must be boolean')
    console_native=console_enabled or console_test
    require(not console_enabled or tasks,'Configured console requires Tasks')
    require(foreign_image is None or tasks, 'Foreign code requires Task packaging')
    require(type(pump_count) is int and 2 <= pump_count <= 65535, 'Invalid diagnostic pump length')
    require(not heap_probe or tasks, 'Heap probes require tasks')
    require(not (sio_request_probe or sio_lifetime_probe) or (tasks and io_test_device), 'SIO probes require the diagnostic device build')
    require(not dos_mounts or (tasks and not dos_test),'Mounts require ordinary Task packaging')
    from generate_dos_mounts import validate_mounts, select_system, encode as encode_mounts
    dos_mounts=validate_mounts(dos_mounts)
    system_selection=select_system(dos_mounts,system_mount)
    dos_system=tasks and not dos_test
    require(type(dos_test) is bool and (not dos_test or tasks),'DOS fixtures require tasks')
    require(type(io_test_device) is bool and (not io_test_device or tasks),'I/O test devices require tasks')
    require(irq_probe in range(11) and (irq_probe == 0 or tasks), 'Invalid IRQ checkpoint profile')
    require(not console_native or (tasks and irq_probe!=10),'Console fixtures require Tasks and exclude the disposable probe')
    require(policy_probe == 0 or tasks, 'Signal checkpoints require tasks')
    require(not tasks or kernel_init_name == 'EXECMEMORY.Init',
            'General tasks require standard memory adoption before reclaiming loader storage')
    require(type(task_capacity) is int and 2 <= task_capacity <= 16, 'Invalid task capacity')
    require(task_capacity==4 or tasks, 'Capacity selection requires tasks')
    require(banked or tasks or kernel_bank is None, 'Kernel bank selection requires banked loading')
    if task_capacity==4:
        require(worker_stack in (None,1536) and idle_stack in (None,1536),
                'Four-task pools use 1536-byte stacks')
    banked = banked or tasks
    preemptive = preemptive or tasks
    cooperative = cooperative or preemptive or banked
    output = output.resolve()
    source = source.resolve()
    output.mkdir(parents=True, exist_ok=True)
    exec_build = None
    if tasks:
        from generate_build_info import generate as generate_build_info
        exec_build = generate_build_info(output, dos_mounts, task_capacity, stack_checks_enabled, system_mount)
    memory = None
    compile_source = source
    if banked:
        import generate_memory
        upper_table=tasks and task_capacity!=4
        memory = generate_memory.layout(kernel_config or generate_memory.CONFIG,
                                        memory_profile or generate_memory.PROFILE, max_banks,kernel_bank,upper_table)
        memory['boot_config'].update(system_selection)
        if upper_table:
            from task_capacity import configure
            configure(memory,task_capacity,worker_stack,idle_stack)
        if tasks:
            import generate_heap
            generate_heap.reserve_metadata(memory)
            import generate_ports
            generate_ports.reserve_metadata(memory)
            import generate_io
            generate_io.reserve_metadata(memory)
            import generate_dos
            generate_dos.reserve_metadata(memory,task_capacity)
            import generate_process
            generate_process.reserve_metadata(memory,task_capacity)
            if console_native:
                import generate_console
                require((ROOT/'lib/console/consoletypes.act').read_text()==generate_console.types(),'Stale console types')
                require((ROOT/'platform/altirraos/console-layout.inc').read_text()==generate_console.assembly(),'Stale console layout')
                generate_console.reserve_metadata(memory)
                generate_console.generate(output,memory)
            from boot_config import reserve_settings
            reserve_settings(memory)
            generate_heap.registration_include(output,memory)
            generate_heap.generate(output,memory["constants"]["MAX_BANKS"])
            import generate_tasks
            from functools import partial
            generated_api = ROOT/'lib/exec/exec-task-types.inc'
            require(generated_api.read_text().replace('\r\n','\n') == generate_tasks.public_api(), 'Stale public task ABI')
            import generate_ports
            generate_ports.generate(output)
            require((ROOT/'lib/exec/exec-port-types.inc').read_text().replace('\r\n','\n') == generate_ports.public_api(),
                    'Stale public port ABI')
            import generate_io
            require((ROOT/'lib/exec/exec-io-types.inc').read_text() == generate_io.public_api(),
                    'Stale public I/O ABI')
            task_generate = partial(generate_tasks.generate_kernel,memory=memory)
            import generate_sio_adapter
            require((ROOT/'platform/altirraos/sio-state.inc').read_text()==generate_sio_adapter.assembly(),'Stale private SIO layout')
            generate_sio_adapter.generate(output,generate_tasks.storage(memory)['BASE'])
            generate_tasks.validate_memory(memory)
            task_generate(output)
            task_modules = generate_tasks.policy_modules(output,policy_probe,memory,manual_wake,irq_probe,io_test_device,dos_test,dos_system,console_native,sio_request_probe=sio_request_probe,sio_lifetime_probe=sio_lifetime_probe)
        memory['config']['stack_checks']=stack_checks_enabled
        generate_memory.reserve_image_data(memory)
        memory_hash = generate_memory.generate(output, memory)
        if tasks:
            generate_heap.install_policy(output)
        # A copy beside generated includes preserves independent build limits.
        memory_policy=read_source(ROOT/'lib/exec/execmemory.act')
        if memory['constants']['TABLE']>=65536:
            memory_policy=memory_policy.replace('BankRecord ARRAY banks(M_MAX_BANKS)=M_TABLE','BankRecord POINTER banks').replace('BYTE ARRAY tableBytes(M_TABLE_BYTES)=M_TABLE','BYTE POINTER tableBytes')
            memory_policy=memory_policy.replace('PUBLIC CARD FUNC Adopt()\n  CARD i','PUBLIC CARD FUNC Adopt()\n  CARD i\n  banks=BankRecord POINTER(ADDRESS(M_TABLE))\n  tableBytes=BYTE POINTER(ADDRESS(M_TABLE))')
        (output/'execmemory.act').write_text(memory_policy)
        (output/'bootconfig.act').write_text(read_source(ROOT/'lib/exec/bootconfig.act'))
        compile_source = output / 'kernel-program.act'
        compile_source.write_text(kernel_source(source.read_text(), source.parent))
        if tasks:
            compile_source.write_text(compile_source.read_text().replace('USE EXECMEMORY\n','USE EXECMEMORY\nUSE PORTCORE\nUSE IOCORE\n',1))
        if console_enabled and not re.search(r'(?mi)^USE\s+CONSOLEDRIVER\s*$',compile_source.read_text()):
            compile_source.write_text(compile_source.read_text().replace('USE EXECMEMORY\n','USE EXECMEMORY\nUSE CONSOLEDRIVER\n',1))
    require(initial_i in (0, 4) and 0 <= probe_nmi <= (24 if tasks else 18 if preemptive else 12 if cooperative else 8), "Invalid qualification mode")
    require(not cooperative or initial_i == 0, "Cooperative startup requires IRQs enabled")
    require(0 <= probe_flags <= 0x100 and (cooperative or probe_flags == 0x100), "Invalid register probe")
    require(forward_signature in (0, 1, 0x7F), "Invalid COP forwarding probe")
    command(["python3", ROOT / "tools/generate_exec_abi.py", "--check"])
    labels = assemble(toolchain, output, APP_BASE, probe_nmi, initial_i, cooperative,
                      probe_flags=probe_flags, forward_signature=forward_signature, preemptive=preemptive,
                      memory=memory, tasks=tasks, policy_probe=policy_probe, irq_probe=irq_probe, manual_wake=manual_wake, pump_count=pump_count, heap_probe=heap_probe,console_test=console_native,console_enabled=console_enabled,stack_checks=stack_checks_enabled)
    if tasks:
        task_generate(output, labels)
    base_args = [toolchain["binary"], *(["--module-path", task_modules] if tasks else []),
                 *(["--module-path", output, "--module-path", source.parent] if banked else []),
                 "--module-path", toolchain['directory']/'runtime/65816',
                 *module_args()]
    interfaces = json.loads(command([*base_args, "--emit-interfaces", compile_source]))
    imports = []
    for interface in interfaces:
        name = interface["name"]
        arguments, outgoing, result, peak = [], 1, "Some(NativeResult(A16))", 0
        if tasks and name.startswith('A816MEMORY.'):
            memory_api = json.loads((toolchain['directory']/'runtime/65816/memory.json').read_text())
            require(memory_api['abi'] == COMPILER_PIN['abi'], 'Memory runtime ABI changed')
            shape = memory_api['imports'][name.split('.')[1]]
            arguments, outgoing, result = shape['arguments'], shape['outgoing_bytes'], 'None'
            label, peak = shape['label'], memory_api['stack_peak']
        elif tasks and name == 'TASKPOLICY.IRQWindow':
            label,result='signal_irq_window','None'
            peak=5 if irq_probe==3 else 1
        elif tasks and name in ('TASKPOLICY.SignalChange', 'TASKPOLICY.WaitBegin',
                                'TASKPOLICY.WaitComplete', 'TASKPOLICY.WakeMatch',
                                'TASKPOLICY.TakeWake', 'TASKPOLICY.CancelWakeNode'):
            operation = name.split('.')[1]
            label = {'SignalChange':'signal_change', 'WaitBegin':'signal_wait_begin',
                     'WaitComplete':'signal_wait_complete', 'WakeMatch':'signal_wake_match',
                     'TakeWake':'signal_wake_take', 'CancelWakeNode':'signal_wake_cancel'}[operation]
            arguments = [] if operation == 'TakeWake' else [{'alignment':1, 'offset':0, 'size':3}]
            outgoing = 1 if operation == 'TakeWake' else 3
            result = generate_tasks.RESULTS[{'SignalChange':4, 'WaitBegin':4, 'WaitComplete':4,
                                             'WakeMatch':1, 'TakeWake':3, 'CancelWakeNode':0}[operation]]
            if operation in ('SignalChange', 'WaitBegin'):
                arguments.append({'alignment':2, 'offset':4, 'size':4})
                outgoing = 9
            if operation == 'SignalChange':
                arguments.append({'alignment':2, 'offset':8, 'size':4})
                outgoing = 13
            peak = 15 + (8 if policy_probe else 0)
        elif tasks and name == 'TASKPOLICY.ClaimCheckpoint' and irq_probe == 9:
            label, result, outgoing, peak = 'signal_claim_checkpoint', 'None', 3, 15
            arguments = [{'alignment':1, 'offset':0, 'size':3}]
        elif tasks and name in ('TASKPOLICY.SerialClaim','TASKPOLICY.SerialRelease'):
            label = 'signal_claim' if name.endswith('Claim') else 'signal_release'
            result = 'Some(NativeResult(A8ZeroExtended))' if name.endswith('Claim') else 'None'
            peak = 3
        elif tasks and name.startswith('CONSOLEPROBE.'):
            require(irq_probe==10,'Console probe is unavailable in production')
            operation=name.split('.')[1]
            require(operation in ('Claim','Release','Take'),'Unknown console probe operation')
            label='console_probe_'+operation.lower()
            result='Some(NativeResult(A16))' if operation=='Take' else 'None'
            peak=5
        elif tasks and name=='CONSOLEDISPLAY.Span':
            require(console_native,'Console span is unavailable in this build')
            label,result,peak='console_span','None',0
            arguments=[dict(alignment=1,offset=0,size=3),dict(alignment=1,offset=3,size=3),dict(alignment=2,offset=6,size=2)]
            outgoing=9
        elif tasks and name in ('TASKPOLICY.ConsoleClaim','TASKPOLICY.ConsoleRelease'):
            require(console_native,'Console native ownership is unavailable in this build')
            label={'ConsoleClaim':'console_claim','ConsoleRelease':'console_release'}[name.split('.')[1]]
            result='Some(NativeResult(A8ZeroExtended))' if name.endswith('Claim') else 'None'
            peak=3
        elif tasks and name.startswith(('CONSOLEADAPTER.','CONSOLECAPTURE.')):
            require(console_native,'Console adapter is unavailable in this build')
            operation=name.split('.')[1]
            require(operation in ('Bind','Release','Take','ResetInput','ClearUnit','Publish','TakeBreak'),'Unknown console adapter import')
            label={'Bind':'console_bind','Release':'console_unbind','Take':'console_take','ResetInput':'console_reset_input','ClearUnit':'console_clear_unit','Publish':'console_publish','TakeBreak':'console_take_break'}[operation]
            if operation=='Bind':
                arguments=[dict(alignment=1,offset=0,size=3),dict(alignment=2,offset=4,size=4)]
                outgoing,result=9,'Some(NativeResult(A8ZeroExtended))'
            elif operation in ('Publish','ClearUnit'):
                arguments=[dict(alignment=2,offset=0,size=4)];outgoing=5;result='None'
            else:result='Some(NativeResult(A16X16))' if operation in ('Take','TakeBreak') else 'None'
            peak=5 if operation in ('Take','ClearUnit') else 1 if operation in ('ResetInput','ClearUnit','Publish','TakeBreak') else 0
        elif tasks and name in ('SIOPROBE.Emulation','SIOPROBE.Stall','SIOPROBE.Stale'):
            require(io_test_device,'SIO test entry is unavailable in production')
            label,result,peak='sio_probe_'+name.split('.')[1].lower(),'None',31 if name.endswith('Stale') else 19
        elif tasks and name.startswith('SIOADAPTER.'):

            operation=name.split('.')[1]
            label='sio_'+operation.lower()
            result='Some(NativeResult(A8ZeroExtended))' if operation in ('Init','Start','Retire','Recovered') else 'None'
            peak=19
        elif tasks and name.startswith('EXECPRODUCER.'):
            operation=name.split('.')[1]
            shape=generate_tasks.ABI['producer_imports'][operation]
            arguments,outgoing=shape['arguments'],shape['outgoing_bytes']
            result=generate_tasks.RESULTS[shape['result_bytes']]
            label={'Bind':'signal_bind','Release':'signal_unbind','Drain':'signal_drain'}[operation]
        elif tasks and name.startswith('EXECSIGNALIRQ.'):
            label={'PumpStart':'signal_pump_start','IRQContext':'signal_context'}[name.split('.')[1]]
            result='None'
            peak=1 if name.endswith('PumpStart') else 14
        elif heap_probe and name.startswith('HEAPAPIPROBE.'):
            operation=name.split('.')[1]
            require(operation in ('Fill','VerifyZero','Masked'),'Unsupported heap probe')
            label='heap_probe_'+operation.lower()
            if operation=='Fill':
                arguments=[{'alignment':1,'offset':0,'size':3},{'alignment':2,'offset':4,'size':4},{'alignment':1,'offset':8,'size':1}]
                outgoing,result=9,'None'
            elif operation=='VerifyZero':
                arguments=[{'alignment':1,'offset':0,'size':3},{'alignment':2,'offset':4,'size':4}]
                outgoing,result=9,'Some(NativeResult(A8ZeroExtended))'
            else: peak=30
        elif name == "HEAPCORE.Abort":
            label, result = "heap_fault", "None"
            arguments, outgoing = [{"alignment":2,"offset":0,"size":2}], 3
        elif name == "EXECOS.Write":
            label, peak = "console_write", 266 if banked else 10
            arguments = [{"alignment": 1, "offset": 0, "size": 3},
                         {"alignment": 2, "offset": 4, "size": 2}]
            outgoing = 7
        elif tasks and name=='PORTCORE.DeleteCheck':
            arguments,outgoing=[{'alignment':1,'offset':0,'size':3}],3
            result='Some(NativeResult(A8ZeroExtended))'
            label='ports_delete_check'
        elif name=='DOSCORE.Current':
            require(tasks,'DOS client operations require Task packaging')
            arguments,outgoing,result=[],1,'Some(NativeResult(A16X8ZeroExtended))'
            label='dos_current'
        elif name=='DOSCORE.Control':
            # The private gateway exists in every Task kernel. Isolated DOS
            # fixtures leave its worker descriptor empty, so no service is admitted.
            require(tasks,'DOS service operations require Task packaging')
            arguments,outgoing,result=[{'alignment':1,'offset':0,'size':1},{'alignment':1,'offset':1,'size':3}],5,'Some(NativeResult(A16X8ZeroExtended))'
            label='dos_control'
        elif name.startswith('DOS.'):
            from generate_dos import production_binding
            production_binding(interface)
        elif tasks and name.startswith('EXEC.') and name[5:] in generate_io.ABI['imports']:
            label=generate_io.production_binding(interface)
            shape=generate_io.ABI['imports'][name[5:]]
            arguments,outgoing=shape['arguments'],shape['outgoing_bytes']
            result=generate_io.RESULTS[shape['result_bytes']]
            peak=3
        elif tasks and name=='IOCORE.OpenGateway':
            shape=generate_io.ABI['imports']['OpenDevice']
            arguments,outgoing=shape['arguments'],shape['outgoing_bytes']
            result='Some(NativeResult(A16X16))'
            label,peak='io_open_dispatch',3
        elif tasks and name in ('IOCORE.Collect','IOCORE.StartGateway','IOCORE.CloseGateway','IOCORE.BeginGateway','IOCORE.SendGateway','IOCORE.AbortGateway'):
            arguments,outgoing=[{'alignment':1,'offset':0,'size':3}],3
            result='Some(NativeResult(A16X16))'
            label={'Collect':'io_collect','StartGateway':'io_start','CloseGateway':'io_close_dispatch',
                   'BeginGateway':'io_begin_dispatch','SendGateway':'io_send_dispatch','AbortGateway':'io_abort_dispatch'}[name.split('.')[1]]
            peak=3
        elif tasks and name=='IOPROBE.Advance':
            require(io_test_device,'Test I/O control is unavailable in production')
            arguments,outgoing=[{'alignment':1,'offset':0,'size':1}],1
            result='Some(NativeResult(A16X16))'
            label='io_test_step'
            peak=3
        elif tasks and name in ('IOCORE.CreateCheck','IOCORE.DeleteCheck'):
            arguments,outgoing=[{'alignment':1,'offset':0,'size':3}],3
            result='Some(NativeResult(A16))'
            label='io_create_check' if name.endswith('CreateCheck') else 'io_delete_check'
            peak=3
        elif tasks and name.startswith('EXEC.') and name[5:] in generate_ports.ABI['imports']:
            operation=name[5:]
            require(operation in generate_ports.IMPLEMENTED,'Unimplemented port import: '+name)
            generate_ports.check_routine(interface,operation)
            shape=generate_ports.ABI['imports'][operation]
            arguments,outgoing=shape['arguments'],shape['outgoing_bytes']
            result=generate_ports.RESULTS[shape['result_bytes']]
            label='ports_'+generate_ports.IMPLEMENTED[operation]
            peak=11 if operation=='WaitPort' else 0
        elif tasks and name.startswith('EXEC.') and name[5:] in generate_heap.ABI['imports']:
            operation=name[5:]
            generate_heap.check_routine(interface,operation)
            shape=generate_heap.ABI['imports'][operation]
            arguments,outgoing=shape['arguments'],shape['outgoing_bytes']
            result=generate_heap.RESULTS[shape['result_bytes']]
            label='heap_'+{'AllocMem':'alloc_mem','FreeMem':'free_mem','AllocVec':'alloc_vec',
                           'FreeVec':'free_vec','AvailMem':'avail_mem','TypeOfMem':'type_of_mem',
                           'Allocate':'allocate','Deallocate':'deallocate'}[operation]
            peak=12 if operation in ('AllocMem','AllocVec') else 0
        elif tasks and name.startswith('EXEC.') and name[5:] in generate_tasks.ABI['imports']:
            shape = generate_tasks.ABI['imports'][name[5:]]
            arguments, outgoing = shape['arguments'], shape['outgoing_bytes']
            result = generate_tasks.RESULTS[shape['result_bytes']]
            label = 'tasks_'+{'CreateTask':'create_task', 'AddTask':'add_task', 'RemTask':'rem_task', 'FindTask':'find_task',
                            'SetTaskPri':'set_task_pri', 'Forbid':'forbid', 'Permit':'permit',
                            'AllocSignal':'alloc_signal', 'FreeSignal':'free_signal',
                            'SetSignal':'set_signal', 'Signal':'signal', 'Wait':'wait',
                            'RetainTask':'retain_task','ReleaseTask':'release_task','RegisterResident':'register_resident','UnregisterResident':'unregister_resident'}[name[5:]]
        elif name.startswith('EXECTASKS.'):
            require(tasks, 'EXECTASKS services require --tasks')
            require(name == 'EXECTASKS.Sleep', f'Unsupported import: {name}')
            label = 'tasks_sleep'
            arguments, outgoing = [{'alignment':2, 'offset':0, 'size':2}], 3
        else:
            bindings = {"Version": "version", "TaskId": "task_id", "Yield": "yield",
                        "Poll": "poll", "Lock": "lock", "Unlock": "unlock", "ExitTask": "exit"}
            require(cooperative and name.startswith("EXEC.") and name[5:] in bindings,
                    f"Unsupported import: {name}")
            require(not tasks or name in ("EXEC.Version","EXEC.Yield","EXEC.Poll"),
                    f"Unsupported task import: {name}")
            label = "exec_"+bindings[name[5:]]
            if name in ("EXEC.Yield", "EXEC.Poll", "EXEC.ExitTask"):
                result = "None"
            if name == "EXEC.ExitTask":
                arguments, outgoing = [{"alignment": 2, "offset": 0, "size": 2}], 3
        require(interface["arguments"] == arguments and interface["outgoing_bytes"] == outgoing
                and interface["result"] == result and interface["abi"] == COMPILER_PIN["abi"],
                f"Interface ABI changed: {name}")
        imports.append({"symbol": interface["symbol"], "signature": interface["signature"],
                        "abi": interface["abi"], "address": labels[label],
                        "size": labels[label+"_end"]-labels[label],
                        "stack_peak": peak, "checks_stack": stack_checks_enabled, "irq_effect": "preserve"})
    layout = {"code_origin": APP_BASE, "data_origin": 0x8800 if cooperative else 0x8000,
              "stack_overflow": labels["stack_overflow"], "arithmetic_fault": labels["arithmetic_fault"],
              "nmi_extra_stack": 0, "imports": imports}
    # Checked emission is the compiler default; only opt-out needs an option.
    if not stack_checks_enabled:
        layout["stack_checks"] = False
    if banked:
        layout.update(code_origin=memory['profile']['code_origin'], data_origin=memory['profile']['data_origin'])
    (output / "layout.json").write_text(json.dumps(layout, indent=2)+"\n")
    image_path = output / "program.a816.json"
    command([*base_args, "--layout", output / "layout.json", "-o", image_path,
             *([] if optimize else ["--no-opt"]), compile_source], timeout=600)
    require(image_path.stat().st_size <= (64 * 1024 * 1024 if banked else MAX_IMAGE_JSON), "Image manifest too large")
    image = json.loads(image_path.read_text())
    if banked:
        generate_memory.validate_compiled_data(image, memory)
    if foreign_image is not None:
        # Foreign functions have their own calling convention and no Action!
        # frame maps. Their load ranges still undergo every image/owner check.
        image['segments'].extend(foreign_image['segments'])
        image['zero_fill'].extend(foreign_image['zero_fill'])
    # Additional fixed image data is subject to the same placement/ownership
    # checks and admission bounds as compiler-emitted storage.
    for address, payload in image_data:
        image['segments'].append({'address':address, 'bytes':list(payload),
                                  'writable':True, 'executable':False})
    if image_data:
        image_path.write_text(json.dumps(image,indent=2)+'\n')
    if banked and probe_flags != 0x100:
        image['segments'].append({'address':labels['bankprobe'], 'bytes':list((output/'hosted.bin.probe').read_bytes()),
                                  'writable':False, 'executable':True})
        image_path.write_text(json.dumps(image, indent=2)+'\n')
    if tasks:
        process_storage = memory['process_storage']
        image['data'].append(dict(kind='global',id=max(d['id'] for d in image['data'])+1,
            name='M_PROCESSSTATE_TABLE',address=process_storage['BASE'],size=process_storage['BYTES'],alignment=2))
        task_storage = generate_tasks.storage(memory)
        image['segments'].append({'address':task_storage['BASE']+0x1000,'bytes':list((output/'hosted.bin.signals').read_bytes()),'writable':False,'executable':True})
        require(task_storage['METADATA_BYTES']<=0x800,'Task metadata overlaps SIO descriptor')
        descriptor=bytearray(128)
        image['segments'].append({'address':task_storage['BASE']+0x800,'bytes':list(descriptor),'writable':True,'executable':False})
        image['data'].append(dict(kind='global',id=max(d['id'] for d in image['data'])+1,
            name='M_TASKPOLICY_SIO_DESCRIPTOR',address=task_storage['BASE']+0x800,size=128,alignment=64))
        from generate_process import check_calls as check_process_calls, resident_entries, ABI as process_abi
        check_process_calls(image)
        dos_descriptor=bytearray(process_abi['resident_entries']['descriptor_bytes'])
        process_entries=resident_entries(image)
        entry_shape=process_abi['resident_entries']
        dos_descriptor[entry_shape['count_offset']]=len(process_entries)
        for index,address in enumerate(process_entries):
            offset=entry_shape['entries_offset']+3*index
            dos_descriptor[offset:offset+3]=address.to_bytes(3,'little')
        for name,offset in [('RUN',8),('FINISH',11),('EXECUTEIMAGE',14)]:
            callbacks=[r['address'] for r in image['routines'] if re.fullmatch(r'M_PROCESS_'+name+r'_[0-9A-F]+',r['name'])]
            require(len(callbacks)<=1, 'Ambiguous Process callback: '+name)
            if callbacks:dos_descriptor[offset:offset+3]=callbacks[0].to_bytes(3,'little')
        if dos_system:
            workers=[r['address'] for r in image['routines'] if re.fullmatch(r'M_FSWORKER_WORKER_[0-9A-F]+',r['name'])]
            require(len(workers)<=1 and (workers or not dos_mounts),'Configured mounts require a DOS application')
            if workers:dos_descriptor[:3]=workers[0].to_bytes(3,'little')
            dos_descriptor[3]=len(dos_mounts)
            config=encode_mounts(dos_mounts)
            if config:image['segments'].append({'address':task_storage['BASE']+0x900,'bytes':list(config),'writable':False,'executable':False})
        image['segments'].append({'address':task_storage['BASE']+0x880,'bytes':list(dos_descriptor),'writable':False,'executable':False})
        from generate_program import ABI as program_abi, provider_manifest, library_contracts
        provider_bytes, providers = provider_manifest(image, labels, stack_checks_enabled, library_contracts(toolchain["directory"]))
        if provider_bytes:
            require(0x1000+(output/'hosted.bin.signals').stat().st_size <= program_abi['provider_offset'],
                    'Task service code overlaps the provider manifest reservation')
            require(program_abi['provider_offset']+program_abi['provider_capacity'] <= 65536,
                    'Provider manifest reservation exceeds the existing Task arena bank')
            image['segments'].append(dict(address=task_storage['BASE']+program_abi['provider_offset'],
                                          bytes=list(provider_bytes),writable=False,executable=False))
            (output/'providers.json').write_text(json.dumps(dict(schema_version=1,compiler=toolchain['revision'],
                stack_checks=stack_checks_enabled,nmi_extra_stack=0,providers=providers),indent=2)+'\n')
        if console_native:
            image['segments'].append(dict(address=memory['console_storage']['GLYPHS'],bytes=generate_console.glyphs()+generate_console.ABI['keymaps']['normal']+generate_console.ABI['keymaps']['shifted'],writable=False,executable=False))

        image['segments'].append({'address':task_storage['BASE'],
                                 'bytes':[0]*task_storage['METADATA_BYTES'],
                                 'writable':True,'executable':False})
        image['data'].append({'kind':'global', 'id':max(d['id'] for d in image['data'])+1,
                              'name':'M_TASKPOLICY_METADATA', 'address':task_storage['BASE'],
                              'size':task_storage['METADATA_BYTES'],'alignment':64})
    regions = image_regions(image, labels, imports, memory, toolchain.get("image_format_version"), stack_checks_enabled)
    dispatch = APP_BASE
    if cooperative:
        policy = 'TASKPOLICY' if tasks else 'EXECPOLICY'
        candidates = [routine for routine in image["routines"]
                      if re.fullmatch(r"M_"+policy+r"_DISPATCH_[0-9A-F]+", routine["name"])]
        require(len(candidates) == 1, "Cooperative image needs EXECPOLICY.Dispatch")
        routine = candidates[0]
        require([{key: arg[key] for key in ("alignment", "offset", "size")}
                 for arg in routine["arguments"]] == [{"alignment": 2, "offset": 0, "size": 2},
                                                      {"alignment": 1, "offset": 2, "size": 1}]
                and routine["outgoing_bytes"] == 3 and routine["result_bytes"] == 2, "Dispatch ABI changed")
        dispatch = routine["address"]
        require_executable(image, dispatch)
    kernel_init = 0
    if banked:
        # Public retained entry; enforce its ordinary zero-argument CARD ABI.
        pattern = r'M_' + re.escape(kernel_init_name.replace('.', '_').upper()) + r'_[0-9A-F]+'
        candidates = [r for r in image['routines'] if re.fullmatch(pattern, r['name'])]
        require(len(candidates) == 1, f'Missing kernel initialization routine: {kernel_init_name}')
        init = candidates[0]
        require(init['arguments'] == [] and init['result_bytes'] == 2, 'Kernel initialization ABI changed')
        kernel_init = init['address']
        require_executable(image, kernel_init)
    console_start=0
    if console_enabled:
        candidates=[r for r in image['routines'] if re.fullmatch(r'M_CONSOLEDRIVER_START_[0-9A-F]+',r['name'])]
        require(len(candidates)==1 and candidates[0]['arguments']==[] and candidates[0]['result_bytes']==1,'Console startup ABI changed')
        console_start=candidates[0]['address']
    task_init = 0
    heap_shutdown = 0
    heap_allocate = heap_deallocate = 0
    ports_create = ports_delete = io_create = io_delete = io_wait = io_do = io_open = 0
    io_close = io_begin = io_send = io_abort = 0
    if tasks:
        candidates = [r for r in image['routines'] if re.fullmatch(r'M_TASKPOLICY_INIT_[0-9A-F]+', r['name'])]
        require(len(candidates) == 1 and candidates[0]['arguments'] == []
                and candidates[0]['result_bytes'] == 2, 'Task initialization ABI changed')
        cleanup=[r for r in image['routines'] if re.fullmatch(r'M_HEAPPOLICY_SHUTDOWN_[0-9A-F]+',r['name'])]
        require(len(cleanup)==1 and cleanup[0]['arguments']==[] and cleanup[0]['result_bytes']==0,'Heap shutdown ABI changed')
        heap_shutdown=cleanup[0]['address']
        private={}
        for operation in ('Allocate','Deallocate'):
            target=[r for r in image['routines'] if re.fullmatch(r'M_HEAPCORE_'+operation.upper()+r'_[0-9A-F]+',r['name'])]
            require(len(target)==1,'Missing private heap routine')
            generate_heap.check_routine(target[0],operation)
            private[operation]=target[0]['address']
        heap_allocate,heap_deallocate=private['Allocate'],private['Deallocate']
        port_targets={}
        for operation in ('CreateMsgPort','DeleteMsgPort'):
            target=[r for r in image['routines'] if re.fullmatch(r'M_PORTCORE_'+operation.upper()+r'_[0-9A-F]+',r['name'])]
            require(len(target)==1,'Missing caller-context port helper')
            generate_ports.check_routine(target[0],operation)
            port_targets[operation]=target[0]['address']
        ports_create,ports_delete=port_targets['CreateMsgPort'],port_targets['DeleteMsgPort']
        io_targets={}
        for operation in ('CreateIORequest','DeleteIORequest','WaitIO','DoIO','OpenDevice','CloseDevice','BeginIO','SendIO','AbortIO'):
            target=[r for r in image['routines'] if re.fullmatch(r'M_IOCORE_'+operation.upper()+r'_[0-9A-F]+',r['name'])]
            require(len(target)==1,'Missing caller-context I/O helper')
            generate_io.check_routine(target[0],operation)
            io_targets[operation]=target[0]['address']
        io_create,io_delete=io_targets['CreateIORequest'],io_targets['DeleteIORequest']
        io_wait,io_do=io_targets['WaitIO'],io_targets['DoIO']
        io_open=io_targets['OpenDevice']
        io_close,io_begin,io_send,io_abort=(io_targets[name] for name in ('CloseDevice','BeginIO','SendIO','AbortIO'))
        task_init = candidates[0]['address']
        require_executable(image, task_init)
        # Only emitted zero-argument procedures from application modules are
        # spawnable. Reject kernel/import addresses and mid-routine pointers.
        entries = generate_tasks.task_entries(image)
        if foreign_image is not None:
            for address in foreign_image['task_entries']:
                require(type(address) is int and address not in entries and any(
                    s['executable'] and s['address'] <= address < s['address']+len(s['bytes'])
                    for s in foreign_image['segments']), 'Invalid foreign Task entry')
                entries.append(address)
        writable = generate_tasks.writable_bindings(image,memory)
        image_path.write_text(json.dumps(image,indent=2)+"\n")
        image_regions(image, labels, imports, memory, toolchain.get("image_format_version"), stack_checks_enabled)
        task_generate(output, labels, entries, writable)
    final_labels = assemble(toolchain, output, image["entry"], probe_nmi, initial_i, cooperative,
                            dispatch, probe_flags, forward_signature, preemptive, memory, kernel_init, tasks, task_init, policy_probe, irq_probe, manual_wake, pump_count, heap_shutdown, heap_allocate, heap_deallocate, heap_probe, ports_create, ports_delete, io_create, io_delete, io_wait, io_do, io_open,console_native,console_enabled,console_start,stack_checks_enabled,
                            io_close=io_close,io_begin=io_begin,io_send=io_send,io_abort=io_abort)
    require(labels == final_labels, "Platform addresses changed during final assembly")
    if tasks:
        # Heap private-call thunks depend on final compiled routine addresses.
        # Refresh upper native code as well as the task binding data.
        signal_segment=next(s for s in image['segments'] if s['address']==task_storage['BASE']+0x1000)
        signal_segment['bytes']=list((output/'hosted.bin.signals').read_bytes())
        bindings = (output/'hosted.bin.tasks').read_bytes()
        segment = next(s for s in image['segments'] if s['address'] == task_storage['BASE'])
        offset = task_storage['ENTRY_COUNT']-task_storage['BASE']
        segment['bytes'][offset:offset+len(bindings)] = bindings
        image_regions(image,labels,imports,memory,toolchain.get("image_format_version"), stack_checks_enabled)
        image_path.write_text(json.dumps(image,indent=2)+'\n')
    if banked:
        from banked_image import emit
        payload, loader_labels = emit(output, image, memory, labels)
        labels.update(loader_labels)
    else:
        payload = b"\xff\xff" + xex_segment(adapter.RESIDENT_BASE, (output / "hosted.bin").read_bytes())
        for address, data in regions:
            payload += xex_segment(address, data)
        payload += xex_segment(0x02E0, struct.pack("<H", labels["start"]))
    xex = output / "program.xex"
    temporary = output / "program.xex.tmp"
    temporary.write_bytes(payload)
    temporary.replace(xex)
    provenance = {key: value for key, value in toolchain.items() if key not in ("directory", "binary")}
    if foreign_image is not None:
        provenance['foreign_image'] = foreign_image['provenance']
    provenance.update({"source": source.name, "source_sha256": sha256(source),
                       "platform_inputs": {name: sha256(ROOT / name) for name in (
                           "platform/altirraos/hosted.s", "platform/altirraos/layout.inc",
                           "platform/altirraos/hosted.cfg", "lib/exec/execos.act",
                           "abi/exec816-v1.json", "platform/altirraos/exec-abi.inc",
                           "tools/adapter_state.py", "tools/generate_exec_abi.py", "platform/altirraos/memory-1m.json",
                           "platform/altirraos/cooperative.s", "lib/exec/exec-abi.inc",
                           "platform/altirraos/cooperative-probe.s", "platform/altirraos/preemptive.s",
                           "lib/exec/exec.act", "lib/exec/execpolicy.act", "tools/library_paths.py")},
                       "optimize": optimize, "stack_checks": stack_checks_enabled, "probe_nmi": probe_nmi, "initial_i": initial_i,
                       "cooperative": cooperative, "preemptive": preemptive, "probe_flags": probe_flags,
                       "forward_signature": forward_signature,
                       "image_sha256": sha256(image_path), "xex_sha256": sha256(xex)})
    if tasks:
        provenance.update(tasks=True, exec_build=exec_build, dos_test=dos_test, dos_system=dos_system, dos_mounts=list(dos_mounts), system_mount=system_mount, system_selection=system_selection, heap_probe=heap_probe, io_test_device=io_test_device, task_init=task_init, task_entries=entries, process_entries=process_entries,
            task_storage=task_storage, signal_probe=policy_probe, signal_irq_probe=irq_probe,
            manual_wake=manual_wake, pump_count=pump_count if irq_probe==8 else None,
            task_inputs={name:sha256(ROOT/name) for name in (
                'abi/filesystems.json','tools/generate_filesystem_formats.py','tools/filesystem_formats.py',
                'lib/spartados/sdfs.act','lib/spartados/sdfstypes.act','lib/spartados/sdfsfile.act',
                'lib/spartados/sdfsdir.act','lib/spartados/sdfsname.act','lib/spartados/sdfsdate.act',
                'lib/fs/fsformats.act','lib/fs/fsbtypes.act','lib/fs/fsbackend.act',
                'lib/fs/fs83.act','lib/fs/fscore.act','lib/fs/fsstatus.act',
                'abi/process.json','tools/generate_process.py','lib/dos/process.act','lib/dos/processstate.act',
                'lib/dos/dosprocess.act','lib/dos/dosinherit.act','lib/fs/fsfiles.act',
                'lib/dos/process-types.inc','lib/dos/task-process.inc',
                'tools/generate_build_info.py','lib/exec/taskinspect.act','lib/io/deviceinspect.act','lib/fs/fsinspect.act',
                'lib/fs/fsactive.act','lib/fs/fsabort.act','lib/fs/fsoperation.act','lib/io/blockio.act','lib/io/blockcache.act','lib/io/blockwire.act','lib/io/blocktypes.act',
                'lib/mydos/mydosfile.act','lib/mydos/mydos.act','lib/mydos/mydostypes.act',
                'lib/dos/dosstreams.act','lib/dos/dosgroup.act','lib/dos/pipeline.act','lib/dos/dospipe.act','lib/dos/dosraw.act','lib/dos/doscancel.act','lib/dos/dosbreak.act','lib/dos/dosbreaktypes.act','lib/dos/doscooked.act','lib/dos/cookedline.act','lib/dos/dos-cooked-types.inc','lib/dos/dosobjects.act','lib/fs/fsmux.act','lib/fs/fsmount.act','lib/fs/fsmanager.act','lib/fs/fspacket.act','lib/fs/fsdirectory.act','lib/fs/fslocks.act','lib/fs/fsobjects.act','lib/fs/fsrelative.act','lib/fs/fsinfo.act','lib/dos/dos-implementation.inc','lib/dos/doscalls.act','lib/fs/fsio.act','lib/fs/fsboot.act','lib/fs/fsworker.act','lib/fs/fsinit.act','lib/fs/fsregistry.act','lib/fs/fsnames.act','lib/fs/fssystem.act','lib/fs/fsports.act','lib/fs/fstypes.act','lib/fs/fshandler.act','lib/dos/dos-registry-types.inc','lib/dos/doscore.act','lib/dos/dos-core-types.inc','lib/dos/dosclient.act','lib/dos/task-dos.inc','platform/altirraos/dos.s',
                'abi/dos.json','lib/dos/dos.act','lib/dos/dos-types.inc','lib/dos/dos-packets.inc','lib/dos/doswire.act','tools/generate_dos.py',
                'lib/io/siodriver.act','lib/io/sio-requests.inc','lib/io/iotestdriver.act','lib/io/sio-lifetime.inc','lib/exec/task-lifetime.inc','lib/exec/execproducer.act','lib/io/iocore.act','lib/io/task-io.inc','lib/io/io-call-types.inc','platform/altirraos/io.s',
                'abi/io.json','abi/sio.json','lib/exec/exec-io-types.inc','tools/generate_io.py',
                'abi/ports.json','lib/exec/exec-port-types.inc','lib/exec/port-call-types.inc','tools/generate_ports.py',
                'lib/exec/task-ports.inc','lib/exec/portcore.act','platform/altirraos/ports.s',
                'abi/tasks.json','lib/exec/taskpolicy.act','lib/exec/taskmemory.act','lib/exec/task-signals.inc','lib/exec/task-wakes.inc',
                'abi/sio-adapter.json','tools/generate_sio_adapter.py','platform/altirraos/sio.s','platform/altirraos/sio-state.inc','lib/io/sioadapter.act',
                'platform/altirraos/signal-irq.s','platform/altirraos/signal-atomic.s','platform/altirraos/fast-services.s','platform/altirraos/fast-getmsg.inc','platform/altirraos/serial-irq.inc',
                'platform/altirraos/heap.s','platform/altirraos/heap-probe.s','lib/exec/task-memory.inc','lib/exec/heap-call-types.inc',
                'lib/exec/heappolicy.act','lib/exec/heap-system.inc','lib/exec/heapcore.act','lib/exec/heap-constants.inc','lib/exec/exec-memory-types.inc','tools/generate_heap.py',
                'lib/exec/exec-task-types.inc','lib/exec/execlists.act','tools/generate_tasks.py','platform/altirraos/tasks.s')},
            task_generated={name:sha256(output/name) for name in (
                'execbuild.act','exec-build.json',
                'dos.inc','dos-action.inc','dos-storage-action.inc','task-kernel/dosraw.act','task-kernel/doscore.act',
                'io.inc','io-action.inc','io-storage-action.inc','sio-storage-action.inc',
                'ports.inc','ports-action.inc','port-packets.inc','ports-storage.inc','ports-storage-action.inc',
                'heappolicy.act','heap-storage.inc','heap.inc','heap-action.inc','heap.json','tasks.inc','tasks-action.inc','tasks-bindings.inc','signal-gateway.inc',
                'task-kernel/processstate.act','task-kernel/exec.act','task-kernel/taskpolicy.act','task-kernel/taskmemory.act','task-kernel/task-wakes.inc',
                'task-kernel/task-console.inc','task-kernel/task-signals.inc','task-kernel/exectasks.act','task-kernel/taskstacks.act','task-kernel/taskinspect.act','task-kernel/deviceinspect.act')})
    if tasks:
        provenance['task_generated'].update({name:sha256(output/name) for name in ('ioresident.act','ioresidentmeta.act')})
    if sio_request_probe:
        provenance['sio_request_probe']=True
        provenance['task_inputs']['tests/programs/sio_request_probe.inc']=sha256(ROOT/'tests/programs/sio_request_probe.inc')
        provenance['task_generated']['task-kernel/sio-requests-probe.inc']=sha256(output/'task-kernel/sio-requests-probe.inc')
    if sio_lifetime_probe:
        provenance['sio_lifetime_probe']=True
        provenance['task_inputs']['tests/programs/sio_lifetime_probe.inc']=sha256(ROOT/'tests/programs/sio_lifetime_probe.inc')
        provenance['task_generated']['task-kernel/sio-lifetime-probe.inc']=sha256(output/'task-kernel/sio-lifetime-probe.inc')
    if tasks and irq_probe==10:
        provenance['task_inputs']['platform/altirraos/console-probe.s']=sha256(ROOT/'platform/altirraos/console-probe.s')
        provenance['console_probe_storage']={'base':task_storage['BASE']+0xc00,'bytes':288,'arena_reserved_bytes':4096,'added_bank_zero_bytes':0}
    if console_native:
        provenance['console_test']=console_test
        provenance['console_enabled']=console_enabled
        provenance['console_start']=console_start
        provenance['console_inputs']={name:sha256(ROOT/name) for name in ('abi/console.json','tools/generate_console.py',
            'lib/console/console.act','lib/console/consolewindows.act','lib/console/consoletiling.act','lib/console/consoleforeground.act','lib/dos/dosbreaktypes.act','lib/console/consoledisplay.act','lib/console/consoletypes.act','lib/console/consolecore.act','lib/console/consoledriver.act','lib/console/console-requests.inc','lib/console/console-lifetime.inc','lib/console/consoleadapter.act','lib/console/consolecapture.act','lib/console/consoleinput.act','lib/console/task-console.inc',
            'platform/altirraos/console-layout.inc','platform/altirraos/console.s')}
        provenance['task_generated'].update({name:sha256(output/name) for name in ('console-storage.inc','console-storage-action.inc','console-action.inc','console-tables.bin','task-kernel/consoleforeground.act','task-kernel/consoledriver.act','task-kernel/consoleinput.act','task-kernel/consoledisplay.act')})
    if tasks and (dos_test or dos_system):provenance['task_generated']['task-kernel/dos.act']=sha256(output/'task-kernel/dos.act')
    if banked:
        provenance.update(banked=True, memory=memory, memory_sha256=memory_hash,
                          manifest_sha256=sha256(output/'manifest.bin'), kernel_init=kernel_init,
                          banked_inputs={name:sha256(ROOT/name) for name in (
                              'abi/memory-v1.json', 'abi/boot-v1.json', 'tools/boot_config.py',
                              'lib/exec/bootconfig.act', 'lib/exec/execmemory.act', 'platform/altirraos/loader.s',
                              'tools/generate_memory.py', 'tools/task_capacity.py', 'tools/banked_image.py', 'tools/native_program.py')},
                          generated_sha256={name:sha256(output/name) for name in (
                              'memory.inc','memory-action.inc','memory.json','boot-config.inc',
                              'boot-config-action.inc','bootconfig.act','loader-image.inc',
                              'loader.cfg','loader.bin')})
    (output / "build.json").write_text(json.dumps(provenance, indent=2)+"\n")
    return {"xex": xex, "labels": labels, "image": image, "build": provenance, "output": output}


def execute(bridge, program, expected_status=0, timer_irq=False, before_run=None,
            frame_limit=None, timeout=None, load_timeout=180, preloaded=False):
    if frame_limit is None:
        frame_limit = 1200 if program['build'].get('tasks') else 120
    if timeout is None:
        timeout = 60 if program['build'].get('tasks') else 15
    bridge.bp_clear_all()
    if not preloaded:
        bridge.boot(str(program["xex"]))
        if program["build"].get("banked"):
            run_to(bridge, program["labels"]["loader_start"], frame_limit=1800, timeout=load_timeout)
            bridge.bp_set(program["labels"]["start"])
        run_to(bridge, program["labels"]["start"])
    bridge.bp_clear_all()
    require(bridge.regs()["mode"] == "65C816", "Incorrect CPU mode")
    old_vectors = bridge.memdump(0x0256, 9)
    old_vbi = bridge.memdump(0x0222, 2)
    old_memlo = bridge.memdump(program['build']['memory']['constants']['OLD_MEMLO'], 2) if program['build'].get('banked') else bridge.memdump(0x02E7, 2)
    if timer_irq:
        # Real POKEY timer-1 IRQs, handled by the pinned ROM's default vector.
        # This is a test stimulus; the next cold boot restores the machine.
        bridge.poke(0xD208, 0)
        bridge.poke(0xD200, 0x80)
        bridge.poke(0xD201, 0)
        bridge.poke(0xD209, 0)
        bridge.poke(0x0010, 1)
        bridge.poke(0xD20E, 1)
    if before_run:
        before_run(bridge)
    # STATUS starts at $FFFF and is published by finish before restoring the
    # host. Qualify both the breakpoint and polling: REGS exposes only PC16.
    completion = adapter.STOPPED
    bridge.bp_set(program["labels"]["done"], condition=completion)
    run_to(bridge, program["labels"]["done"], frame_limit, timeout=timeout, condition=completion)
    state = bridge.memdump(adapter.STATE, 64)
    word = lambda offset: int.from_bytes(state[offset:offset+2], "little")
    result = {"status": word(0), "native_nmi_count": word(2), "native_irq_count": word(4),
              "os_busy": state[6], "return_s": word(8), "return_d": word(10), "return_p": state[12],
              "fault_required": word(24), "fault_s": word(26),
              "clock_start": state[28], "clock_end": state[29],
              "return_dbr": state[30], "return_e": state[31]}
    (program["output"] / "state.bin").write_bytes(state)
    require(result["status"] == expected_status, f"Unexpected termination: {result}")
    if expected_status==0xff93:
        regs=bridge.regs()
        require(int(regs['P'].lstrip('$'),16)&4,'Reset-required park left IRQs enabled')
        result['platform_reset_required']=True
    else:
        require(bridge.memdump(0x0256, 9) == old_vectors, "Native interrupt/COP vectors not restored")
        require(bridge.memdump(0x0222, 2) == old_vbi, "Immediate VBI vector not restored")
        require(bridge.memdump(0x02E7, 2) == old_memlo, "OS memory reservation not restored")
    cooperative = program["build"].get("cooperative", False)
    guards = [0x0100, adapter.TASK0_STACK_BASE-16, adapter.TASK0_STACK_CEILING+1]
    domains = [(adapter.TASK0_DP, adapter.TASK0 if cooperative else adapter.STATE, 0,
                adapter.TASK0_STACK_FLOOR, adapter.TASK0_STACK_CEILING)]
    if cooperative:
        guards += [adapter.KERNEL_STACK_BASE-16, adapter.KERNEL_STACK_CEILING+1,
                   adapter.TASK1_STACK_BASE-16, adapter.TASK1_STACK_CEILING+1]
        domains += [(adapter.TASK1_DP, adapter.TASK1, 0, adapter.TASK1_STACK_FLOOR, adapter.TASK1_STACK_CEILING),
                    (adapter.KERNEL_DP, adapter.KERNEL_OWNER, 1, adapter.KERNEL_STACK_FLOOR, adapter.KERNEL_STACK_CEILING)]
        result.update({"current": state[35], "switching": state[36], "switches": word(38),
                       "gateway_calls": word(40), "os_calls": word(42), "forwarded_cops": word(44),
                       "os_owner": state[50], "tick_pending": state[48], "vbi_count": word(52),
                       "vbi_dispatches": word(54), "irq_depth": word(56), "tasks": list(bridge.memdump(adapter.TASK0, 32))})
    if program['build'].get('tasks'):
        guards = [0x0100, adapter.KERNEL_STACK_BASE-16, adapter.KERNEL_STACK_CEILING+1]
        domains = [(adapter.KERNEL_DP, adapter.KERNEL_OWNER, 1, adapter.KERNEL_STACK_FLOOR, adapter.KERNEL_STACK_CEILING)]
        task_records = []
        task_constants = program['build']['task_storage']
        from banked_test_memory import read as far_read
        metadata = far_read(bridge,task_constants['BASE'],task_constants['METADATA_BYTES'],program['output'])
        read_task = lambda address,size: metadata[address-task_constants['BASE']:address-task_constants['BASE']+size]
        for slot, pool in enumerate(program['build']['memory']['task_pools']):
            dp, base = pool['dp'], pool['stack_base']
            stack_bytes=pool.get('stack_bytes',1536)
            guards += [base-16,base+stack_bytes]
            owner = task_constants['BASE']+slot*task_constants['SIZE']
            domains.append((dp,owner,0,base+256,base+stack_bytes-1))
            task_records.append(list(read_task(owner, task_constants['SIZE'])))
        result['task_records'] = task_records
        header = task_constants['READY']
        result['ready_queue'] = list(read_task(header, task_constants['READY_BYTES']))
        empty_ready = list((header+3).to_bytes(3,'little')+bytes(3)+header.to_bytes(3,'little'))
        result['live_tasks'] = read_task(task_constants['LIVE'], 1)[0]
        result['idle_runs'] = int.from_bytes(read_task(task_constants['IDLE_RUNS'], 2), 'little')
        result['created'] = int.from_bytes(read_task(task_constants['CREATED'], 2), 'little')
        result['signal_nmi_checkpoints'] = bridge.peek16(adapter.PROBE0) if program['build'].get('signal_probe') else 0
        result['wake_queue'] = list(read_task(task_constants['WAKE'],9))
        result['root_task'] = list(read_task(task_constants['ROOT'],task_constants['TASK_SIZE']))
        padding=min(value for key,value in program['build']['task_storage'].items() if key.startswith('TCB_PADDING') or key=='TCB_LIFETIMEPAD')
        require(all(r[padding:] == [0]*(64-padding) for r in task_records), 'Context stride padding changed')
    for address in guards:
        require(bridge.memdump(address, 16) == bytes([0xA5])*16, f"Guard changed at ${address:04x}")
    from native_abi import FIELDS
    for dp, owner, kind, floor, ceiling in domains:
        expected = owner.to_bytes(3,"little") + struct.pack("<BHH", kind, floor, ceiling)
        require(bridge.memdump(dp+FIELDS["owner_pointer"]["offset"], len(expected)) == expected,
                f"Domain metadata changed: ${dp:04x}")
        reserved = FIELDS["reserved_zero"]
        require(bridge.memdump(dp+reserved["offset"], reserved["size"]) == bytes(reserved["size"]),
                f"Domain reserved bytes changed: ${dp:04x}")
    if expected_status == 0:
        if cooperative:
            if program['build'].get('tasks'):
                require(all(r[8] in (0, 5) and r[28:32] == [0]*4 for r in result['task_records'][:task_constants['CAPACITY']])
                        and result['live_tasks'] == 0 and result['idle_runs'] > 0
                        and result['ready_queue'] == empty_ready, 'General task cleanup mismatch')
            else:
                require(result["tasks"][2] == 2 and result["tasks"][18] == 2, 'Task cleanup mismatch')
            require(result["os_busy"] == 0 and result["os_owner"] == 255
                    and result["switching"] == 0 and result["irq_depth"] == 0,
                    f"Cooperative cleanup mismatch: {result}")
        else:
            require((result["return_s"], result["return_d"], result["os_busy"]) == (adapter.TASK0_STACK_TOP, adapter.TASK0_DP, 0),
                    f"Native return context mismatch: {result}")
        require(result["return_p"] & 0x3C == program["build"]["initial_i"], "Native boundary flags changed")
        require(result["return_dbr"] == 0 and result["return_e"] == 0, "Native bank/mode boundary changed")
    screen_address = int.from_bytes(bridge.memdump(0x58, 2), "little")
    screen = bridge.memdump(screen_address, 960)
    (program["output"] / "screen.bin").write_bytes(screen)
    result["guards"] = "intact"
    return result, screen


def platform_files(bridge_dir, rom):
    require(sha256(rom) == PLATFORM_PIN["rom"]["sha256"], "Incorrect ROM hash")
    require(sha256(bridge_dir / "AltirraBridgeServer") == PLATFORM_PIN["emulator"]["sha256"],
            "Incorrect emulator hash")


def verify_machine(bridge, rom, pin=PLATFORM_PIN):
    config = bridge.config()
    for key, value in {"machine": "800XL", "memory": "64K", "video": "pal",
                       "basic": False, "highbanks": pin['machine']['high_banks'], "addons": "off"}.items():
        require(config.get(key) == value, f"Incorrect machine setting: {key}")
    raw = rom.read_bytes()
    require(bridge.memdump(0xC000, 0x1000) == raw[:0x1000], "Wrong mapped kernel")
    require(bridge.memdump(0xD800, 0x2800) == raw[0x1800:], "Wrong mapped upper kernel")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler-dir", type=Path, required=True)
    parser.add_argument("--allow-compiler-override", action="store_true")
    parser.add_argument("--compiler-pin", type=Path, help="Explicit candidate contract; requires --allow-compiler-override")
    parser.add_argument("--source", type=Path, default=ROOT / "examples/hello.act")
    parser.add_argument("--output", type=Path, default=ROOT / "build/hello")
    parser.add_argument("--no-opt", action="store_true")
    parser.add_argument("--tasks", action="store_true", help="Classic Exec Task API; root counts toward task capacity")
    parser.add_argument('--dos-mounts',type=Path,help='Explicit read-only MyDOS mount configuration (requires --tasks)')
    parser.add_argument("--console",action=argparse.BooleanOptionalAction,default=None,help="Start the resident native console (requires --tasks; defaults to kernel config)")
    parser.add_argument("--stack-checks",action=argparse.BooleanOptionalAction,default=None,help="Compiler and assembly stack checks (default: kernel config, enabled)")
    parser.add_argument("--cooperative", action="store_true", help="Launch two tasks with the Exec gateway")
    parser.add_argument("--preemptive", action="store_true", help="Launch two tasks with VBI preemption")
    parser.add_argument('--banked', action='store_true', help='Boot the kernel with INITAD in upper RAM')
    parser.add_argument('--kernel-bank',type=int)
    parser.add_argument('--task-capacity',type=int,default=4)
    parser.add_argument('--worker-stack',type=int)
    parser.add_argument('--idle-stack',type=int)
    parser.add_argument('--max-banks', type=int, help='Kernel bank table limit (default 16)')
    parser.add_argument('--memory-profile', type=Path, help='Explicit banked memory map')
    parser.add_argument('--kernel-config', type=Path, help='Kernel memory build configuration')
    parser.add_argument("--bridge-dir", type=Path, help="Also execute on the pinned AltirraBridge")
    parser.add_argument("--rom", type=Path, default=ROOT / "build/firmware/altirraos-816.rom")
    args = parser.parse_args()
    require(args.banked or args.tasks or not (args.max_banks is not None or args.memory_profile or args.kernel_config or args.kernel_bank is not None or args.task_capacity!=4),
            'Memory configuration options require --banked')
    require(args.tasks or args.dos_mounts is None,'--dos-mounts requires --tasks')
    from generate_dos_mounts import load as load_mounts
    mount_config=load_mounts(args.dos_mounts or ROOT/'config/dos-mounts.json') if args.tasks else dict(mounts=[],system_mount=None)
    toolchain = compiler(args.compiler_dir, args.allow_compiler_override,
                         json.loads(args.compiler_pin.read_text()) if args.compiler_pin else None)
    program = build(toolchain, args.source, args.output, not args.no_opt, cooperative=args.cooperative,
                    preemptive=args.preemptive, banked=args.banked, max_banks=args.max_banks,
                    memory_profile=args.memory_profile, kernel_config=args.kernel_config, tasks=args.tasks, kernel_bank=args.kernel_bank,task_capacity=args.task_capacity,worker_stack=args.worker_stack,idle_stack=args.idle_stack,dos_mounts=mount_config['mounts'],system_mount=mount_config['system_mount'],console=args.console,stack_checks=args.stack_checks)
    print(f"Built {program['xex']}", flush=True)
    if args.bridge_dir:
        bridge_dir, rom = args.bridge_dir.resolve(), args.rom.resolve()
        platform_files(bridge_dir, rom)
        pin = json.loads((ROOT/program['build']['memory']['profile']['pin']).read_text()) if program['build'].get('banked') else PLATFORM_PIN
        with emulator(bridge_dir, rom, args.output, pin=pin) as bridge:
            verify_machine(bridge, rom, pin)
            result, _ = execute(bridge, program)
        (args.output / "result.json").write_text(json.dumps(result, indent=2)+"\n")
        print(f"Native program returned with intact guards: {result}")


if __name__ == "__main__":
    main()
