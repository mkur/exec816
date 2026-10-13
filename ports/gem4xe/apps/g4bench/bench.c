/* Exec window/timing/report adapter for G4BENCH; GPL-2.0-or-later. */
#include <gem.h>
#include <exec816/aes.h>
#include <proto/dos.h>
#include "clock.h"
#include "workload.h"

#define ROWS 5
#define SAMPLES 3
#define PENDING 0
#define COMPLETE 1
#define COARSE 2
#define CANCELLED 3
#define INVALID 4
#define FAILED 5

/* Ordinary application state, also read by the development observer. */
WORD g4b_ready,g4b_done,g4b_window,g4b_vdi,g4b_work[4],g4b_canvas[4];
WORD g4b_phase,g4b_row,g4b_sample,g4b_progress,g4b_runs,g4b_save;
WORD g4b_status[ROWS],g4b_counts[ROWS],g4b_operations[ROWS*SAMPLES];
WORD g4b_clips[ROWS*4];
ULONG g4b_ticks[ROWS*SAMPLES],g4b_rate;
struct BenchTick g4b_times[ROWS*SAMPLES*2];
static struct BenchClock clock;
static struct BenchTick start,end;
static ULONG elapsed_ticks;
static WORD work_in[11]={1,1,1,1,1,1,1,1,1,1,2},work_out[57],message[8];
static WORD quit,abort_run,invalid,paint_needed;
static char line[128];
static const char *names[ROWS]={"solid bars","text even X","text odd X","text clipped","five-object dialog"};
static const char *states[6]={"pending","complete","low resolution","cancelled","invalidated","error"};
static const WORD base_count[ROWS]={50,50,50,50,20};

static WORD report(void);

/* Only formatting uses decimal division. Never called inside a sample. */
static WORD string(WORD at,const char *s)
{
    while (*s) line[at++]=*s++;
    line[at]=0;return at;
}
static WORD number(WORD at,ULONG n)
{
    char digits[10];WORD count=0;
    do { digits[count++]='0'+n%10;n/=10; } while (n);
    while (count) line[at++]=digits[--count];
    line[at]=0;return at;
}
static ULONG median(WORD row)
{
    ULONG a=g4b_ticks[row*3],b=g4b_ticks[row*3+1],c=g4b_ticks[row*3+2],swap;
    if (a>b) { swap=a;a=b;b=swap; }
    if (b>c) { b=c;if (a>b) b=a; }
    return b;
}
static void result_line(WORD row)
{
    WORD at=string(0,names[row]);ULONG tenths;
    while (at<20) line[at++]=' ';
    if (g4b_status[row]==COMPLETE || g4b_status[row]==COARSE) {
        /* Multiply the remainder separately to keep bounded batches in ULONG. */
        ULONG ticks=median(row),divisor=g4b_rate*(UWORD)g4b_counts[row];
        tenths=(ticks/divisor)*10000UL+((ticks%divisor)*10000UL)/divisor;
        at=number(at,tenths/10);at=string(at,".");line[at++]='0'+tenths%10;
        at=string(at," ms/op");
        if (g4b_status[row]==COARSE) string(at," (coarse)");
    } else string(at,states[g4b_status[row]]);
}

static WORD get_work(void)
{
    return wind_get(g4b_window,WF_WORKXYWH,&g4b_work[0],&g4b_work[1],&g4b_work[2],&g4b_work[3]);
}
static WORD full_canvas(void)
{
    WORD x,y,w,h,top,i;
    if (!get_work()) return 0;
    for (i=0;i<4;++i) if (g4b_work[i]!=g4b_canvas[i]) return 0;
    if (!wind_get(0,WF_TOP,&top,&y,&w,&h) || top!=g4b_window) return 0;
    if (!wind_get(g4b_window,WF_FIRSTXYWH,&x,&y,&w,&h) ||
        x!=g4b_canvas[0] || y!=g4b_canvas[1] || w!=480 || h!=160) return 0;
    return wind_get(g4b_window,WF_NEXTXYWH,&x,&y,&w,&h) && !w && !h;
}

