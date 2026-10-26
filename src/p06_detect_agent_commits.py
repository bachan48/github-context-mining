import os as _os
CLONES=_os.environ.get('CLONES','clones')            # blobless clones for claim history (RQ1, RQ2)
CLONES_FULL=_os.environ.get('CLONES_FULL','clones_full')  # clones for rules and commits (RQ3)
import sys,json,os,glob,collections,concurrent.futures as cf
sys.path.insert(0,'src'); from agent_traces import *
import pandas as pd
c=pd.read_csv('data/intermediate/context_file_candidates.csv')
ai=pd.read_csv('data/raw/commits.csv',usecols=['repo_name','commit_sha'])
aimap=ai.groupby('repo_name').commit_sha.apply(set).to_dict()
os.makedirs('data/intermediate/agent_traces',exist_ok=True)
def job(f):
    J=json.load(open(f))
    if 'rules' not in J: return J.get('repo'),'norules'
    repo=J['repo']; key=repo.replace('/','__'); out=f'data/intermediate/agent_traces/{key}.json'
    if os.path.exists(out): return repo,'skip'
    d=CLONES_FULL+'/'+key
    g=c[c.repo_name==repo]
    since=(pd.to_datetime(g.created_at).min()-pd.Timedelta(days=2)).strftime('%Y-%m-%d')
    n0=int(G(d,'rev-list','--count',J['head']).stdout.strip() or 0)
    lab,C=label_repo(d,aimap.get(repo,set()),head=J['head'],window_start=since)
    n1=int(G(d,'rev-list','--count',J['head']).stdout.strip() or 0)
    if n1<n0:
        G(d,'fetch','-q','--filter=blob:none',f'--shallow-since={since}','origin',g.branch.iloc[0])
    json.dump({'repo':repo,'n_before':n0,'n_after':n1,'labels':lab},open(out,'w'))
    return repo,(n0,n1,sum(v['agent'] for v in lab.values()))
fs=sorted(glob.glob('data/intermediate/rule_checks/*.json'))
with cf.ThreadPoolExecutor(4) as ex:
    for r in ex.map(job,fs): print(*r,flush=True)
