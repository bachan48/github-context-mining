import pandas as pd, requests, os, concurrent.futures as cf, json, gzip, subprocess, tempfile, shutil
c=pd.read_csv('data/intermediate/context_file_candidates.csv')
os.makedirs('data/intermediate/fetched_files',exist_ok=True); os.makedirs('data/intermediate/file_trees',exist_ok=True); os.makedirs('data/intermediate/gitignore',exist_ok=True); os.makedirs('/tmp/ctxgit',exist_ok=True)
S=requests.Session()
def get(repo,sha,path):
    for _ in range(3):
        try:
            r=S.get(f'https://raw.githubusercontent.com/{repo}/{sha}/{path}',timeout=25)
            if r.status_code==200: return r.text
            if r.status_code==404: return None
        except Exception: pass
    return None
def filejob(row):
    repo,sha,path=row.repo_name,row.last_commit_sha,row.context_file
    d=f"data/intermediate/fetched_files/{repo.replace('/','__')}"; os.makedirs(d,exist_ok=True)
    fn=f"{d}/ctx__{path.replace('/','__')}"
    if not os.path.exists(fn):
        t=get(repo,sha,path)
        if t: open(fn,'w').write(t)
def repojob(row):
    repo,sha=row.repo_name,row.last_commit_sha; key=repo.replace('/','__'); d=f"data/intermediate/fetched_files/{key}"; os.makedirs(d,exist_ok=True)
    if not os.path.exists(f'{d}/README.md.done'):
        for p in ['README.md','readme.md','Readme.md','README.MD']:
            t=get(repo,sha,p)
            if t: open(f'{d}/doc__README.md','w').write(t); break
        open(f'{d}/README.md.done','w').write('1')
    gi=f'data/intermediate/gitignore/{key}'
    if not os.path.exists(gi): open(gi,'w').write(get(repo,sha,'.gitignore') or '')
    tf=f'data/intermediate/file_trees/{key}.json.gz'
    if not os.path.exists(tf):
        td=tempfile.mkdtemp(dir='/tmp/ctxgit')
        try:
            g=lambda *a: subprocess.run(['git','-C',td,*a],capture_output=True,text=True,timeout=300)
            g('init','-q'); g('remote','add','origin',f'https://github.com/{repo}.git')
            if g('fetch','-q','--depth','1','--filter=blob:none','origin',sha).returncode==0:
                out=g('ls-tree','-r','-t','FETCH_HEAD').stdout
                json.dump({'paths':[(l.split('\t',1)[1],l.split()[1]) for l in out.splitlines() if '\t' in l]},gzip.open(tf,'wt'))
        except Exception: pass
        finally: shutil.rmtree(td,ignore_errors=True)
with cf.ThreadPoolExecutor(16) as ex: list(ex.map(filejob,c.itertuples()))
# repo-level: take the row with latest last_commit (use any)
g=c.sort_values('timestamp').drop_duplicates('repo_name',keep='last')
with cf.ThreadPoolExecutor(12) as ex: list(ex.map(repojob,g.itertuples()))
print('ctx files',sum(len([f for f in os.listdir('data/intermediate/fetched_files/'+d) if f.startswith('ctx__')]) for d in os.listdir('data/intermediate/fetched_files')))
print('trees',len(os.listdir('data/intermediate/file_trees')),'readmes',sum(os.path.exists(f'data/intermediate/fetched_files/{d}/doc__README.md') for d in os.listdir('data/intermediate/fetched_files')))
