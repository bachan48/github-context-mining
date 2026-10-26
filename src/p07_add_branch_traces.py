import os as _os
CLONES=_os.environ.get('CLONES','clones')            # blobless clones for claim history (RQ1, RQ2)
CLONES_FULL=_os.environ.get('CLONES_FULL','clones_full')  # clones for rules and commits (RQ3)
"""Second step: identity fix (S3) and same-PR propagation (S6), no network needed."""
import sys,json,glob,os,concurrent.futures as cf
sys.path.insert(0,'src'); from agent_traces import *
def job(f):
    J=json.load(open(f)); lab=J['labels']; d=CLONES_FULL+'/'+os.path.basename(f)[:-5]
    C=read_commits(d,'HEAD')
    for sha,c in C.items():
        if sha in lab and 'S3' not in lab[sha]['signals'] and (ident_hit(c['an'],c['ae']) or ident_hit(c['cn'],c['ce'])):
            lab[sha]['signals'].append('S3'); lab[sha]['agent']=True; lab[sha]['bot']=False
    branch_signals(d,lab,C)
    J['labels']=lab; json.dump(J,open(f,'w')); return J['repo'],sum(v['agent'] for v in lab.values())
with cf.ThreadPoolExecutor(6) as ex:
    for r in ex.map(job,sorted(glob.glob('data/intermediate/agent_traces/*.json'))): print(*r,flush=True)
