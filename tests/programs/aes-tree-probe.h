/* Traversal cases are supplied by the independent host object corpus. */
#define TREE_CASES 23
#define TREE_OBJECTS 40
volatile UWORD TreePhase,TreeGo,TreeActive,TreeBorrowCount,TreeFailAt;
WORD TreeRequest[8],TreeState[8],TreeDamage[4],TreeWork[4],TreePeerWork[4];
OBJECT TreeObjects[TREE_OBJECTS];
OBJECT TreePeerObjects[4]={
    {-1,1,3,G_IBOX,0,0,0,0,0,140,56},
    {3,2,2,G_BOX,0,0,0x1172,8,8,64,32},
    {1,-1,-1,G_BOX,0,0,0x1174,5,5,24,12},
    {0,-1,-1,G_BOX,LASTOB,0,0x1176,88,18,32,16}
};
volatile UWORD TreePeerReady,TreePeerStop,TreePeerDone,TreePeerPause,TreePeerHeld;
volatile UWORD TreeMainDraws,TreePeerDraws;
static struct Task *treeController;
static ULONG treeWake;

UWORD ObjectBorrowFailed(void)
{
    if (!TreeActive) return 0;
    ++TreeBorrowCount;
    return TreeFailAt && TreeBorrowCount==TreeFailAt;
}

static void tree_checkpoint(WORD phase)
{
    TreePhase=phase;
    while (TreeGo!=phase) ExecYield();
}

static void tree_peer(void)
{
    WORD window=-1,vdi=1,input[11],output[57],i,opened=0,attached=0;
    static OBJECT paper={-1,-1,-1,G_BOX,LASTOB,0,0x1177,0,0,0,0};
    CHECK(ExecAESAttach((struct MsgPort *)AESService));attached=1;
    if (appl_init()<0) { CHECK(0);goto finish; }
    for (i=0;i<10;++i) input[i]=1;input[10]=2;
    v_opnvwk(input,&vdi,output);
    if (!vdi) { CHECK(0);goto finish; }
    window=wind_create(NAME|CLOSER|MOVER,456,144,176,80);
    if (window<0) { CHECK(0);goto finish; }
    CHECK(wind_set_str(window,WF_NAME,"Tree peer"));
    if (!wind_open(window,456,144,176,80)) { CHECK(0);goto finish; }
    opened=1;
    CHECK(wind_get(window,WF_WORKXYWH,&TreePeerWork[0],&TreePeerWork[1],
        &TreePeerWork[2],&TreePeerWork[3]));
    paper.ob_x=TreePeerWork[0];paper.ob_y=TreePeerWork[1];
    paper.ob_width=TreePeerWork[2];paper.ob_height=TreePeerWork[3];
    TreePeerObjects[0].ob_x=TreePeerWork[0]+2;
    TreePeerObjects[0].ob_y=TreePeerWork[1]+2;
    TreePeerReady=1;Signal(treeController,treeWake);
    while (!TreePeerStop) {
        if (TreePeerPause) {
            TreePeerHeld=1;
            while (TreePeerPause && !TreePeerStop) ExecYield();
            TreePeerHeld=0;
            if (TreePeerStop) break;
        }
        CHECK(wind_update(BEG_UPDATE));
        CHECK(wind_get(window,WF_WORKXYWH,&TreePeerWork[0],&TreePeerWork[1],
            &TreePeerWork[2],&TreePeerWork[3]));
        CHECK(objc_draw(&paper,0,0,0,0,640,240));
        CHECK(objc_draw(TreePeerObjects,1,8,0,0,640,240));
        CHECK(wind_update(END_UPDATE));
        ++TreePeerDraws;
        ExecYield();
    }
finish:
    if (opened) CHECK(wind_close(window));
    if (window>0) CHECK(wind_delete(window));
    if (vdi>1) v_clsvwk(vdi);
    if (attached) CHECK(ExecAESDetach());
    Forbid();TreePeerReady=TreePeerDone=1;
    Signal(treeController,treeWake);RemTask(NULL);
}

