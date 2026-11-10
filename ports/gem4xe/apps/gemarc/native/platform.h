/* SPDX-License-Identifier: MIT */
#ifndef EXEC_GEMARC_PLATFORM_H
#define EXEC_GEMARC_PLATFORM_H
#include "arcfile.h"
#include <gem.h>
#include <proto/dos.h>
#include <exec816/runtime.h>
#include <exec816/aes.h>
#include <exec816/vdi-unit.h>
#include <stdlib.h>
#include <string.h>
#define GEM_PATH_MAX 256
/* Standard GEM keyboard qualifier, matching the pinned application kit. */
#define K_CTRL 0x0004
void GemArcIOBegin(void);
LONG GemArcCause(void);
int GemArcFailure(LONG);
int GemArcPoll(void);
int GemArcExists(const char *);
int GemArcCollect(const char *,const char *,char (*)[ARC_NAMELEN],unsigned int,const char *);
int GemArcJoin(char *,const char *,const char *);
#endif
