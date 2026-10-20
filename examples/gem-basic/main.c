/* SPDX-License-Identifier: MIT */
#include "editor.h"
struct BasicEditor Basic;
int main(void)
{
    WORD result;
    if (BasicDocumentInit(&Basic.document)) return 20;
    result=BasicEditorRun(&Basic);
    BasicDocumentDispose(&Basic.document);
    return result;
}
