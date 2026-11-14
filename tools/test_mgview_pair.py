#!/usr/bin/env python3
"""One same-document line down/up check on original MagiC and native MGVIEW."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from native_program import ROOT,require,sha256
from test_magic_scroll import capture
from test_mgview import run as exec_viewer


def run(output,reference,exec_build):
    output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    profile=json.loads((reference/'build.json').read_text())
    require(sha256(reference/'documents.st')==profile['documents']['sha256'],'Changed MagiC reference disk')
    for name,digest in profile['binaries'].items():
        require(sha256(reference/name)==digest,'Changed MagiC reference binary: '+name)
    document=(reference/'drive-c/STORY.TXT').read_bytes()
    require(hashlib.sha256(document).hexdigest()==profile['document_sha256'],'Changed reference text')
    original=subprocess.run(['mtype','-i',str(reference/'documents.st'),'::STORY.TXT'],check=True,capture_output=True).stdout
    require(document==original,'Reference host and floppy documents differ')
    folder=output/'reference/mgview';folder.mkdir(parents=True,exist_ok=True)
    shutil.copytree(reference/'drive-c',folder/'drive-c',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.LOG'))
    shutil.copyfile(reference/'documents.st',folder/'documents.st')
    for flag,value in (('--harddrive',folder/'drive-c'),('--disk-a',folder/'documents.st')):
        profile['command'][profile['command'].index(flag)+1]=str(value)
    (folder/'build.json').write_text(json.dumps(profile,indent=2)+'\n')
    magic=capture(output/'reference',{'mgview':profile})
    native=exec_viewer(exec_build,reuse=True,scroll=True,document=folder/'drive-c/STORY.TXT',vertical_only=True)
    record=dict(status='pass',tier='development',qualification=False,document_bytes=len(document),
        document_sha256=hashlib.sha256(document).hexdigest(),magic=magic,
        exec_app_sha256=native['app_sha256']['mgview'],exec_pixels=native['pixels'],
        exec_result=str(exec_build/'results-reference.json'),
        scope='Same byte-identical document, line down/up and within-machine pixel oracles.',
        timing='Not measured: MagiC 8x16/8 MHz mono and Exec 8x8/65816/VBXE are not normalized; only Exec has a background Counter.')
    (output/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Original MGVIEW on MagiC and Exec: paired functional check passed')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/mgview-dev/paired')
    parser.add_argument('--reference',type=Path,default=ROOT/'build/magic-scroll-comparison/mgview')
    parser.add_argument('--exec-build',type=Path,default=ROOT/'build/mgview-dev/smoke')
    args=parser.parse_args();run(args.output,args.reference,args.exec_build)
