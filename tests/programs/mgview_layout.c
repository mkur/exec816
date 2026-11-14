#include "mgview-native.h"
#include "windows.h"
__attribute__((section("exec_layout"))) const UWORD MGViewLayout[]={
    sizeof(WORD),sizeof(char *),sizeof(WINDOW),offsetof(WINDOW,out),
    offsetof(WINDOW,in),offsetof(WINDOW,vscroll),offsetof(WINDOW,hscroll),
    offsetof(WINDOW,user_file),offsetof(WINDOW,user_lines),offsetof(WINDOW,user_tabsize)
};
