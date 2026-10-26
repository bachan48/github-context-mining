"""Apply v5 agent labels to the RQ3 commit records."""
import json,glob,collections,pandas as pd,os
rows=[]
sig=collections.Counter(); old_new=collections.Counter()
for f in glob.glob('data/intermediate/rule_checks/*.json'):
    j=json.load(open(f))
    if 'rules' not in j: continue
    L=json.load(open('data/intermediate/agent_labels/'+os.path.basename(f)))['labels']
    for x in j['recs']:
        l=L.get(x['sha'])
        if l is None: new=x['who']                      # boundary commit not re-read: keep old label
        else: new='agent' if l['agent'] else ('bot' if (l['bot'] or x['who']=='bot') else 'human')
        rows.append(dict(repo=j['repo'],sha=x['sha'],rid=x['rid'],who_old=x['who'],who=new,viol=x['viol'],fix=x['fix'],
                         signals='+'.join(sorted(l['signals'])) if l else ''))
D=pd.DataFrame(rows)
C=D.groupby(['repo','sha']).agg(who=('who','first'),who_old=('who_old','first'),signals=('signals','first'),viol=('viol','max'),fix=('fix','max')).reset_index()
print(pd.crosstab(C.who_old,C.who))
C=C[C.who!='bot']
print(C.who.value_counts(), C[C.who=='agent'].repo.nunique())
print(C[C.who=='agent'].signals.value_counts())
D.to_csv('data/intermediate/commit_rule_pairs_raw.csv',index=False); C.to_csv('data/intermediate/commit_groups_raw.csv',index=False)
