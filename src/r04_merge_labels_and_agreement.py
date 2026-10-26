"""Final LLM labels (agreed label, else adjudicated label) and agreement between the two LLM labellers.
Writes data/intermediate/review/final_labels.json and agreement.json."""
import json, glob, collections
from sklearn.metrics import cohen_kappa_score as kappa
V = 'data/intermediate/review'
def load(f): return {x['id']: x for x in json.load(open(f))}
def loadB(p):
    B = {}
    for f in sorted(glob.glob(f'{V}/{p}')): B.update(load(f))
    return B
O, AG = {}, {}
def merge(name, A, B, adj, key='label', binary=None):
    O[name] = {i: (A[i][key] if A[i][key] == B[i][key] else adj[i]['final']) for i in A}
    ids = sorted(A); a = [A[i][key] for i in ids]; b = [B[i][key] for i in ids]
    r = {'n': len(ids), 'agree': sum(x == y for x, y in zip(a, b)) / len(ids), 'kappa': kappa(a, b)}
    if binary:
        a2 = [binary(x) for x in a]; b2 = [binary(x) for x in b]
        r.update(bin_agree=sum(x == y for x, y in zip(a2, b2)) / len(ids), bin_kappa=kappa(a2, b2))
    AG[name] = r
adjf = lambda n: load(f'{V}/adjudicated_{n}.json') if glob.glob(f'{V}/adjudicated_{n}.json') else {}
merge('paths', load(f'{V}/llm_A_missing_paths.json'), loadB('llm_B_missing_paths_*.json'), adjf('missing_paths'), binary=lambda x: x == 'WRONG_PATH')
merge('rules', load(f'{V}/llm_A_broken_rules.json'), load(f'{V}/llm_B_broken_rules.json'), adjf('broken_rules'), binary=lambda x: x == 'TRUE')
# commits: confirmed = TRUE and the commit itself added the import
A, B, adj = load(f'{V}/llm_A_flagged_commits.json'), load(f'{V}/llm_B_flagged_commits.json'), adjf('flagged_commits')
for d in (A, B):
    for v in d.values(): v['conf'] = bool(v['label'] == 'TRUE' and v.get('added_in_commit') is not False)
O['commits'] = {i: (A[i]['conf'] if (A[i]['label'], A[i].get('added_in_commit')) == (B[i]['label'], B[i].get('added_in_commit'))
                    else bool(adj[i]['final'] == 'TRUE' and adj[i].get('added_in_commit') is not False)) for i in A}
ids = sorted(A); AG['commits'] = {'n': len(ids), 'agree': sum(A[i]['conf'] == B[i]['conf'] for i in ids) / len(ids),
                                  'kappa': kappa([A[i]['conf'] for i in ids], [B[i]['conf'] for i in ids])}
for n, f in [('found', 'found_paths'), ('agentlabel', 'agent_labels'), ('unflagged', 'unflagged_commits')]:
    merge(n, load(f'{V}/llm_A_{f}.json'), load(f'{V}/llm_B_{f}.json'), adjf(f))
# Rules that held: the first round (llm_A/B_held_rules.json) was a pilot. Its disagreements came from cases the
# codebook did not cover (build files, dynamic loading, overlapping labels). After adding decision rules for
# them, both labellers labelled all 40 rules again; the analysis uses this second round.
merge('held_pilot', load(f'{V}/llm_A_held_rules.json'), load(f'{V}/llm_B_held_rules.json'), adjf('held_rules'))
merge('held', load(f'{V}/round2_llm_A_held_rules.json'), load(f'{V}/round2_llm_B_held_rules.json'),
      load(f'{V}/round2_adjudicated_held_rules.json'))
json.dump({k: {str(i): v for i, v in d.items()} for k, d in O.items()}, open(f'{V}/final_labels.json', 'w'), indent=1)
json.dump(AG, open(f'{V}/agreement.json', 'w'), indent=1)
for k, d in O.items(): print(k, dict(collections.Counter(d.values())))