static void tree_probe(WORD window)
{
    static OBJECT paper={-1,-1,-1,G_BOX,LASTOB,0,0x1175,0,0,0,0};
    struct ExecAESContext *context=ExecAESContext();
    struct AESWindowView *view;
    struct AESRect saved;
    WORD i,count;
    UWORD before;
    struct Task *peer;
    ULONG available=AvailMem(0);
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);treeWake=1UL<<bit;treeController=FindTask(NULL);
    CHECK(wind_set_str(window,WF_NAME,"Tree primary"));
    CHECK(wind_get(window,WF_WORKXYWH,&TreeWork[0],&TreeWork[1],&TreeWork[2],&TreeWork[3]));
    paper.ob_x=TreeWork[0];paper.ob_y=TreeWork[1];
    paper.ob_width=TreeWork[2];paper.ob_height=TreeWork[3];
    for (i=0;i<TREE_CASES;++i) {
        tree_checkpoint(i*2+1);
        CHECK(wind_update(BEG_UPDATE));
        CHECK(wind_get(window,WF_WORKXYWH,&TreeWork[0],&TreeWork[1],&TreeWork[2],&TreeWork[3]));
        CHECK(objc_draw(&paper,0,0,0,0,640,240));
        view=context->view;saved=view->visible[0];count=view->visibleCount;
        if (TreeRequest[6]==1) {
            view->visible[1]=saved;
            view->visible[0].right=173;view->visible[1].left=181;
            view->visibleCount=2;
        } else if (TreeRequest[6]==2) view->visibleCount=0;
        view->changed=0;
        TreeBorrowCount=0;TreeFailAt=TreeRequest[6]==3 ? 3:0;
        TreeActive=1;
        TreeState[0]=objc_draw(TreeObjects,TreeRequest[0],TreeRequest[1],
            TreeRequest[2],TreeRequest[3],TreeRequest[4],TreeRequest[5]);
        TreeActive=0;TreeFailAt=0;
        TreeState[1]=context->diagnostic;TreeState[2]=context->busy;
        TreeState[3]=context->request.paintFailed;TreeState[4]=view->changed;
        TreeState[5]=TreeBorrowCount;
        TreeDamage[0]=view->change.left;TreeDamage[1]=view->change.top;
        TreeDamage[2]=view->change.right;TreeDamage[3]=view->change.bottom;
        CHECK(TreeState[0]==(TreeRequest[6]!=3));
        CHECK(TreeState[1]==(TreeRequest[6]==3 ? AES_DISPLAY_ERROR:AES_OK));
        CHECK(!TreeState[2] && TreeState[3]==(TreeRequest[6]==3));
        view->visible[0]=saved;view->visibleCount=count;
        CHECK(wind_update(END_UPDATE));
        tree_checkpoint(i*2+2);
    }
    peer=CreateTask("Object tree peer",0,(APTR)AESClientOne,1536UL);
    CHECK(peer!=NULL);
    while (peer && !TreePeerReady) Wait(treeWake);
    before=TreePeerDraws;
    for (i=0;i<32;++i) {
        CHECK(wind_update(BEG_UPDATE));
        CHECK(wind_get(window,WF_WORKXYWH,&TreeWork[0],&TreeWork[1],&TreeWork[2],&TreeWork[3]));
        CHECK(objc_draw(&paper,0,0,0,0,640,240));
        CHECK(objc_draw(TreeObjects,0,8,0,0,640,240));
        CHECK(wind_update(END_UPDATE));
        ++TreeMainDraws;
        ExecYield();
    }
    TreePeerPause=1;
    while (peer && !TreePeerHeld && !TreePeerDone) ExecYield();
    CHECK(TreePeerDraws>before && TreeMainDraws==32);
    tree_checkpoint(1000);
    TreePeerStop=1;TreePeerPause=0;
    while (peer && !TreePeerDone) Wait(treeWake);
    FreeSignal(bit);
    CHECK(AvailMem(0)==available);
}
