/* SPDX-License-Identifier: MIT */
#ifndef QED_SAVING_H
#define QED_SAVING_H
#include "global.h"
void QedSavingStart(TEXTP text,bool save_as);
bool QedSavingBusy(void);
bool QedSavingAttention(void);
bool QedSavingMessage(short *message);
void QedSavingKey(short state,short key);
void QedSavingObserved(short events);
void QedSavingStep(void);
short QedSavingTakeResult(void);
bool QedSavingExitPending(void);
void QedSavingForget(void);
void QedSavingShutdown(void);
#endif
