"""RQ3 tables for v5: final rule labels and commit groups from the layered agent detection."""
import json,glob,pandas as pd
F=json.load(open('data/intermediate/review/final_labels.json'))
R=pd.read_csv('data/intermediate/rule_status_raw.csv').drop(columns=['lab'])
v=json.load(open('data/intermediate/review/sample_broken_rules.json')); J={}
for f in glob.glob('data/intermediate/rule_checks/*.json'):
    j=json.load(open(f))
    if 'rules' in j:
        for r in j['rules']: J[r['rid']]=r
lab={}
for x in v:
    rid=[k for k,r in J.items() if r['repo']==x['repo'] and r['text']==x['rule_text'] and r['source']==x['rule']['source'] and r['ti']==x['rule']['ti'] and r['te']==x['rule']['te']][0]
    lab[rid]=F['rules'][str(x['id'])]
R['lab']=R.rid.map(lab).where(R.intro>0)
R.to_csv('data/intermediate/rule_status.csv',index=False)
C=pd.read_csv('data/intermediate/commit_groups_raw.csv')
vc=json.load(open('data/intermediate/review/sample_flagged_commits.json'))
conf={}
for x in vc:
    k=(x['repo'],x['sha']); conf[k]=conf.get(k,False) or F['commits'][str(x['id'])]
C['conf']=[conf.get((r,s),False) for r,s in zip(C.repo,C.sha)]
assert not (C.conf & ~C.viol).any()
C.to_csv('data/intermediate/commit_groups.csv',index=False)
print(R.lab.value_counts(dropna=False).to_dict()); print(C.groupby('who')[['viol','conf','fix']].sum(), C.who.value_counts().to_dict())
