import re
EXT=r"\.(ts|tsx|js|jsx|mjs|cjs|py|pyi|md|mdx|json|jsonc|ya?ml|toml|cfg|ini|sh|ps1|sql|css|scss|less|html|vue|svelte|go|mod|rs|java|kt|kts|scala|groovy|gradle|cs|csproj|sln|fs|vb|rb|rake|php|c|cc|cpp|cxx|h|hh|hpp|hxx|m|mm|swift|dart|ex|exs|erl|lua|r|jl|zig|nim|clj|hs|ml|pl|txt|lock|prisma|graphql|proto|xml|cmake|mk|bzl|env\.example)$"
STARTS=('src/','lib/','app/','apps/','packages/','tests/','test/','docs/','scripts/','components/','server/','client/','backend/','frontend/','services/','web/','core/','utils/','public/','.github/','.claude/','modules/','examples/','tools/','config/','internal/','pages/','hooks/','packages/','crates/','cmd/','pkg/','include/','src-tauri/','test/','spec/','app/','lib/','plugins/','extensions/','static/','assets/','e2e/','migrations/','infra/','deploy/')
GEN=re.compile(r"(^|/)(node_modules|dist[-\w]*|build|generated|[\w-]*-generated|output|outputs|results|snapshots|\.gradle|mxbuild|logs?|data|reports?|artifacts|\.next|out|coverage|\.venv|venv|__pycache__|target|\.turbo|\.cache|tmp|\.git|\.pytest_cache|\.mypy_cache|site-packages|\.nuxt|\.output|storybook-static|htmlcov|\.tox|egg-info)(/|$)|\.env($|\.)|\.log$|local|\.egg-info|^\.claude/(settings|worktrees|plans)|/\*\*|~")
ARCH_H=re.compile(r"architect|structure|layout|organi[sz]|module|director|folder|codebase|overview|component|layer|package|map|where|key files|file|boundar|design",re.I)
PATHTOK=re.compile(r"^[\w@.\-\[\]()+]+(/[\w@.\-\[\]()+]+)*/?$")
def norm(t):
    t=t.strip().strip('"\'')
    if t.startswith('./'): t=t[2:]
    return t
PLACE=re.compile(r"\[|\{|YYYY|HHMM|(^|[/_-])(your|my|foo|bar|baz|xxx|example|sample|name|modulename|module-name|plugin-name|feature|component-name|path/to|some|new|<)([/_.-]|$)|NNN|0000",re.I)
def ok_tok(t):
    if PLACE.search(t) or t.startswith('+'): return False
    if not t or len(t)>150 or ' ' in t: return False
    if t.startswith(('http','/','@','~','$','-','.git/','../')) or '//' in t: return False
    if any(ch in t for ch in '*{}<>:=,;|?!#%^&"\'`\\'): return False
    if '...' in t: return False
    if not PATHTOK.match(t): return False
    if '/' not in t: return False
    if re.fullmatch(r"\d+(\.\d+)*/\d+.*",t): return False
    looks = t.endswith('/') or re.search(EXT,t) or t.startswith(STARTS)
    if not looks: return False
    if GEN.search(t): return False
    return True
BR=re.compile(r"^(?P<pre>[\s│|`]*)(├──|└──|\|--|`--|├─|└─|\+--|├|└)\s*(?P<name>.+)$")
def extract(text):
    """returns list of dicts: path, kind(inline|tree), arch(bool), line"""
    out=[]; head=''; infence=False; fence=[]; fstart=0
    lines=text.splitlines()
    def tree(block,start,arch):
        stack=[]; root=None; res=[]
        for j,l in enumerate(block):
            m=BR.match(l)
            if not m:
                s=l.strip().split('#')[0].split('//')[0].strip()
                if j==0 or (root is None and not stack and s.endswith('/')):
                    if s.endswith('/') and ' ' not in s and s not in ('./','/'): root=s.rstrip('/')
                continue
            depth=len(m.group('pre').replace('\t','    '))
            name=m.group('name').split(' #')[0].split('  ')[0].split(' //')[0].split(' - ')[0].split(' —')[0].split(' (')[0].strip().strip('`*')
            if not name or ' ' in name or not re.fullmatch(r"[\w@.\-()+]+/?",name) or PLACE.search(name):
                continue
            while stack and stack[-1][0]>=depth: stack.pop()
            if any(not s[1].endswith('/') for s in stack):  # parent is a file -> broken tree
                stack.append((depth,name)); continue
            parts=[s[1].rstrip('/') for s in stack]+[name]
            p='/'.join(parts)
            stack.append((depth,name))
            if (name.endswith('/') or re.search(EXT,name)) and not SKIPLINE.search(l):
                res.append((p,start+j+1))
        outp=[]
        for p,ln in res:
            p=norm(p)
            if '...' in p or '*' in p or '<' in p or GEN.search(p) or PLACE.search(p) or (root and PLACE.search(root)): continue
            outp.append({'path':p,'root':root,'kind':'tree','arch':True,'line':ln})
        return outp
    SKIPLINE=re.compile(r"\b(create|creates|creating|add (a |new |your )?(test|file)|new file|e\.g\.|eg\b|for example|such as|example|compiles? to|outputs? to|output (goes|is)|generated|build output|will be|if (it )?exists?|copy|your|submodule|symlink|delete|remove|gitignored|ignored|not committed|local only|mirror(ing)?|named|name (it|them)|→|->|=>)",re.I)
    for i,l in enumerate(lines):
        st=l.strip()
        if st.startswith('```') or st.startswith('~~~'):
            if infence:
                if any(BR.match(x) for x in fence): out+=tree(fence,fstart,bool(ARCH_H.search(head)))
                infence=False; fence=[]
            else: infence=True; fstart=i+1; fence=[]
            continue
        if infence: fence.append(l); continue
        m=re.match(r"^#{1,6}\s+(.*)",st)
        if m: head=m.group(1); continue
        if SKIPLINE.search(l): continue
        for t in re.findall(r"`([^`\n]+)`",l):
            t=norm(t)
            if ok_tok(t): out.append({'path':t,'root':None,'kind':'inline','arch':bool(ARCH_H.search(head)),'line':i+1})
    # dedupe by path
    seen={}; 
    for c in out:
        k=c['path'].rstrip('/')
        if k not in seen: seen[k]=c
    return list(seen.values())
def verify(claim,pathset,dirset,top):
    p=claim['path'].rstrip('/')
    cands=[p]
    if claim.get('root'): cands=[claim['root']+'/'+p,p]
    for q in cands:
        if q in pathset or q in dirset: return 'exact'
    for q in cands:
        suf='/'+q
        if q in SUFFIX_CACHE.get(id(pathset),{}) : return 'suffix'
    return None
SUFFIX_CACHE={}
def build_index(paths):
    ps=set(); ds=set(); suf=set()
    for p,t in paths:
        ps.add(p)
        if t=='tree': ds.add(p)
        parts=p.split('/')
        for k in range(1,len(parts)): suf.add('/'.join(parts[k:]))
    return ps,ds,suf
def check(claim,idx):
    ps,ds,suf=idx
    p=claim['path'].rstrip('/')
    cands=[p]+([claim['root']+'/'+p] if claim.get('root') else [])
    if any(q in ps for q in cands): return 'exact'
    if any(q in suf for q in cands): return 'suffix'
    return 'missing'
