; Host packaging metadata. This virtual section is never loaded into bank zero.
              .section registers,noinit
              .section zhuge,bss
              .section execinfo,rodata
              .public __exec_image_info
__exec_image_info:
              .long 0x31434345
              .long .sectionStart zhuge
              .long .sectionSize zhuge
              .long .sectionSize registers
