Exec816 text console demo

The upper area is your shell.
The lower area searches for primes.

Try these commands:
DIR
TYPE STORY.TXT
TASKS
MEM
HELLO | WC
CAT STORY.TXT | WC
CAT LONG.TXT | WC

Press BREAK during the long pipeline.
The prime search keeps running.
Run MEM again after commands finish.
EXIT closes the demo and returns to OS.

Command toolbox:
HEAD STORY.TXT LINES 5
GREP shell STORY.TXT NOCASE NUMBER
CKSUM STORY.TXT
HEXDUMP STORY.TXT LENGTH 32
CMP STORY.TXT STORY.TXT
LIST NAMES
MORE LONG.TXT
MORE: Space=page, Return=line, Q=quit.

Commands after changing directory:
CD SYS:WORK
HEAD SYS:STORY.TXT LINES 3
HEAD MISSING
HEAD ?
PATH
CAT SYS:STORY.TXT | WC
CD SYS:

Writable toolbox (WORK: on D8):
MAKEDIR WORK:NOTES
COPY STORY.TXT WORK:NOTES/ONE.TXT
RENAME WORK:NOTES/ONE.TXT WORK:NOTES/TWO.TXT
HELLO | TEE WORK:LOG.TXT
HELLO | TEE WORK:LOG.TXT APPEND
DELETE WORK:NOTES/TWO.TXT
DELETE WORK:NOTES
COPY/TEE truncate unless APPEND is used.
RENAME stays within one directory.
DELETE accepts files or empty directories.

Prompt editing and ten-command history:
Ctrl-A/E: start/end. Ctrl-B/F: left/right.
Ctrl-U: clear. Ctrl-K: delete to end.
Ctrl-W: delete word. Ctrl-P/N: history.
Atari Ctrl-+/*: left/right, Ctrl--/=: up/down.
Past newest history restores your draft.

Commands live in SYS:C, assigned as C:.
PATH searches here, then C: by default.
PATH RESET restores the C: search entry.
Every supplied command supports ? help.
Errors are explained on the console.
