; SPDX-License-Identifier: MIT
; Copyright (c) 2026 Michal Kurcewicz and Exec816 contributors.
.include "fastbasic.inc"
.export FB_ARGUMENT, FB_ERROR, FB_DIAGNOSTIC, FB_DIAG_MESSAGES
.import error_msg_list
FB_DIAG_MESSAGES = error_msg_list
.segment "CODE"
; FastBasic USR passes each word high then low on the CPU stack.
FB_ARGUMENT:
    pla
    pla
    jsr FB_SERVICE_ARGUMENT
    rts
FB_ERROR:
    pla
    pla
    jsr FB_SERVICE_ERROR
    rts
FB_DIAGNOSTIC:
    pla
    pla
    jsr FB_SERVICE_DIAGNOSTIC
    rts
