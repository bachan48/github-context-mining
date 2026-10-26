import os as _os
CLONES=_os.environ.get('CLONES','clones')            # blobless clones for claim history (RQ1, RQ2)
CLONES_FULL=_os.environ.get('CLONES_FULL','clones_full')  # clones for rules and commits (RQ3)
"""Packets for the agent-label check (L) and the unflagged-commit check (U)."""
import sys,json,glob,os,random,re,pandas as pd
sys.path.insert(0,'src'); from agent_traces import *
random.seed(2028)
C=pd.read_csv('data/intermediate/commit_groups_raw.csv'); P=pd.read_csv('data/intermediate/commit_rule_pairs_raw.csv')
J={}
for f in glob.glob('data/intermediate/rule_checks/*.json'):
    j=json.load(open(f))
    if 'rules' in j: J[j['repo']]=j
def clone(repo): return CLONES_FULL+'/'+repo.replace('/','__')
def evidence(repo,sha,signals):
    d=clone(repo); ev={}
    if 'S5' in signals:
        subj=G(d,'show','-s','--format=%s',sha).stdout.strip(); m=SQUASH.search(subj)
        if m: ev['pull_request_branch_ref']=f'refs/prs/{m.group(1)}'; ev['pr_parent']=G(d,'rev-parse',sha+'^').stdout.strip()
    if 'S4' in signals or 'S6' in signals:
        for m in G(d,'rev-list','--first-parent','--merges','HEAD').stdout.split():
            par=G(d,'show','-s','--format=%P',m).stdout.split()
            if len(par)>1 and (sha==m or sha in G(d,'rev-list',par[1],'--not',par[0]).stdout.split()):
                ev['merge_commit']=m; ev['merged_branch_commits_cmd']=f'git -C {d} log {par[1]} --not {par[0]}'; break
    return ev
new_only=C[(C.who=='agent')&(C.who_old!='agent')]
old=C[(C.who=='agent')&(C.who_old=='agent')]
other=C[C.who=='human']
L=[]
for grp,df,n in [('new',new_only,60),('old',old,40),('other',other,50)]:
    for r in df.sample(n,random_state=5).itertuples():
        L.append(dict(id=len(L),repo=r.repo,clone=clone(r.repo),sha=r.sha,
                      hint=(evidence(r.repo,r.sha,r.signals or '') if grp!='other' else {})))
json.dump(L,open('data/intermediate/review/sample_agent_labels.json','w'),indent=1)
key={x['id']:dict(group=g,signals=s) for x,(g,s) in zip(L,[('new',r.signals) for r in new_only.sample(60,random_state=5).itertuples()]+[('old',r.signals) for r in old.sample(40,random_state=5).itertuples()]+[('other','') for _ in range(50)])}
json.dump(key,open('data/intermediate/review/agent_label_sample_groups.json','w'),indent=1)
# U: exposed commits that the checker did not flag
U=[]
unf=C[~C.viol]
for grp,n in [('agent',50),('human',50)]:
    for r in unf[unf.who==grp].sample(n,random_state=9).itertuples():
        rids=P[(P.repo==r.repo)&(P.sha==r.sha)].rid.unique().tolist()
        rules=[dict(rule_text=x['text'],context_file=x['file'],source=x['source'],exceptions=x['exceptions'],forbidden_internal=x['ti'],
                    forbidden_external=x['te'],polarity=x['polarity'],sibling_scope=x['sibling']) for x in J[r.repo]['rules'] if x['rid'] in rids]
        U.append(dict(id=len(U),repo=r.repo,clone=clone(r.repo),sha=r.sha,rules=rules))
json.dump(U,open('data/intermediate/review/sample_unflagged_commits.json','w'),indent=1)
json.dump({u['id']:g for u,g in zip(U,['agent']*50+['human']*50)},open('data/intermediate/review/unflagged_sample_groups.json','w'))
print(len(L),len(U))
