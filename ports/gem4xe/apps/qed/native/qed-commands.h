/* SPDX-License-Identifier: MIT */
#ifndef QED_COMMANDS_H
#define QED_COMMANDS_H
#include "global.h"
#define QED_DIALOG_FAILED (-1)
#define QED_DIALOG_CANCELLED 0
#define QED_DIALOG_ACCEPTED 1
#define QED_DIALOG_INTERRUPTED 2
short QedNativeForm(OBJECT *tree,short start);
short QedChooseFile(const char *initial,char *destination,const char *title);
void QedFindStart(TEXTP text,bool prompt);
void QedAboutStart(void);
void QedOpenStart(TEXTP text,const char *path);
void QedNewStart(TEXTP text);
void QedSaveCommand(TEXTP text,bool save_as);
void QedExitStart(void);
void QedArgumentsError(void);
void QedCommandsCancel(void);
void QedCommandsMessage(short *message);
void QedCommandsStep(void);
bool QedCommandsSearching(void);
bool QedCommandsWorking(void);
#endif
