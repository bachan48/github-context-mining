import os as _os
CLONES=_os.environ.get('CLONES','clones')            # blobless clones for claim history (RQ1, RQ2)
CLONES_FULL=_os.environ.get('CLONES_FULL','clones_full')  # clones for rules and commits (RQ3)
import json,glob,re,collections,sys,os
sys.path.insert(0,'src')
from p05_check_rules_and_commits import *
import pandas as pd
lab=pd.read_csv('data/intermediate/rule_status.csv').set_index('rid')
ai=pd.read_csv('data/raw/commits.csv',usecols=['repo_name','commit_sha'])
aimap=ai.groupby('repo_name').commit_sha.apply(set).to_dict()
AL={}
def who(d,sha,aiset):
    key=os.path.basename(d)
    if key not in AL: AL[key]=json.load(open(f'data/intermediate/agent_traces/{key}.json'))['labels']
    t=G(d,'show','-s','--format=%ct',sha).stdout.strip()
    l=AL[key].get(sha)
    if l is None: return 'unknown',(int(t) if t else None)
    return ('agent' if l['agent'] else 'human'),(int(t) if t else None)
rows=[]
for f in glob.glob('data/intermediate/rule_checks/*.json'):
    J=json.load(open(f))
    if 'rules' not in J: continue
    repo=J['repo']; d=CLONES_FULL+'/'+repo.replace('/','__'); aiset=aimap.get(repo,set())
    shallow=set(open(d+'/.git/shallow').read().split()) if os.path.exists(d+'/.git/shallow') else set()
    for r in J['rules']:
        n=J['intro_viol'].get(r['rid'],0)
        if not n or not r['intro_sha']: continue
        res=build_resolver(d,J['head'])
        # find violating lines at intro
        out=G(d,'grep','-I','-n','-P',GREP_RE,r['intro_sha'],'--',*CODE_GLOBS).stdout
        lines=[]
        for l in out.splitlines():
            try:_,fp,ln,txt=l.split(':',3)
            except ValueError: continue
            lg=lang_of(fp)
            if not lg or not exposed(r,fp): continue
            for spec,names,to,kind in parse(txt,lg):
                if violates(r,fp,spec,names,res.resolve(spec,fp,lg,kind),to): lines.append((fp,int(ln))); break
        rw,rt=who(d,r['intro_sha'],aiset)
        src=collections.Counter()
        for fp,ln in lines[:200]:
            b=G(d,'blame','--porcelain','-L',f'{ln},{ln}',r['intro_sha'],'--',fp).stdout
            m=re.match(r'\^?([0-9a-f]{40})',b)
            if not m: src['unknown']+=1; continue
            sha=m.group(1)
            if b.startswith('^') or sha in shallow or 'boundary' in b.split('\n',20)[-1] or '\nboundary' in b: src['before_window']+=1; continue
            w,t=who(d,sha,aiset)
            src[w or 'unknown']+=1
        rows.append(dict(rid=r['rid'],repo=repo,lab=lab.loc[r['rid'],'lab'] if r['rid'] in lab.index else None,rule_commit=rw,nviol=n,checked=len(lines[:200]),**src))
df=pd.DataFrame(rows).fillna(0); df.to_csv('data/intermediate/rule_attribution.csv',index=False)
print(df.drop(columns=['repo']).to_string())