/* Zero-duration MU_TIMER is a caller-local poll. No wait holds UPDATE. */
static WORD events(WORD active,WORD wait)
{
    WORD ev,mx,my,mb,ks,kr,br;
    ev=evnt_multi_moblk(MU_MESAG|MU_KEYBD|(wait ? 0:MU_TIMER),0,0,0,
                       NULL,NULL,message,0,0,&mx,&my,&mb,&ks,&kr,&br);
    if (!ev) return 0;
    if (ev&MU_KEYBD) {
        if ((kr&255)==27) { if (active) abort_run=1;else quit=1; }
        else if ((kr&255)==13 && !active) return 2;
    }
    if ((ev&MU_MESAG) && message[3]==g4b_window) {
        switch (message[0]) {
        case WM_CLOSED:quit=abort_run=1;break;
        case WM_TOPPED:
            if (active) invalid=1;
            if (!wind_set(g4b_window,WF_TOP,0,0,0,0)) return 0;
            break;
        case WM_MOVED:
            if (active) invalid=1;
            if (!wind_set(g4b_window,WF_CURRXYWH,message[4],message[5],message[6],message[7])) return 0;
            paint_needed=1;break;
        case WM_REDRAW:
            if (active) invalid=1;
            paint_needed=1;break;
        }
    }
    return 1;
}

/* Preparation is outside both timestamp reads. */
static WORD prepare(WORD row)
{
    WORD p[4],okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=full_canvas();
    if (okay) {
        p[0]=g4b_canvas[0];p[1]=g4b_canvas[1];p[2]=g4b_canvas[0]+479;p[3]=g4b_canvas[1]+159;
        vs_clip(g4b_vdi,1,p);vsf_color(g4b_vdi,0);v_bar(g4b_vdi,p);
        okay=ExecAESDiagnostic()==0;
        BenchClip(row,p);vs_clip(g4b_vdi,1,p);
        vswr_mode(g4b_vdi,MD_REPLACE);vsf_interior(g4b_vdi,FIS_SOLID);
    } else invalid=1;
    if (!wind_update(END_UPDATE)) okay=0;
    return okay;
}

/* Synchronous public calls have finished their blits before the end read.
 * Group admission, visible-region checks and event polling are measured. */
static WORD batch(WORD row,WORD count,WORD timed)
{
    WORD okay=1,i=0,n,group=row==4 ? 1:4;
    if (!prepare(row)) return 0;
    g4b_progress=0;
    if (timed && !BenchClockRead(&clock,&start)) return 0;
    while (g4b_progress<count && !quit && !abort_run && !invalid) {
        if (!wind_update(BEG_UPDATE)) return 0;
        if (!full_canvas()) { invalid=1;okay=0; }
        for (n=0;okay && n<group && g4b_progress<count;++n) {
            BenchDraw(row,i);
            okay=ExecAESDiagnostic()==0;
            if (okay) ++g4b_progress;
            if (++i==base_count[row]) i=0;
        }
        if (!wind_update(END_UPDATE)) okay=0;
        if (!okay || !events(1,0)) return 0;
    }
    if (quit || abort_run || invalid) return 0;
    if (timed && (!BenchClockRead(&clock,&end) || !BenchElapsed(&start,&end,&elapsed_ticks))) return 0;
    return 1;
}

