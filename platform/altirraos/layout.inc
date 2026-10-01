; Initial bank-zero hosted layout. Native images occupy $6000-$8fff.
STATE = E816_STATE
TASK_DP = $2200
STACK_BASE = $4200
STACK_FLOOR = $4300             ; includes a conservative interrupt reserve
STACK_CEILING = $47ff
STACK_TOP = $47fe
OS_STACK_TOP = $01ef
APP_BASE = $6000
APP_LIMIT = $9000

STATUS = STATE                 ; word: $ffff running, 0 returned, faults below
NMI_COUNT = STATE+2
IRQ_COUNT = STATE+4
OS_BUSY = STATE+6               ; byte; task switches deferred while nonzero
RETURN_S = STATE+8
RETURN_D = STATE+10
RETURN_P = STATE+12
OLD_MEMLO = STATE+14
OLD_NMI = STATE+16              ; 24-bit vectors
OLD_IRQ = STATE+19
FAULT_REQUIRED = STATE+24
FAULT_S = STATE+26
START_CLOCK = STATE+28
END_CLOCK = STATE+29
RETURN_DBR = STATE+30
RETURN_E = STATE+31

MEMLO = $02e7
MEMTOP = $02e5
VNMIN = $0259
VIRQN = $025c
VCOPN = $0256
VVBLKI = $0222
NMIEN = $d40e
CIOV = $e456

FAULT_STACK = 1
FAULT_MEMORY = 2
FAULT_RETURN = 3
FAULT_CONTEXT = 4
ERROR_POINTER = $ff01
ERROR_BUSY = $ff02
.if BANKED
WRITE_STACK_BYTES = 266         ; full save and 256-byte ROM buffer
.else
WRITE_STACK_BYTES = 10
.endif

.assert STACK_FLOOR-STACK_BASE >= A816_INTERRUPT_TASK_OR_BOOTSTRAP_HEADROOM_BASE_BYTES, error, "interrupt reserve"
.assert TASK_DP .mod A816_DP_ALIGNMENT = 0, error, "DP alignment"
