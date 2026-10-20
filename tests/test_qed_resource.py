"""Audit generated resource identities and capacities independently of loading."""
import json,re,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_qed_resource import menu,link
from prepare_qed import PORT
from native_program import ROOT

class QedMenuTests(unittest.TestCase):
    def test_compact_menu_reaches_each_initial_action_once(self):
        groups=json.loads((PORT/'resource-selection.json').read_text())['menu']
        ids={};tree=menu(groups,ids)
        self.assertLessEqual(len(tree),33)
        visited=set()
        def walk(parent):
            self.assertNotIn(parent,visited);visited.add(parent)
            first,last=tree[parent][1:3]
            if first<0:return
            child=first
            while child!=parent:
                walk(child);nxt=tree[child][0]
                if child==last:self.assertEqual(nxt,parent)
                child=nxt
        walk(0)
        self.assertEqual(visited,set(range(len(tree))))
        self.assertEqual(sum(bool(o[4]&32) for o in tree),1)
        for name,label,items in groups:
            self.assertLessEqual(tree[ids[name]][7]+tree[ids[name]][9],432)
            self.assertLessEqual(tree[ids[name]][10],json.loads((ROOT/'abi/desktop.json').read_text())['constants']['MENU_BAR_HEIGHT'])
            for item,text in items:
                self.assertEqual(tree[ids[item]][3],28)
                caption=tree[ids[item]][6]
                self.assertEqual(' '.join(text.split()),' '.join(caption.split()))
                if '^' in text:self.assertEqual(caption[-2:],text[-2:])
        self.assertEqual(len({ids[item] for _,_,items in groups for item,_ in items}),16)

if __name__=='__main__':unittest.main()
