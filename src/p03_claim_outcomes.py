import json,glob,os,pathspec,pandas as pd,numpy as np
specs={}
def ign(repo,path,root):
    k=repo.replace('/','__',1)
    if repo not in specs:
        fn=f'data/intermediate/gitignore/{k}'; t=open(fn,errors='ignore').read() if os.path.exists(fn) else ''
        pats=[]
        for ln in t.splitlines():
            try: pathspec.PathSpec.from_lines('gitwildmatch',[ln]); pats.append(ln)
            except Exception: pass
        specs[repo]=pathspec.PathSpec.from_lines('gitwildmatch',pats)
    ps=[path]+([root+'/'+path] if isinstance(root,str) and root else [])
    return any(specs[repo].match_file(p) or specs[repo].match_file(p+'/') for p in ps)
rows=[]; meta=[]
for f in glob.glob('data/intermediate/claim_histories/*.json'):
    j=json.load(open(f))
    if 'error' in j: continue
    meta.append({'repo':j['repo'],'head_t':j['head_t']})
    for d in j['docs']:
        for c in d['claims']:
            rows.append({'repo':j['repo'],'doc':d['kind'],'file':d['file'],'nvers':d['nvers'],'head_t':j['head_t'],**c})
H=pd.DataFrame(rows)
H['root']=H['root'].where(H['root'].notna(),None)
H['ignored']=[ign(r.repo,r.path,r.root) for r in H.itertuples()]
H=H[~H.ignored].copy()
def fate(r):
    if r.exist_intro:
        if r.present_head:
            return 'valid' if r.exist_head else 'rotted_unfixed'
        # claim removed before head
        if r.exist_head: return 'removed_while_valid'
        g=r.path_gone_t if pd.notna(r.path_gone_t) else None
        if g is not None and r.removed_t is not None and r.removed_t>=g: return 'rotted_fixed'
        return 'removed_while_valid'
    else:
        if r.present_head: return 'became_valid' if r.exist_head else 'never_valid'
        return 'never_valid_removed'
H['fate']=H.apply(fate,axis=1)
H.to_pickle('data/intermediate/claim_histories.pkl')
print(H.groupby('doc').size(), H.repo.nunique())
print(pd.crosstab(H.doc,H.fate,normalize='index').round(3))
print(pd.crosstab(H.doc,H.fate))
v=H[H.exist_intro]
rot=v.fate.isin(['rotted_unfixed','rotted_fixed'])
print('rot among valid-at-intro:',rot.groupby(v.doc).mean())
fixed=v[v.fate.isin(['rotted_unfixed','rotted_fixed'])]
print('share fixed:',(fixed.fate=='rotted_fixed').groupby(fixed.doc).mean())
lag=(fixed[fixed.fate=='rotted_fixed'].removed_t-fixed[fixed.fate=='rotted_fixed'].path_gone_t)/86400
print('fix lag days',lag.groupby(fixed[fixed.fate=='rotted_fixed'].doc).describe())
age=(fixed[fixed.fate=='rotted_unfixed'].head_t-fixed[fixed.fate=='rotted_unfixed'].path_gone_t)/86400
print('stale age days',age.groupby(fixed[fixed.fate=='rotted_unfixed'].doc).describe())
# per-repo
pr=H[H.doc=='ctx'].groupby('repo').apply(lambda g:(g.fate=='rotted_unfixed').any())
print('repos with >=1 unfixed rotted ctx claim',pr.mean(),len(pr))
