/* SPDX-License-Identifier: MIT. ARC's DOS date words over native metadata. */
#include "platform.h"
static unsigned int leap(unsigned int year)
{ return !(year%4) && (year%100 || !(year%400)); }
static unsigned int month_days(unsigned int year,unsigned int month)
{
    static const unsigned char days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    return days[month-1]+(month==2 && leap(year));
}
void pf_stamp(const char *name,uint16_t *date,uint16_t *time)
{
    struct FileInfoBlock info;
    BPTR lock;
    LONG remaining;
    unsigned int year=1978,month=1;
    *date=*time=0;
    lock=Lock(name,SHARED_LOCK);
    if (!lock) return;
    if (!ExamineExact(lock,&info)) { UnLock(lock);return; }
    UnLock(lock);
    remaining=info.fib_Date.ds_Days;
    if (remaining<0 || info.fib_Date.ds_Minute<0 || info.fib_Date.ds_Minute>=1440 ||
            info.fib_Date.ds_Tick<0 || info.fib_Date.ds_Tick>=3000) return;
    while (year<=2049 && remaining>=(LONG)(365+leap(year))) remaining-=365+leap(year++);
    if (year<1980 || year>2049) return;
    while (remaining>=month_days(year,month)) remaining-=month_days(year,month++);
    *date=((year-1980)<<9)|(month<<5)|(remaining+1);
    *time=((info.fib_Date.ds_Minute/60)<<11)|((info.fib_Date.ds_Minute%60)<<5)|
        (info.fib_Date.ds_Tick/100);
}
int pf_setstamp(const char *name,uint16_t date,uint16_t time)
{
    struct DateStamp stamp={0};
    unsigned int year=1980+(date>>9),month=(date>>5)&15,day=date&31,index;
    if (!date || year>2049 || !month || month>12 || !day || day>month_days(year,month) ||
            (time>>11)>23 || ((time>>5)&63)>59 || (time&31)>29) return 0;
    for (index=1978;index<year;++index) stamp.ds_Days+=365+leap(index);
    for (index=1;index<month;++index) stamp.ds_Days+=month_days(year,index);
    stamp.ds_Days+=day-1;
    stamp.ds_Minute=(time>>11)*60+((time>>5)&63);stamp.ds_Tick=(time&31)*100;
    if (SetFileDate(name,&stamp)) return 0;
    if (IoErr()==ERROR_ACTION_NOT_KNOWN) { SetIoErr(0);return 0; }
    return GemArcFailure(IoErr());
}
