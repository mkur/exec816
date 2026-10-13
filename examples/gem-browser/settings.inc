/* Small, explicit preferences file. Parse once at startup, never on redraw. */
#define SETTINGS_BYTES 1024
static WORD setting_number(char **text,WORD *value)
{
    char *p=*text;
    UWORD n=0,d;
    if (*p<'0' || *p>'9') return 0;
    while (*p>='0' && *p<='9') {
        d=*p++-'0';if (n>3276 || (n==3276 && d>7)) return 0;
        n=n*10+d;
    }
    if (*p && *p!=' ') return 0;
    while (*p==' ') ++p;
    *text=p;*value=n;return 1;
}
static void settings_line(struct Desktop *d,char *line)
{
    WORD i,values[6];
    char *p=line;
    if (!strncmp(p,"FOLDER ",7)) {
        struct DesktopFolder *f;
        if (d->savedCount==DESKTOP_FOLDERS) return;
        p+=7;for (i=0;i<6;++i) if (!setting_number(&p,&values[i])) return;
        if (values[0]+(LONG)values[2]>640 || values[1]<16 || values[1]+(LONG)values[3]>240 ||
            values[2]<240 || values[3]<144 || values[4]>1 || values[5]>1 || !*p || strlen(p)>127) return;
        f=&d->saved[d->savedCount++];
        for (i=0;i<4;++i) f->bounds[i]=values[i];
        f->icons=values[4];f->sort=values[5];strcpy(f->path,p);
    } else if (!strncmp(p,"MOUSE ",6)) {
        p+=6;if (setting_number(&p,&i) && !*p && i<=AES_MOUSE_MILD) d->mouse=i;
    } else if (!strncmp(p,"VIEW ",5)) {
        p+=5;if (setting_number(&p,&values[0]) && setting_number(&p,&values[1]) &&
            !*p && values[0]<=1 && values[1]<=1) {
            d->defaultIcons=values[0];d->defaultSort=values[1];
        }
    } else if (!strncmp(p,"ASSOC ",6)) {
        p+=6;
        if (strlen(p)<5 || p[3]!=' ' || strlen(p+4)>63) return;
        for (i=0;i<2;++i) if (!d->associations[i].extension[0] ||
            !strncmp(p,d->associations[i].extension,3)) {
            memcpy(d->associations[i].extension,p,3);d->associations[i].extension[3]=0;
            strcpy(d->associations[i].program,p+4);break;
        }
    }
}
static void settings_load(struct Desktop *d)
{
    BPTR file;
    char *buffer,*line,*end;
    LONG count;
    d->defaultIcons=d->defaultSort=1;d->mouse=ExecAESMouseProfile(AES_MOUSE_QUERY);
    strcpy(d->associations[0].extension,"TXT");strcpy(d->associations[0].program,"C:TEXT.APP");
    file=Open("WORK:DESKTOP.CFG",MODE_OLDFILE);if (!file) return;
    buffer=AllocMem(SETTINGS_BYTES,MEMF_PUBLIC);
    if (!buffer) { Close(file);return; }
    count=Read(file,buffer,SETTINGS_BYTES-1);
    if (count<0) d->error=IoErr();
    if (!Close(file) && !d->error) d->error=IoErr();
    if (count>0 && count<SETTINGS_BYTES-1 && !d->error) {
        buffer[count]=0;line=buffer;
        /* A versioned header prevents a partial/foreign file becoming config. */
        end=strchr(line,'\n');
        if (end) {
            *end=0;if (end>line && end[-1]=='\r') end[-1]=0;
            if (!strcmp(line,"EXEC816_DESKTOP 1")) {
                d->settingsLoaded=1;line=end+1;
                while ((end=strchr(line,'\n'))!=NULL) {
                    *end=0;if (end>line && end[-1]=='\r') end[-1]=0;
                    settings_line(d,line);line=end+1;
                }
            }
        }
    }
    FreeMem(buffer,SETTINGS_BYTES);
}
static WORD settings_save(struct Desktop *d)
{
    BPTR file;
    char *buffer,*p;
    WORD i,j,bounds[4];
    LONG count;
    buffer=AllocMem(SETTINGS_BYTES,MEMF_PUBLIC);
    if (!buffer) { strcpy(d->status,"No memory for settings");return 0; }
    strcpy(buffer,"EXEC816_DESKTOP 1\nMOUSE ");p=buffer+strlen(buffer);
    p=decimal(p,ExecAESMouseProfile(AES_MOUSE_QUERY));strcpy(p,"\nVIEW ");p+=6;
    p=decimal(p,d->defaultIcons);*p++=' ';p=decimal(p,d->defaultSort);*p++='\n';
    for (i=0;i<DESKTOP_FOLDERS;++i) if (d->folders[i]) {
        struct Browser *b=d->folders[i];
        if (!wind_get(b->window,WF_CURRXYWH,&bounds[0],&bounds[1],&bounds[2],&bounds[3])) continue;
        strcpy(p,"FOLDER ");p+=7;
        for (j=0;j<4;++j) { p=decimal(p,bounds[j]);*p++=' '; }
        p=decimal(p,b->iconView);*p++=' ';p=decimal(p,b->sortNames);*p++=' ';
        strcpy(p,b->path);p+=strlen(p);*p++='\n';
    }
    for (i=0;i<2;++i) if (d->associations[i].extension[0]) {
        strcpy(p,"ASSOC ");p+=6;
        strcpy(p,d->associations[i].extension);p+=3;*p++=' ';
        strcpy(p,d->associations[i].program);p+=strlen(p);*p++='\n';
    }
    /* Fixed three paths and two associations fit below 800 bytes. */
    count=p-buffer;d->error=0;
    file=Open("WORK:DESKTOP.CFG",MODE_NEWFILE);
    if (!file) d->error=IoErr();
    else {
        if (Write(file,buffer,count)!=count) { d->error=IoErr();if (!d->error) d->error=ERROR_DISK_FULL; }
        if (!Close(file) && !d->error) d->error=IoErr();
    }
    FreeMem(buffer,SETTINGS_BYTES);
    strcpy(d->status,d->error ? "Could not save WORK:DESKTOP.CFG":"Saved WORK:DESKTOP.CFG");
    return d->error==0;
}
