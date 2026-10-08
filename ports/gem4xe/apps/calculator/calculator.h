/* Exec window state for the donor calculator. GPL-2.0-or-later. */
#ifndef EXEC_CALCULATOR_H
#define EXEC_CALCULATOR_H
#include <gem.h>
#pragma pack(push,2)
struct Calculator {
    WORD window,opened,ready,focus,armed,saved,down,vdi,result;
    ULONG actions;
    WORD work[4],message[8];
};
#pragma pack(pop)
extern struct Calculator Calculator;
WORD calc_start(void);
WORD calc_ws(void);
WORD calc_panel(void);
#endif