static WORD write_line(BPTR file)
{
    WORD length=0;
    while (line[length]) ++length;
    line[length++]='\n';
    return Write(file,line,length)==length;
}
static WORD save(void)
{
    BPTR file=Open("WORK:G4BENCH.TXT",MODE_NEWFILE);
    WORD okay=1,row,s,at,index,i;
    if (!file) return 0;
    string(0,"G4BENCH Exec816 subset v1; application throughput, not input latency");okay=write_line(file);
    string(0,"Donor fbfea9b0b1233a5d659d5ec583c63f863cceadfa; 8x8, replace text");if (okay) okay=write_line(file);
    at=string(0,"VBI ticks/second: ");at=number(at,g4b_rate);
    at=string(at,"; text bytes: ");number(at,BenchTextLength());if (okay) okay=write_line(file);
    at=string(0,"Canvas x y w h:");
    for (i=0;i<4;++i) { at=string(at," ");at=number(at,(UWORD)g4b_canvas[i]); }
    if (okay) okay=write_line(file);
    string(0,"Includes UPDATE, visible checks, scheduling, polling and completed drawing.");if (okay) okay=write_line(file);
    string(0,"Excludes clearing, warmup, formatting and disk writes. Cursor stays visible.");if (okay) okay=write_line(file);
    for (row=0;row<ROWS && okay;++row) {
        result_line(row);okay=write_line(file);
        at=string(0,"  status: ");at=string(at,states[g4b_status[row]]);at=string(at,"; clip:");
        for (i=0;i<4;++i) { at=string(at," ");at=number(at,(UWORD)g4b_clips[row*4+i]); }
        if (okay) okay=write_line(file);
        for (s=0;s<SAMPLES && okay;++s) {
            index=row*3+s;
            at=string(0,"  sample ");at=number(at,s+1);at=string(at,": ops=");at=number(at,g4b_operations[index]);
            at=string(at," ticks=");at=number(at,g4b_ticks[index]);at=string(at," start=");
            at=number(at,g4b_times[index*2].high);at=string(at,":");at=number(at,g4b_times[index*2].low);
            at=string(at," end=");at=number(at,g4b_times[index*2+1].high);at=string(at,":");
            number(at,g4b_times[index*2+1].low);okay=write_line(file);
        }
    }
    string(0,"Adapted: vr_recfl -> v_bar; transparent -> replace; no OUTLINED dialog.");if (okay) okay=write_line(file);
    string(0,"SKIP lines, patterns, curves/polygons/rounded boxes: public VDI unavailable.");if (okay) okay=write_line(file);
    string(0,"SKIP effects/heights: fixed font. SKIP copies/icons: no MFDB calls.");if (okay) okay=write_line(file);
    string(0,"SKIP window cycles: one window/app. SKIP Mandelbrot: needs polylines.");if (okay) okay=write_line(file);
    string(0,"Odd/clipped rows are Exec variants. No direct donor speed ratio or score.");if (okay) okay=write_line(file);
    if (!Close(file)) okay=0;
    return okay;
}

static WORD report(void)
{
    WORD x,y,w,h,p[4],okay,row,at;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=get_work();
    if (okay) okay=wind_get(g4b_window,WF_FIRSTXYWH,&x,&y,&w,&h);
    while (okay && w && h) {
        p[0]=x;p[1]=y;p[2]=x+w-1;p[3]=y+h-1;
        vs_clip(g4b_vdi,1,p);vsf_color(g4b_vdi,0);v_bar(g4b_vdi,p);vst_color(g4b_vdi,1);
        v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+14,"G4BENCH - Exec816 subset v1");
        for (row=0;row<ROWS;++row) {
            result_line(row);v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+34+row*12,line);
        }
        at=string(0,"Clock: ");at=number(at,g4b_rate);string(at," Hz; median of 3 batch averages.");
        v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+102,line);
        v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+114,
            "15 donor tests skipped: unsupported APIs (see report).");
        v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+126,
            g4b_save==1 ? "Saved WORK:G4BENCH.TXT":g4b_save==2 ? "Could not save WORK:G4BENCH.TXT":"Adapted tests; no direct GEM4XE score.");
        v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+146,
            "Return: run. Escape: stop/close. Keep window uncovered.");
        okay=ExecAESDiagnostic()==0 && wind_get(g4b_window,WF_NEXTXYWH,&x,&y,&w,&h);
    }
    if (!wind_update(END_UPDATE)) okay=0;
    paint_needed=0;return okay;
}

