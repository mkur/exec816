; Short current-task lookup; no allocation, waiting or DOS continuation here.
.include "dos.inc"
.segment "SIGNAL_CODE"
.a16
.i16
heap_packet dos_current, DOS_SERVICE_CONTEXT
heap_packet dos_control, DOS_SERVICE_MOUNT_REFERENCE
