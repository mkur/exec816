; Generated boot labels; each has a fixed 16-byte stride.
boot_labels:
    .byte "BOOT MEMLO=",0
    .res 4,0
    .byte "MEMTOP=",0
    .res 8,0
    .byte "KERNEL BANK=",0
    .res 3,0
    .byte "TABLE BANK=",0
    .res 4,0
    .byte "KERNEL DP=",0
    .res 5,0
    .byte "KERNEL STACK=",0
    .res 2,0
    .byte "RAM ADOPT=",0
    .res 5,0
    .byte "TASK/HEAP INIT=",0
    .res 0,0
    .byte "VBXE BASE=",0
    .res 5,0
    .byte "VBXE ID/REV=",0
    .res 3,0
    .byte "CONSOLE START=",0
    .res 1,0
    .byte "KERNEL READY=",0
    .res 2,0
    .byte "SKIP RAM BANK=",0
    .res 1,0
    .byte "VBXE rev=1.",0
    .res 4,0
    .byte "NO VBXE; IDs=",0
    .res 2,0
    .byte "VBXE NOT FX=",0
    .res 3,0
    .byte "VBXE BASELINE=",0
    .res 1,0
    .byte "VBXE BUSY=",0
    .res 5,0
    .byte "CONSOLE FAILED=",0
    .res 0,0
    .byte "KERNEL FAILED=",0
    .res 1,0
    .byte "System halted",0
    .res 2,0
