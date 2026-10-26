import os as _os
CLONES=_os.environ.get('CLONES','clones')            # blobless clones for claim history (RQ1, RQ2)
CLONES_FULL=_os.environ.get('CLONES_FULL','clones_full')  # clones for rules and commits (RQ3)
import pandas as pd, os, json, subprocess, sys, datetime as dt, concurrent.futures as cf, traceback, re
sys.path.insert(0,'src'); from claims_extractor import extract, build_index, check
c=pd.read_csv('data/intermediate/context_file_candidates.csv')
r=pd.read_csv('data/raw/repos.csv',low_memory=False,usecols=['repo_name','scanned_at','commits'])
c=c.merge(r,on='repo_name',how='left',suffixes=('','_r'))
os.makedirs('data/intermediate/claim_histories',exist_ok=True)
def G(d,*a,timeout=600):
    return subprocess.run(['git','-C',d,*a],capture_output=True,text=True,timeout=timeout,errors='ignore')
def tree_at(d,sha,cache):
    if sha not in cache:
        out=G(d,'ls-tree','-r','-t',sha).stdout
        cache[sha]=build_index([(l.split('\t',1)[1],l.split()[1]) for l in out.splitlines() if '\t' in l])
    return cache[sha]
def job(g):
    repo=g.repo_name.iloc[0]; key=repo.replace('/','__')
    outf=f'data/intermediate/claim_histories/{key}.json'
    if os.path.exists(outf): return 'skip'
    d=f'{CLONES}/{key}'
    branch=g.branch.iloc[0]
    t0=pd.to_datetime(g.created_at).min()-pd.Timedelta(days=2)
    snap=pd.to_datetime(g.scanned_at.iloc[0]) if isinstance(g.scanned_at.iloc[0],str) else pd.to_datetime(g.timestamp).max()
    try:
        if not os.path.exists(d+'/.git'):
            r=subprocess.run(['git','clone','-q','--filter=blob:none','--no-checkout','--single-branch','--branch',branch,
                f'--shallow-since={t0.strftime("%Y-%m-%d")}',f'https://github.com/{repo}.git',d],capture_output=True,text=True,timeout=900)
            if r.returncode: 
                json.dump({'repo':repo,'error':'clone','msg':r.stderr[-300:]},open(outf,'w')); return 'clonefail'
        else:
            G(d,'fetch','-q','--filter=blob:none',f'--shallow-since={t0.strftime("%Y-%m-%d")}','origin',branch,timeout=900)
        head=G(d,'rev-list','-1',f'--before={snap.isoformat()}','HEAD').stdout.strip() or G(d,'rev-parse','HEAD').stdout.strip()
        head_t=int(G(d,'show','-s','--format=%ct',head).stdout.strip())
        cache={}
        res={'repo':repo,'head':head,'head_t':head_t,'docs':[]}
        docs=[('ctx',f) for f in g.context_file]+[('readme','README.md')]
        for kind,path in docs:
            log=G(d,'log','--format=%H %ct',head,'--',path).stdout.split()
            vers=list(zip(log[0::2],map(int,log[1::2])))[::-1]  # oldest first
            if not vers: continue
            if kind=='readme':
                # window: versions since t0 (ctx creation); plus the version in effect at window start
                ctx_t0=int(pd.to_datetime(g.created_at).min().timestamp())
                before=[v for v in vers if v[1]<=ctx_t0]; after=[v for v in vers if v[1]>ctx_t0]
                vers=(before[-1:]+after)
                if not vers: continue
            claims={}  # path -> info
            prev=set()
            for sha,t in vers:
                txt=G(d,'show',f'{sha}:{path}').stdout
                cur={}
                for cl in extract(txt): cur[cl['path'].rstrip('/')]=cl
                for p,cl in cur.items():
                    if p not in claims:
                        idx=tree_at(d,sha,cache)
                        claims[p]={'path':p,'kind':cl['kind'],'arch':cl['arch'],'root':cl.get('root'),'intro_sha':sha,'intro_t':t,'exist_intro':check(cl,idx)!='missing','removed_t':None}
                    else: claims[p]['removed_t']=None
                for p in prev-set(cur): claims[p]['removed_t']=t
                prev=set(cur)
            hidx=tree_at(d,head,cache)
            for p,cl in claims.items():
                cl['exist_head']=check(cl,hidx)!='missing'
                cl['present_head']=cl['removed_t'] is None
                # when did path disappear (if existed at intro and gone by head, or at claim removal)
                if cl['exist_intro'] and not cl['exist_head']:
                    q=p if not cl.get('root') else p
                    lr=G(d,'log','-1','--format=%H %ct',head,'--',q).stdout.split()
                    cl['path_gone_t']=int(lr[1]) if len(lr)>1 else None
                if cl['present_head'] is False and cl['exist_intro']:
                    # did path exist right before claim removal?
                    pass
            res['docs'].append({'kind':kind,'file':path,'nvers':len(vers),'claims':list(claims.values())})
        json.dump(res,open(outf,'w')); return 'ok'
    except Exception as e:
        json.dump({'repo':repo,'error':'exc','msg':traceback.format_exc()[-500:]},open(outf,'w')); return 'exc'
groups=[g for _,g in c.groupby('repo_name')]
groups=[g for g in groups if (g.commits_r.iloc[0] if 'commits_r' in g else 0)<400000]
if len(sys.argv)>1: groups=groups[:int(sys.argv[1])]
print(len(groups),flush=True)
import collections; cnt=collections.Counter()
with cf.ThreadPoolExecutor(10) as ex:
    for i,x in enumerate(ex.map(job,groups)):
        cnt[x]+=1
        if i%100==0: print(i,dict(cnt),flush=True)
print(dict(cnt))
