/* SPDX-License-Identifier: MIT. Pinned vendor integration, not a public ABI. */
#include <exec/types.h>
#include <stdio.h>
#include <stddef.h>
#include "libc.h"
__attribute__((section("exec_layout"))) const UWORD ExecCRuntimeStdioLayout[]={
    sizeof(size_t),sizeof(fpos_t),sizeof(FILE),sizeof(struct __streamlist),
    offsetof(FILE,fs_fd),offsetof(FILE,fs_oflags),offsetof(FILE,fs_flags)};
