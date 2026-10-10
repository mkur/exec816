"""Physical cancellation at frozen offsets from observed workload boundaries."""
from file_selector_model import FIELDS as SELECTOR, FORM_SELECTOR
from generate_aes_server import expected_layout, layout
from native_program import require
from sio_transaction_trace import BASE_HZ
from test_shell_core import KEYS
from text_model import FIELDS, LOAD_PHASE


def at_offset(s, start, milliseconds):
    target = start+round(milliseconds*BASE_HZ/1000)
    now=s.b.eval_expr('@clk')
    require(now < target, 'Cancellation setup missed frozen offer time: %.3f ms' % ((now-start)*1000/BASE_HZ))
    s.rendezvous('@clk>=%d' % target)
    return s.b.eval_expr('@clk')


def escape(s, shared, a, click, key, settled):
    """Keep STORY.TXT while cancelling a LONG.TXT replacement during Read."""
    def value(address, size):
        return s.b.memdump(address,size).split(b'\0')[0]
    old = s.b.memdump(a+FIELDS['document'], 142)
    loads = s.number(a+FIELDS['loads'],4)
    first = s.number(a+FIELDS['first'],2)
    key('O');s.frames(100)
    context = next(c for i in range(4) if (c:=s.number(shared['contexts']+4*i,4)) and
                   s.number(c+layout()['Request']['fields']['global']+4,2)==s.number(a,2))
    form = s.number(context+dict(expected_layout())['C context form'],4)
    require(form,'Cancellation selector did not open')
    selector = s.number(form+FORM_SELECTOR,4)
    s.rendezvous('dw($%x)=1'%(selector+SELECTOR['valid']));s.frames(60)
    obj=selector+5*24
    click(s.number(selector+16,2)+s.number(obj+16,2)+12,
          s.number(selector+18,2)+s.number(obj+18,2)+8)
    for _ in value(selector+SELECTOR['file'],13):
        key('BACKSPACE');s.frames(8)
    for char in 'LONG.TXT':
        name,shift=KEYS[char]
        if shift:s.b._cmd_ok('KEY SHIFT down')
        key(name);s.frames(8)
        if shift:s.b._cmd_ok('KEY SHIFT up')
    require(value(selector+SELECTOR['file'],13)==b'LONG.TXT','Cancellation filename')
    key('RETURN')
    phase=a+FIELDS['load']+LOAD_PHASE
    s.rendezvous('dw($%x)=3'%phase)
    start=s.b.eval_expr('@clk')
    offered=at_offset(s,start,100)
    require(s.number(phase,2)==3,'Replacement completed before Escape')
    progress=s.b.memdump(a+FIELDS['load'],24).hex()
    key('ESC')
    s.rendezvous('dw($%x)=0'%phase);retired=s.b.eval_expr('@clk')
    settled();idle=s.b.eval_expr('@clk')
    require(s.number(a+FIELDS['loads'],4)==loads and s.number(a+FIELDS['first'],2)==first
            and s.b.memdump(a+FIELDS['document'],142)==old,'Escape replaced the document')
    require(value(a+FIELDS['status'],81)==b'Load cancelled','Escape was lost')
    return dict(kind='viewer_escape',boundary='Observed load.phase=READ',offset_ms=100,
                start=start,offered=offered,io_retired=retired,idle=idle,progress=progress,
                retire_ms=(retired-offered)*1000/BASE_HZ,idle_ms=(idle-offered)*1000/BASE_HZ,
                document_retained=True)


def shell_break(s):
    """The command's foreground publication starts this clock, not Panel paint."""
    for char in 'CAT LONG.TXT':s.press(char)
    previous=s.number(s.saved['scope']+14,4)
    s.b._cmd_ok('KEY RETURN down');s.frames(3);s.b._cmd_ok('KEY RETURN up')
    window=s.p['build']['memory']['console_storage']['WINDOWS']+s.console['WINDOWS_ITEMS']
    scope=window+s.console['WINDOW_SCOPE']
    s.rendezvous('(dw($%x)!=0)&(dw($%x)!=$%x)'%(scope,scope,s.saved['scope']&65535))
    start=s.b.eval_expr('@clk')
    offered=at_offset(s,start,1000)
    foreground=s.number(scope,3)
    require(foreground not in (0,s.saved['scope']),'CAT completed before BREAK')
    s.b._cmd_ok('KEY BREAK down');s.frames(3);s.b._cmd_ok('KEY BREAK up')
    s.ready(previous);s.result(304)
    retired=s.b.eval_expr('@clk')
    return dict(kind='shell_break',boundary='Observed foreground scope publication',offset_ms=1000,
                start=start,offered=offered,foreground=foreground,idle=retired,
                retire_ms=(retired-offered)*1000/BASE_HZ)
