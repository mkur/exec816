; Native PBI transactions. IRQ excludes ROM PBI dispatch; SWITCHING excludes
; Task transitions. The pinned VBI chain never accesses IDE registers/latches.
; It still runs and records ticks. Preserve selection and its OS shadow.
.include "ideplus.inc"
.segment "SIGNAL_CODE"
.a16
.i16
.export ideplus_read_register,ideplus_read_register_end
.export ideplus_write_register,ideplus_write_register_end
.export ideplus_read_words,ideplus_read_words_end
.export ideplus_write_words,ideplus_write_words_end

; DP $80..$87 is the caller's call-clobbered workspace, never global storage.
IP_POINTER = $80
IP_VALUE = $84
IP_SELECTED = $85
IP_RESULT = $86

ideplus_enter:
    sep #$20
    lda #1
    sta f:E816_SWITCHING
    lda f:$0247
    sta IP_SELECTED
    lda #1                      ; configured initial PBI ID 0
    sta f:$0247
    sta f:$d1ff
    rts
ideplus_leave:
    lda IP_SELECTED
    sta f:$0247
    sta f:$d1ff
    lda #0
    sta f:E816_SWITCHING
    rep #$20
    rts

.a16
ideplus_read_register:
    signal_stack_check 9
    jsr io_context
    lda 4,s
    tax
    php
    sei
    jsr ideplus_enter
    lda f:$00d100,x
    sta IP_RESULT
    jsr ideplus_leave
    plp
    lda IP_RESULT
    and #$ff
    rtl
ideplus_read_register_end:

.a16
ideplus_write_register:
    signal_stack_check 9
    jsr io_context
    lda 4,s
    tax
    lda 6,s
    sep #$20
    sta IP_VALUE
    rep #$20
    php
    sei
    jsr ideplus_enter
    lda IP_VALUE
    sta f:$00d100,x
    jsr ideplus_leave
    plp
    rtl
ideplus_write_register_end:

.a16
ideplus_read_words:
    signal_stack_check 9
    jsr io_context
    lda 4,s
    sta IP_POINTER
    sep #$20
    lda 6,s
    sta IP_POINTER+2
    rep #$20
    ldy #0
ideplus_read_pair:
    php
    sei
    jsr ideplus_enter
    lda f:$00d110
    sta [IP_POINTER],y
    iny
    lda f:$00d100
    sta [IP_POINTER],y
    iny
    jsr ideplus_leave
    plp
    cpy #512
    bcc ideplus_read_pair
    rtl
ideplus_read_words_end:

.a16
ideplus_write_words:
    signal_stack_check 9
    jsr io_context
    lda 4,s
    sta IP_POINTER
    sep #$20
    lda 6,s
    sta IP_POINTER+2
    rep #$20
    ldy #0
ideplus_write_pair:
    php
    sei
    jsr ideplus_enter
    iny
    lda [IP_POINTER],y
    sta f:$00d100
    dey
    lda [IP_POINTER],y
    sta f:$00d110
    iny
    iny
    jsr ideplus_leave
    plp
    cpy #512
    bcc ideplus_write_pair
    rtl
ideplus_write_words_end:
