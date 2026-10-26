"""Collect the items where the two LLM labellers disagreed, for the adjudication pass.
Writes data/intermediate/review/disagreements_<check>.json."""
import json, glob
V = 'data/intermediate/review'
def load(f): return {x['id']: x for x in json.load(open(f))}
CHECKS = {  # check name: (sample file, labeller A file, labeller B file or glob)
    'missing_paths': ('llm_B_input_missing_paths.json', 'llm_A_missing_paths.json', 'llm_B_missing_paths_*.json'),
    'broken_rules': ('sample_broken_rules.json', 'llm_A_broken_rules.json', 'llm_B_broken_rules.json'),
    'flagged_commits': ('llm_B_input_flagged_commits.json', 'llm_A_flagged_commits.json', 'llm_B_flagged_commits.json'),
    'found_paths': ('sample_found_paths.json', 'llm_A_found_paths.json', 'llm_B_found_paths.json'),
    'held_rules': ('sample_held_rules.json', 'llm_A_held_rules.json', 'llm_B_held_rules.json'),
    'agent_labels': ('sample_agent_labels.json', 'llm_A_agent_labels.json', 'llm_B_agent_labels.json'),
    'unflagged_commits': ('sample_unflagged_commits.json', 'llm_A_unflagged_commits.json', 'llm_B_unflagged_commits.json'),
}
key = lambda x: (x['label'], x.get('added_in_commit'))
for name, (s, a, b) in CHECKS.items():
    S = load(f'{V}/{s}'); A = load(f'{V}/{a}'); B = {}
    for f in sorted(glob.glob(f'{V}/{b}')): B.update(load(f))
    out = [dict(item=S[i], label_1=A[i]['label'], reason_1=A[i].get('reason', A[i].get('evidence')), added_1=A[i].get('added_in_commit'),
                label_2=B[i]['label'], reason_2=B[i].get('reason', B[i].get('evidence')), added_2=B[i].get('added_in_commit'))
           for i in sorted(A) if key(A[i]) != key(B[i])]
    json.dump(out, open(f'{V}/disagreements_{name}.json', 'w'), indent=1); print(name, len(out))
