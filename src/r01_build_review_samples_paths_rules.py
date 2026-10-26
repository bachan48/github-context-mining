import os as _os
CLONES=_os.environ.get('CLONES','clones')            # blobless clones for claim history (RQ1, RQ2)
CLONES_FULL=_os.environ.get('CLONES_FULL','clones_full')  # clones for rules and commits (RQ3)
"""Prepare packets for the second, blind labeling pass and for the found-claim and held-rule checks."""
import json,glob,random,subprocess,re,os,pandas as pd
random.seed(2027)
H={}
for f in glob.glob('data/intermediate/claim_histories/*.json'):
    j=json.load(open(f))
    if 'error' not in j: H[j['repo']]=j
def G(d,*a): return subprocess.run(['git','-C',d,*a],capture_output=True,text=True,errors='ignore').stdout
# 1) second pass, path claims (blind: no fate, no first label)
v=json.load(open('data/intermediate/review/sample_missing_paths.json'))
P=[]
for x in v:
    k=x['repo'].replace('/','__')
    P.append(dict(id=x['id'],repo=x['repo'],clone=CLONES+'/'+k,head=H[x['repo']]['head'] if x['repo'] in H else 'HEAD',
                  document='context file' if x['doc']=='ctx' else 'README',claimed_path=x['claimed_path'],tree_root=x['tree_root'],context=x['context']))
json.dump(P,open('data/intermediate/review/llm_B_input_missing_paths.json','w'),indent=1)
# 2) second pass, rules and commits (drop first-pass hints)
R=json.load(open('data/intermediate/review/sample_broken_rules.json')); json.dump(R,open('data/intermediate/review/llm_B_input_broken_rules.json','w'),indent=1)
Cm=json.load(open('data/intermediate/review/sample_flagged_commits.json')); json.dump(Cm,open('data/intermediate/review/llm_B_input_flagged_commits.json','w'),indent=1)
# 3) found-claim check: context-file claims that exist at the snapshot; 50 exact, 50 suffix-only matches
D=pd.read_pickle('data/intermediate/claim_histories.pkl')
D=D[(D.doc=='ctx')&D.present_head&D.exist_head]
rows=D.sample(frac=1,random_state=7)
def idx(clone,sha):
    out=G(clone,'ls-tree','-r','-t','--name-only',sha).split('\n')
    return set(p for p in out if p)
F=[];need={'exact':50,'suffix':50}; cache={}
for r in rows.itertuples():
    if not any(need.values()): break
    k=r.repo.replace('/','__'); clone=CLONES+'/'+k; head=H[r.repo]['head']
    if r.repo not in cache: cache[r.repo]=idx(clone,head)
    ps=cache[r.repo]; p=r.path.rstrip('/'); c=[p]+([r.root+'/'+p] if isinstance(r.root,str) and r.root else [])
    if any(q in ps for q in c): mt='exact'; matches=[q for q in c if q in ps]
    else:
        mt='suffix'; matches=[q for q in ps if any(q.endswith('/'+cc) for cc in c)][:5]
        if not matches: continue
    if need[mt]==0: continue
    txt=G(clone,'show',f'{head}:{r.file}').split('\n')
    li=[i for i,l in enumerate(txt) if p in l]
    if not li: continue
    i=li[0]; ctx='\n'.join(txt[max(0,i-6):i+5])
    if r.kind=='tree': ctx='\n'.join(txt[max(0,i-15):i+4])
    F.append(dict(id=len(F),repo=r.repo,clone=clone,head=head,context_file=r.file,claimed_path=r.path,tree_root=r.root if isinstance(r.root,str) else None,
                  match_type=mt,matching_paths=matches,context=ctx))
    need[mt]-=1
json.dump(F,open('data/intermediate/review/sample_found_paths.json','w'),indent=1)
# 4) held rules: random 40 of the rules with zero violations at writing and at snapshot
rules=pd.read_csv('data/intermediate/rule_status.csv')
held=rules[(rules.intro==0)&(rules['head']==0)]
J={}
for f in glob.glob('data/intermediate/rule_checks/*.json'):
    j=json.load(open(f))
    if 'rules' in j:
        for r in j['rules']: J[r['rid']]=(j,r)
Hd=[]
for rid in held.rid.sample(40,random_state=11):
    j,r=J[rid]; k=j['repo'].replace('/','__')
    Hd.append(dict(id=len(Hd),repo=j['repo'],clone=CLONES_FULL+'/'+k,snapshot=j['head'],context_file=r['file'],rule_text=r['text'],
                   rule=dict(source=r['source'],exceptions=r['exceptions'],forbidden_internal=r['ti'],forbidden_external=r['te'],polarity=r['polarity'],sibling_scope=r['sibling'])))
json.dump(Hd,open('data/intermediate/review/sample_held_rules.json','w'),indent=1)
print(len(P),len(R),len(Cm),len(F),len(Hd), len(held))
