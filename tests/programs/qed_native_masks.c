#include <proto/exec.h>
#include <exec816/runtime.h>
static volatile unsigned maskCalls;
static volatile unsigned maskSeed=1;
extern int filematch(char *,char *,short);
int main(void)
{
    ExecYield();
    maskCalls+=maskSeed;
    if(maskCalls!=1)return 200;
    if(!filematch("readme.txt","*.TXT",0))return 201;
    if(!filematch("readme.txt","r?ad*.t?t",0))return 202;
    if(filematch("readme.txt","*.c",0))return 203;
    if(!filematch("abbbc","a*b*c",0))return 204;
    if(filematch("abbbc","a*b*d",0))return 205;
    if(!filematch("","**",0) || filematch("","?",0))return 206;
    if(!filematch("plain","plain",0) || filematch("plains","plain",0))return 207;
    if(!filematch("aaaaaaaab","*a*a*a*a*b",0))return 208;
    if(filematch("aaaaaaaac","*a*a*a*a*b",0))return 209;
    return -321;
}
