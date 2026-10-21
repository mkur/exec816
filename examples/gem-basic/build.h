/* SPDX-License-Identifier: MIT */
#ifndef BASIC_BUILD_H
#define BASIC_BUILD_H
#include "editor.h"
enum { BASIC_BUILD_CHECK=1,BASIC_BUILD_RUN,BASIC_BUILD_STOP,BASIC_BUILD_PUBLISH,
    BASIC_BUILD_INTEGER,BASIC_BUILD_OUTPUT };
void BasicBuildRequest(struct BasicEditor *,WORD);
WORD BasicBuildBusy(void);
WORD BasicBuildWork(void);
ULONG BasicBuildMask(void);
void BasicBuildStep(struct BasicEditor *);
WORD BasicBuildMessage(struct BasicEditor *,WORD *);
void BasicBuildStop(void);
void BasicBuildDispose(void);
WORD BasicBuildRecovery(struct BasicEditor *);
#endif
