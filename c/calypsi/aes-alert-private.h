#ifndef EXEC816_AES_ALERT_PRIVATE_H
#define EXEC816_AES_ALERT_PRIVATE_H
#include "aes-form-private.h"
struct ExecAESAlert {
    OBJECT tree[10];
    char lines[5][41], labels[3][21];
    WORD icon, lineCount, buttonCount;
};
UWORD ExecAESAlertParse(struct ExecAESAlert *,WORD,const char *);
WORD ExecAESAlertPaint(struct ExecAESContext *);
#endif
