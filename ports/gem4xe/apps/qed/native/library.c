/* SPDX-License-Identifier: MIT */
#include "qed-runtime.h"
#include <proto/dos.h>
#include <string.h>
void QedRetirementFault(const char *message)
{
    Write(Output(),message,strlen(message));
    for (;;) Wait(0);
}
