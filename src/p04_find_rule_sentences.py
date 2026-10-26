import os,re,json,glob
RESTRICT=r"(never|must not|mustn't|should not|shouldn't|do not|don't|cannot|can't|may not|not allowed|forbidden|prohibited|no direct|avoid|only|must only|exclusively|instead of|must go through|should go through|go through|goes through|always use|must use|bypass|without going through)"
DEP=r"(import|imports|importing|imported|depend|depends|depending|dependency|dependencies|reach into|reaches into|couple|coupled|coupling|know about|knows about|leak into|references? (?:from|into)|(?:call|calls|access|accesses|accessing|query|queries|talk to|talks to|use|uses|using) [^.]{0,40}directly|directly (?:call|access|query|use|import)\w*)"
PART=r"(`|/|::|\\\\|\b(layer|layers|module|modules|package|packages|crate|crates|namespace|component|components|service|services|domain|core|ui|api|db|database|repository|repositories|store|lib|library|utils?|client|server|backend|frontend|adapter|adapters|infra\w*|controller|controllers|handler|handlers|model|models|view|views|presenter|feature|features|internal|shared|common|platform|plugin|plugins)\b)"
pat=re.compile(RESTRICT+r".{0,100}\b"+DEP+r"\b|\b"+DEP+r"\b.{0,80}"+RESTRICT,re.I)
layer=re.compile(r"\b(layers?|layering|dependency direction|dependency rule|boundar(y|ies))\b.*\b(never|must not|only|should not|cannot|may not|not allowed|forbidden)\b|\b(never|must not|only|should not|cannot|may not)\b.*\b(layers?|boundar(y|ies))\b",re.I)
NOISE=re.compile(r"\b(npm|pnpm|yarn|pip|uv|cargo|go get|install|dependabot|renovate|version|upgrade|bump|lockfile|package-lock|timeout|never cancel)\b",re.I)
old={}
# reuse LLM classifications already made for earlier sentence sets (llm_output_batch*.json)
for f in glob.glob('data/intermediate/rule_classification/llm_output_batch*.json'):
    for x in json.load(open(f)): old[(x['repo'],x['text'])]=x
out=[];reused=0
for d in sorted(glob.glob('data/intermediate/fetched_files/*')):
    repo=os.path.basename(d).replace('__','/',1)
    for f in glob.glob(d+'/ctx__*'):
        fname=os.path.basename(f)[5:].replace('__','/')
        for i,l in enumerate(open(f,errors='ignore').read().splitlines()):
            s=l.strip()
            if len(s)<15 or len(s)>500: continue
            if not re.search(PART,s,re.I): continue
            if not (pat.search(s) or layer.search(s) or re.search(r'depguard|import-linter|importlinter|no-restricted-imports|dependency-cruiser|archunit|eslint-plugin-boundaries|arch-go|module boundar',s,re.I)): continue
            if NOISE.search(s) and not re.search(r"\bimport",s,re.I): continue
            rec={'repo':repo,'file':fname,'line':i+1,'text':s}
            if (repo,s) in old: rec['prev']=old[(repo,s)]; reused+=1
            out.append(rec)
seen={(o['repo'],o['text']) for o in out}
for (repo,t),x in old.items():
    if (repo,t) not in seen: out.append({'repo':repo,'file':x['file'],'line':x['line'],'text':t,'prev':x}); reused+=1
json.dump(out,open('data/intermediate/rule_classification/candidate_sentences.json','w'))
print(len(out),'repos',len({o['repo'] for o in out}),'reused',reused,'new',len(out)-reused)
