; Ordinary library leaves, no COP service and no additional bank-zero state.
.segment "SIGNAL_CODE"
.export display_ticks,display_ticks_end,display_reset_required,display_reset_required_end
.a16
.i16
display_ticks:
    lda f:E816_VBI_COUNT
    rtl
display_ticks_end:
display_reset_required:
    jml reset_required
display_reset_required_end:
