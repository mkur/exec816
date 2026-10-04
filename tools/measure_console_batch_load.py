#!/usr/bin/env python3
"""Measure the eight-Task output/input load without requiring DMA at BREAK.

Focus damage can keep a continuously written view on bounded full-redraw
fallback. Z/A/Return still rendezvous with real BUSY; BREAK samples whichever
output phase is active and records the actual hardware state.
"""
import argparse
from pathlib import Path
from unittest.mock import patch
import measure_async_scroll as fixture
from native_program import require

original=fixture.instrument_loaded

def instrument(text,phase):
    text=original(text,phase)
    needle="            rendezvous(f'(db(${pending:x})!=0)&((db($d653)&3)!=0)',point='native_irq')"
    require(text.count(needle)==1,'Loaded BUSY rendezvous changed')
    text=text.replace(needle,'            if key!=\'BREAK\':'+needle.lstrip())
    return text.replace("print('Confirmed BUSY',key,flush=True)",
        "print('Input phase',key,'hardware_busy',bool(b.eval_expr('db($d653)&3')),flush=True)")

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reuse',action='store_true')
    p.add_argument('--replay',action='store_true')
    a=p.parse_args()
    with patch.object(fixture,'instrument_loaded',instrument):
        fixture.run(a.output,0,reuse=a.reuse,replay=a.replay,profile_turns=True)
