import os as _os
CLONES=_os.environ.get('CLONES','clones')            # blobless clones for claim history (RQ1, RQ2)
CLONES_FULL=_os.environ.get('CLONES_FULL','clones_full')  # clones for rules and commits (RQ3)
"""Who first committed each context file: agent trace (S1-S3) on the file's first commit."""
import sys,subprocess,pandas as pd,concurrent.futures as cf
sys.path.insert(0,'src'); from agent_traces import *
c=pd.read_csv('data/intermediate/context_file_candidates.csv')
ai=set(pd.read_csv('data/raw/commits.csv',usecols=['commit_sha']).commit_sha)
def job(r):
    d=CLONES+'/'+r.repo_name.replace('/','__')
    o=G(d,'show','-s','--format=%an%x1f%ae%x1f%cn%x1f%ce%x1f%B',r.first_commit_sha).stdout.split('\x1f')
    if len(o)<5: return (r.repo_name,r.context_file,bool(r.first_commit_ai_created),None)
    an,ae,cn,ce,msg=o
    hit=r.first_commit_sha in ai or bool(r.first_commit_ai_created) or bool(message_hit(msg)) or bool(ident_hit(an,ae)) or bool(ident_hit(cn,ce))
    return (r.repo_name,r.context_file,bool(r.first_commit_ai_created),hit)
with cf.ThreadPoolExecutor(16) as ex: res=list(ex.map(job,c.itertuples()))
D=pd.DataFrame(res,columns=['repo','file','ai_dataset','ai_v5'])
D.to_csv('data/intermediate/context_file_creators.csv',index=False)
print(D.ai_dataset.mean(), D.ai_v5.mean(), D.ai_v5.isna().sum())