static void measure(void)
{
    WORD row,s,i,count,index,okay=1,coarse;
    ULONG elapsed;
    g4b_done=0;g4b_save=0;abort_run=invalid=0;++g4b_runs;
    for (i=0;i<ROWS;++i) { g4b_status[i]=PENDING;g4b_counts[i]=0; }
    for (i=0;i<ROWS*SAMPLES;++i) {
        g4b_ticks[i]=0;g4b_operations[i]=0;
        g4b_times[i*2].high=g4b_times[i*2].low=g4b_times[i*2+1].high=g4b_times[i*2+1].low=0;
    }
    if (!get_work()) okay=0;
    for (i=0;i<4;++i) g4b_canvas[i]=g4b_work[i];
    BenchSetup(g4b_vdi,g4b_canvas,work_out[13]);
    for (i=0;i<ROWS;++i) BenchClip(i,&g4b_clips[i*4]);
    for (row=0;row<ROWS && okay;++row) {
        g4b_row=row;g4b_phase=1;g4b_sample=-1;count=base_count[row];
        if (!batch(row,count,0)) { okay=0;break; }
        g4b_phase=2;
        for (;;) {
            if (!batch(row,count,1)) { okay=0;break; }
            elapsed=elapsed_ticks;
            if (elapsed>=2*g4b_rate || count>4096/2) break;
            count*=2;
        }
        if (!okay) break;
        g4b_counts[row]=count;coarse=0;g4b_phase=3;
        for (s=0;s<SAMPLES;++s) {
            g4b_sample=s;index=row*3+s;
            if (!batch(row,count,1)) { okay=0;break; }
            elapsed=elapsed_ticks;
            g4b_times[index*2]=start;g4b_times[index*2+1]=end;
            g4b_ticks[index]=elapsed;g4b_operations[index]=count;
            if (elapsed<2*g4b_rate) coarse=1;
        }
        if (!okay) break;
        g4b_status[row]=coarse ? COARSE:COMPLETE;
    }
    if (!okay && row<ROWS) g4b_status[row]=abort_run || quit ? CANCELLED:invalid ? INVALID:FAILED;
    g4b_phase=4;
    if (!quit) { g4b_save=save() ? 1:2;paint_needed=1; }
    g4b_phase=0;g4b_done=1;
}

int main(void)
{
    WORD cw,ch,bw,bh,x,y,w,h,opened=0,result=1,ev;
    g4b_window=-1;
    if (appl_init()<0) return 1;
    g4b_vdi=graf_handle(&cw,&ch,&bw,&bh);v_opnvwk(work_in,&g4b_vdi,work_out);
    if (!g4b_vdi) goto finish;
    if (!wind_calc(WC_BORDER,NAME|CLOSER|MOVER,80,56,480,160,&x,&y,&w,&h)) goto finish;
    g4b_window=wind_create(NAME|CLOSER|MOVER,x,y,w,h);
    if (g4b_window<0 || !wind_set_str(g4b_window,WF_NAME,"G4BENCH")) goto finish;
    if (!wind_open(g4b_window,x,y,w,h)) goto finish;
    opened=1;
    if (!BenchClockOpen(&clock) || !BenchClockRead(&clock,&start)) goto finish;
    g4b_rate=start.rate;g4b_ready=1;paint_needed=1;result=0;
    while (!quit) {
        if (paint_needed && !report()) { result=2;break; }
        ev=events(0,1);
        if (!ev) { result=2;break; }
        if (ev==2 && !quit) {
            /* Consume initial redraws and warm the zero-time event poll before
             * timing. A bounded drain cannot starve a continuously active peer. */
            WORD i;
            for (i=0;i<8 && !quit;++i) if (!events(0,0)) { result=2;break; }
            if (!quit && !result) measure();
        }
    }
finish:
    g4b_ready=0;BenchClockClose(&clock);
    if (opened && wind_close(g4b_window)) opened=0;
    if (g4b_window>0 && !opened) wind_delete(g4b_window);
    if (g4b_vdi) v_clsvwk(g4b_vdi);
    if (!appl_exit()) result=3;
    if (result) {
        static const char failed[]="G4BENCH: could not open or complete the benchmark.\n";
        Write(Output(),failed,sizeof(failed)-1);
    }
    return result;
}
