"""Independent AES rasterization of retained models and the compiled demo form."""
import struct
import sys
from native_program import ROOT, require
from test_desktop_presentation import frame


def draw(result, objects, labels, bounds, focus=-1):
    sys.path.insert(0, str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    tree = [a.Obj(*obj) for obj in objects]
    left, top, right, bottom = bounds
    tree[0].ob_x += left
    tree[0].ob_y += top
    device = v.VDI()
    device.call(v.V_OPNWK, (), v.WORK_IN)
    device.dev.s.mem[:76800] = result.packed()
    aes = a.AES(device, tree, {k: a.Text(value) for k, value in labels.items()})
    aes.gsx_start()
    aes.gsx_sclip(a.Rect(left, top, right-left, bottom-top))
    aes.ob_draw(0, 7)
    if focus >= 0:
        # Find ancestry from the public tree, not the target's cached bounds.
        parents = {}
        for index, obj in enumerate(tree):
            child = obj.ob_head
            while child >= 0:
                require(child not in parents, 'Invalid oracle tree')
                parents[child] = index
                if child == obj.ob_tail:
                    break
                child = tree[child].ob_next
        obj = tree[focus]
        x, y = obj.ob_x, obj.ob_y
        parent = parents.get(focus)
        while parent is not None:
            x += tree[parent].ob_x
            y += tree[parent].ob_y
            parent = parents.get(parent)
        for xx in range(x+3, x+obj.ob_width-3):
            device.dev.plot_xor(xx, y+obj.ob_height-3)
    packed = device.dev.s.mem[:76800]
    result.pixels[:] = bytes(n for byte in packed for n in (byte >> 4, byte & 15))


def retained(bridge, result, context, bounds, focused):
    header = bridge.memdump(context, 24)
    count, size = struct.unpack_from('<HH', header, 8)
    require(count <= 32 and size <= 1024, 'Unbounded widget model')
    data = bridge.memdump(context+24, count*24)
    text = bridge.memdump(context+792, size)
    objects = [list(struct.unpack_from('<hhhHHHIhhhh', data, i*24)) for i in range(count)]
    labels = {}
    for index, obj in enumerate(objects):
        if obj[3] in (26, 28):
            labels[index+1] = text[obj[6]:].split(b'\0')[0].decode('ascii')
            obj[6] = index+1
    focus = struct.unpack_from('<h', header, 18)[0] if focused else -1
    draw(result, objects, labels, bounds, focus)


def panel(result, focused=False, status='Ready', toggle=0, radio=4, focus=2,
          bounds=(432, 80, 624, 224), pressed=-1):
    left, top, right, bottom = bounds
    frame(result, bounds, b'Control Panel', focused, 8, close=True)
    objects = [
        [-1,1,7,20,0,0,0x78,0,0,176,120],
        [2,-1,-1,28,0,0,1,8,8,160,8],
        [3,-1,-1,26,1,toggle,2,8,24,72,16],
        [4,-1,-1,26,1,8,3,96,24,72,16],
        [5,-1,-1,26,17,int(radio==4),4,8,56,72,16],
        [6,-1,-1,26,17,int(radio==5),5,96,56,72,16],
        [7,-1,-1,26,7,0,6,8,88,72,16],
        [0,-1,-1,26,37,0,7,96,88,72,16]]
    if pressed >= 0:
        objects[pressed][5] ^= 1
    labels = dict(enumerate((status, 'Toggle', 'Locked', 'Small', 'Large', 'Apply', 'Cancel'), 1))
    draw(result, objects, labels, (left+8, top+16, right-8, bottom-8), focus if focused else -1)
