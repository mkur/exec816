/* SPDX-License-Identifier: MIT */
#include "widget.h"

struct Widget GEMWidget;

int main(int argc,char **argv)
{
    (void)argc;
    (void)argv;
    return WidgetRun(&GEMWidget);
}
