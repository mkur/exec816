"""Same serial deadlines; keyboard attribution to the actual editor redraw Write."""
import json
from console_concurrent_trace import analyze as console_timing,distribution
from sio_transaction_trace import read_events,BASE_HZ

def analyze(path,marks,media,size,speed,file_bytes):
    r=console_timing(path,marks,media,size,speed,file_bytes,key_count=9,
        keyboard_boundary='Physical raw capture; console finish-read call before publication; cooked adapter after its exact input WaitIO collection; cooked adapter immediately after that key’s echo Write completes. This observes retained cooked output, not a glyph anywhere on screen or physical scanout. Shared writers can move the row; the same native capture executes in observed and replay images.')
    r['keyboard']['capture_to_completed_editor_write_upper_bound']=r['keyboard'].pop('capture_to_observed_visible_echo_upper_bound')
    events=read_events(path)
    times=lambda name:[t for t,e in events if e[0]=='cpu'and int(e[4],16)==marks[name]]
    begins=times('command_begin');ends=times('command_end')
    # First completion is the physical ECHO. The remaining four parse/dispatch calls are marked.
    if len(begins)!=4 or len(ends)!=5 or any(a>b for a,b in zip(begins,ends[1:])):
        r['violations'].append('missing shell command completion')
    r['commands']=dict(physical_completions=len(ends)-len(begins),native_completions=len(begins),durations=distribution([b-a for a,b in zip(begins,ends[1:])]),
        samples=[dict(begin=a,end=b,microseconds=(b-a)/BASE_HZ*1e6)for a,b in zip(begins,ends[1:])])
    r['verdict']='fail'if r['violations']else 'pass';(path.parent/'timing.json').write_text(json.dumps(r,indent=2)+'\n');return r
