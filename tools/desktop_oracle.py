"""Independent full recomposition from desktop retained records (no GPU reads)."""
from generate_desktop import layout
from generate_layers import layout as layers_layout
from gem_render_oracle import Raster
from test_desktop_presentation import frame, rectangle, text
from test_gem_cursor import overlay
from native_program import require


def compose(bridge, program, font, terminal, pointer=(320, 120), external=None):
    def symbol(module, name):
        return next(d['address'] for d in program['image']['data']
                    if '_'+module+'_'+name.upper()+'_' in d['name'])
    service = int.from_bytes(bridge.memdump(symbol('DESKSTATE', 'service'), 3), 'little')
    types = layout()
    fields = types['Service']['fields']
    number = lambda data, offset, size=2: int.from_bytes(data[offset:offset+size], 'little')
    rect = lambda data, offset: tuple(int.from_bytes(data[offset+i:offset+i+2], 'little', signed=True) for i in (0, 2, 4, 6))
    focused = number(bridge.memdump(service+fields['focus'], 4), 0, 4)
    scene = service+fields['scene']
    lf = layers_layout()['Scene']['fields']
    count = number(bridge.memdump(scene+lf['count'], 1), 0, 1)
    require(count <= 6, 'Unbounded desktop scene')
    order = bridge.memdump(scene+lf['order'], count)
    windows = {}
    wf = types['Window']['fields']
    for slot in range(4):
        start = service+fields['windows']+slot*types['Window']['size']
        window = bridge.memdump(start, wf['content'])
        if number(window, wf['id'], 4):
            windows[number(window, wf['layer'], 4)] = (window, start+wf['content'])
    result = Raster(font)
    rectangle(result, (0, 0, 640, 240), 8)
    chrome = {}
    if any('_DESKSTATE_BARLAYER_' in d['name'] for d in program['image']['data']):
        chrome = {name: number(bridge.memdump(symbol('DESKSTATE' if name in ('barLayer', 'popupLayer') else 'DESKMENU', name), size), 0, size)
                  for name, size in [('barLayer', 4), ('popupLayer', 4), ('menu', 1),
                                     ('selected', 2)]}
    shown = set()
    for slot in order:
        at = scene+lf['items']+slot*layers_layout()['Layer']['size']
        if bridge.memdump(at+layers_layout()['Layer']['fields']['shown'], 1)[0]:
            shown.add(number(bridge.memdump(at, 4), 0, 4))
    active = next((w for w, _ in windows.values() if number(w, wf['id'], 4) == focused), None)

    def menu_layer(ident, bounds):
        left, top, right, bottom = bounds
        rectangle(result, bounds, 0)
        if ident == chrome['barLayer']:
            inverse = chrome['menu'] == 1
            rectangle(result, (0, 0, 320, 15), int(inverse))
            title = active[wf['title']:wf['title']+32].split(b'\0')[0] if active else b'Desktop'
            text(result, 8, 4, title, int(not inverse), int(inverse))
            inverse = chrome['menu'] == 2
            rectangle(result, (432, 0, 640, 15), int(inverse))
            text(result, 440, 4, b'Windows', int(not inverse), int(inverse))
            rectangle(result, (0, 15, 640, 16), 1)
        else:
            if chrome['menu'] == 2:
                entries = [(w[wf['title']:wf['title']+24].split(b'\0')[0], True)
                           for ident, (w, _) in windows.items() if ident in shown]
            else:
                entries = [(b'Next window', True), (b'Close', active is not None and active[wf['kind']] != 1)]
            for row, (label, enabled) in enumerate(entries):
                inverse = enabled and row == chrome['selected']
                rectangle(result, (left, top+row*16, right, top+(row+1)*16), int(inverse))
                text(result, left+8, top+row*16+4, label,
                     int(not inverse) if enabled else 8, int(inverse))
    for slot in reversed(order):
        start = scene+lf['items']+slot*layers_layout()['Layer']['size']
        if not bridge.memdump(start+layers_layout()['Layer']['fields']['shown'], 1)[0]:
            continue
        # Read retained geometry/content only, never the target's cached visible
        # regions or damage. This also avoids thousands of far debugger reads.
        layer = bridge.memdump(start, 12)
        bounds = rect(layer, 4)
        ident = number(layer, 0, 4)
        if chrome and ident in (chrome['barLayer'], chrome['popupLayer']):
            menu_layer(ident, bounds)
            continue
        window, content_address = windows[ident]
        left, top, right, bottom = bounds
        kind = window[wf['kind']]
        title = window[wf['title']:wf['title']+32].split(b'\0')[0]
        title = title[:(right-left-(32 if kind != 1 else 16))//8]
        cf = types['Content']['fields']
        content = bytearray(types['Content']['size'])
        if kind == 2:
            content[:cf['commands']] = bridge.memdump(content_address, cf['commands'])
            commands, text_bytes = number(content, cf['count']), number(content, cf['textBytes'])
            require(commands <= 32 and text_bytes <= 256, 'Unbounded retained content')
            length = commands*types['Command']['size']
            content[cf['commands']:cf['commands']+length] = bridge.memdump(content_address+cf['commands'], length)
            content[cf['text']:cf['text']+text_bytes] = bridge.memdump(content_address+cf['text'], text_bytes)
        frame(result, bounds, title, number(window, wf['id'], 4) == focused,
              number(content, cf['background']) if kind == 2 else 0, close=kind != 1)
        if kind == 1:
            terminal.paint(result, (left+8)//8, (top+16)//8, number(window, wf['id'], 4) == focused)
        elif kind == 3:
            from control_panel_oracle import retained
            context = number(bridge.memdump(content_address-wf['content']+wf['widgets'], 3), 0, 3)
            retained(bridge, result, context,
                     (left+8, top+16, right-8, bottom-8),
                     number(window, wf['id'], 4) == focused)
        elif kind == 4:
            require(external is not None, "External application needs an independent painter")
            external(result, title, bounds)
        else:
            for index in range(number(content, cf['count'])):
                start = cf['commands']+index*types['Command']['size']
                command = content[start:start+types['Command']['size']]
                df = types['Command']['fields']
                l, t, r, b = rect(command, df['bounds'])
                pen = command[df['pen']]
                if command[df['kind']] == 1:
                    rectangle(result, (left+8+l, top+16+t, left+8+r, top+16+b), pen)
                else:
                    offset, length = number(command, df['offset']), number(command, df['count'])
                    value = content[cf['text']+offset:cf['text']+offset+length]
                    text(result, left+8+l, top+16+t, value, pen, number(content, cf['background']))
    return overlay(result, pointer)
