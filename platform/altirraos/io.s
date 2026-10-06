; Caller-domain checks precede public/private I/O. Established resident calls
; stay on the caller stack; admission and collection retain kernel packets.
.include "io.inc"
.segment "SIGNAL_CODE"
.a16
.i16
io_context:
    heap_context
    php
    sep #$20
    pla
    and #4
    rep #$20
    beq :+
    lda #FAULT_CONTEXT
    jml finish
:
    rts

.macro io_packet name, selector
.export name, .ident(.concat(.string(name), "_end"))
name:
    jsr io_context
    tsc
    clc
    adc #4
    tax
    ldy #T_PROFILE_TAG
    lda #selector
    cop E816_COP
    rtl
.ident(.concat(.string(name), "_end")):
.endmacro
io_packet io_open_dispatch, IO_SERVICE_OPEN_DEVICE
io_packet io_check_io, IO_SERVICE_CHECK_IO
io_packet io_create_check, IO_SERVICE_CREATE_CHECK
io_packet io_delete_check, IO_SERVICE_DELETE_CHECK
io_packet io_collect, IO_SERVICE_WAIT_REQUEST
io_packet io_test_close, IO_SERVICE_TEST_CLOSE
io_packet io_test_begin, IO_SERVICE_TEST_BEGIN
io_packet io_test_abort, IO_SERVICE_TEST_ABORT
io_packet io_test_step, IO_SERVICE_TEST_STEP
.macro io_caller name, target
.export name, .ident(.concat(.string(name), "_end"))
name:
    jsr io_context
    jml target
.ident(.concat(.string(name), "_end")):
.endmacro
io_caller io_close_device, IO_CLOSE
io_caller io_begin_io, IO_BEGIN
io_caller io_send_io, IO_SEND
io_caller io_abort_io, IO_ABORT
.export io_open_device,io_open_device_end
io_open_device:
    jsr io_context
    jml IO_OPEN
io_open_device_end:
.export io_create_request, io_create_request_end, io_delete_request, io_delete_request_end
io_create_request:
    jsr io_context
    jml IO_CREATE
io_create_request_end:
io_delete_request:
    jsr io_context
    jml IO_DELETE
io_delete_request_end:
.export io_wait_io, io_wait_io_end, io_do_io, io_do_io_end
io_wait_io:
    jsr io_context
    jml IO_WAIT
io_wait_io_end:
io_do_io:
    jsr io_context
    jml IO_DO
io_do_io_end:
