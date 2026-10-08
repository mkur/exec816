"""Physical desktop-menu checks; guest memory is observed, never patched."""
from generate_desktop import layout
from generate_layers import layout as layer_layout
from native_program import require


class Menus:
    def __init__(self, session, click, move):
        self.s, self.click, self.move = session, click, move
        self.types, self.layers = layout(), layer_layout()
        self.service = session.number(self.at('DESKSTATE', 'service'), 3)
        self.focus_address = self.service+self.types['Service']['fields']['focus']
        self.closed = []

    def at(self, module, name):
        return next(d['address'] for d in self.s.p['image']['data']
                    if '_'+module+'_'+name.upper()+'_' in d['name'])

    def focus(self):
        return self.s.number(self.focus_address, 4)

    def windows(self):
        s = self.s
        scene = self.service+self.types['Service']['fields']['scene']
        lf = self.layers['Scene']['fields']
        count = s.number(scene+lf['count'], 1)
        order = s.b.memdump(scene+lf['order'], count)
        visible = []
        for slot in order:
            at = scene+lf['items']+slot*self.layers['Layer']['size']
            if s.number(at+self.layers['Layer']['fields']['shown'], 1):
                visible.append(s.number(at, 4))
        result = []
        wf = self.types['Window']['fields']
        for slot in range(4):
            at = self.service+self.types['Service']['fields']['windows']+slot*self.types['Window']['size']
            ident, layer = s.number(at+wf['id'], 4), s.number(at+wf['layer'], 4)
            if ident and layer in visible:
                title = s.b.memdump(at+wf['title'], 65).split(b'\0')[0].decode('ascii')
                result.append(dict(id=ident, title=title, rank=visible.index(layer)))
        return result

    def key(self, key, ctrl=False, shift=False):
        b = self.s.b
        if ctrl: b._cmd_ok('KEY CTRL down')
        if shift: b._cmd_ok('KEY SHIFT down')
        b._cmd_ok('KEY '+key+' down'); self.s.frames(3)
        b._cmd_ok('KEY '+key+' up')
        if shift: b._cmd_ok('KEY SHIFT up')
        if ctrl: b._cmd_ok('KEY CTRL up')
        self.s.frames(85)

    def select(self, title):
        windows = self.windows()
        row = next(i for i, window in enumerate(windows) if title in window['title'])
        target = windows[row]['id']
        self.click(472, 8)
        require(self.s.number(self.at('DESKMENU', 'menu'), 1) == 2, 'Windows menu did not open')
        self.click(472, 24+row*16)
        self.s.rendezvous('dw($%x)=%d' % (self.focus_address, target))
        self.s.frames(75)
        require(self.focus() == target, 'Menu selected the wrong window')
        return target

    def close(self):
        owner = self.focus()
        candidates = [w for w in self.windows() if w['id'] != owner]
        expected = min(candidates, key=lambda w: w['rank'])['id'] if candidates else 0
        self.click(80, 8)
        self.click(40, 40)
        self.s.rendezvous('dw($%x)=%d' % (self.focus_address, expected))
        require(self.focus() == expected, 'Close did not restore the frontmost remaining owner')
        self.closed.append(owner)
        self.s.saved['desktop_menu']['focus_restoration'] = True


def exercise(s, sy, click, move):
    menus = Menus(s, click, move)
    windows = menus.windows()
    require(len(windows) == 4, 'Desktop menu lost an application slot')
    panel_actions = s.number(sy['GEMPanel']+10, 4)
    shell = menus.select('Shell')
    # Shell covers the Counter's entire title. No geometry change is used to
    # reach it, and the switch must update the actual keyboard focus.
    counter = menus.select('Counter')
    require(counter != shell, 'Covered Counter was not selected')
    move(632, 232); s.cells('menu-covered-counter')
    ticks = s.number(sy['GEMCounter']+14, 4)
    click(472, 8)
    move(632, 232); s.cells('windows-menu-open')
    require(s.number(sy['GEMCounter']+14, 4) > ticks, 'Menu stopped Counter updates')
    menus.key('ESC')
    require(menus.focus() == counter and s.number(menus.at('DESKMENU', 'menu'), 1) == 0,
            'Escape changed focus or left menu open')
    s.cells('windows-menu-dismissed')
    click(472, 8); click(600, 220)
    require(menus.focus() == counter, 'Outside menu click passed through')
    click(472, 8); move(472, 24)
    s.b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(25)
    menus.key('ESC')
    s.b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(70)
    require(menus.focus() == counter and not s.number(menus.at('DESKMENU', 'menu'), 1),
            'Escape during held menu selection activated an entry')
    # Complete forward/reverse cycles, including the unfiltered GEM and native
    # console keyboard routes; Ctrl+Tab must never become an application Tab.
    ids = [w['id'] for w in windows]
    current = ids.index(counter)
    for reverse in (False, True):
        for _ in windows:
            current = (current+(-1 if reverse else 1)) % len(ids)
            menus.key('TAB', ctrl=True, shift=reverse)
            require(menus.focus() == ids[current], 'Keyboard cycle skipped a window')
    menus.key('ESC', ctrl=True)
    require(s.number(menus.at('DESKMENU', 'menu'), 1) == 2, 'Keyboard menu shortcut failed')
    menus.key('TAB'); menus.key('RETURN')
    require(menus.focus() == ids[1], 'Keyboard menu selection failed')
    menus.select('Shell')
    click(80, 8); click(40, 40)
    require(menus.focus() == shell and len(menus.windows()) == 4, 'Disabled shell Close acted')
    move(632, 232); s.cells('shell-close-disabled')
    menus.key('ESC')
    # Next window is the active-window menu's first action.
    click(80, 8); click(40, 24)
    require(menus.focus() == ids[(ids.index(shell)+1) % len(ids)], 'Next window menu action')
    menus.select('Control Panel')
    require(s.number(sy['GEMPanel']+10, 4) == panel_actions, 'Desktop menu leaked input into Panel')
    # A held application button keeps its gesture when dragged across the bar.
    move(456, 104); s.b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(30)
    move(472, 8); s.b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(70)
    require(s.number(sy['GEMPanel']+10, 4) == panel_actions
            and not s.number(menus.at('DESKMENU', 'menu'), 1), 'Bar stole an application gesture')
    # The title remains reachable below the bar; restore its original position.
    for start, end, work_y in [((480, 56), (480, 8), 32), ((480, 24), (480, 56), 64)]:
        move(*start); s.b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(20)
        move(*end); s.b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(90)
        require(s.number(sy['GEMPanel']+36, 2) == work_y, 'Title drag crossed the desktop bar')
    move(632, 232); s.cells('menu-panel-restored')
    s.saved['desktop_menu'] = dict(windows=4, covered_counter=True, pointer=True,
        keyboard_cycle=8, keyboard_menu=True, outside_cancel=True, escape=True,
        disabled_close=True, next_window=True, independent_pixels=5,
        counter_during_menu=True, held_escape=True, gesture_ownership=True, drag_limit=True)
    print('Desktop menu, covered-window and keyboard checks passed', flush=True)
    return menus
