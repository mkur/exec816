#include <hardware/console-bitmap.h>
__attribute__((section("exec_layout"))) const unsigned short __exec_layout[]={
sizeof(struct ConsoleBitmapPacket),
offsetof(struct ConsoleBitmapPacket,operation),
offsetof(struct ConsoleBitmapPacket,status),
offsetof(struct ConsoleBitmapPacket,text),
offsetof(struct ConsoleBitmapPacket,x),
offsetof(struct ConsoleBitmapPacket,y),
offsetof(struct ConsoleBitmapPacket,width),
offsetof(struct ConsoleBitmapPacket,height),
offsetof(struct ConsoleBitmapPacket,foreground),
offsetof(struct ConsoleBitmapPacket,background),
offsetof(struct ConsoleBitmapPacket,copy),
offsetof(struct ConsoleBitmapPacket,token),
};
