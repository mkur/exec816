/* SPDX-License-Identifier: MIT */
#ifndef BASIC_FILE_UI_H
#define BASIC_FILE_UI_H
#include "editor.h"
enum { BASIC_FILE_NEW=1,BASIC_FILE_OPEN,BASIC_FILE_SAVE,BASIC_FILE_SAVE_AS,BASIC_FILE_QUIT,BASIC_FILE_RECOVERY };
void BasicFilesRequest(WORD);
WORD BasicFilesWork(void);
WORD BasicFilesLoading(void);
/* 0 continue, 1 quit, 2 deliver retained AES policy before repair/retry. */
WORD BasicFilesStep(struct BasicEditor *);
void BasicFilesCancel(void);
void BasicFilesDispose(void);
const char *BasicFilesPath(void);
#endif
