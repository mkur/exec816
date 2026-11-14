/* SPDX-License-Identifier: MIT */
#include <compat/gemdos.h>
#include <stdlib.h>
void Pterm(WORD status) { exit(status); }
void Pterm0(void) { exit(0); }
