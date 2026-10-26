"""Export the clean, human-readable tables in data/processed/ and the review files in manual_review/.

Reads the intermediate outputs of the pipeline (data/intermediate/) and writes:
  data/processed/*.csv            one row per project, file, claim, rule or commit
  manual_review/*.csv             one sheet per manual check: the item, its evidence links, the two LLM labels,
                                  the adjudicated label, and the final label used in the analysis
"""
import json, glob, os, re, sys, pandas as pd
I = sys.argv[1] if len(sys.argv) > 1 else 'data/intermediate'
P, MR = 'data/processed', 'manual_review'
for d in (P, MR): os.makedirs(d, exist_ok=True)
gh = lambda repo: f'https://github.com/{repo}'

# ---------------------------------------------------------------- projects and context files
cand = pd.read_csv(f'{I}/context_file_candidates.csv')
claims = pd.read_pickle(f'{I}/claim_histories.pkl')
creator = pd.read_csv(f'{I}/context_file_creators.csv')
sample_repos = set(claims.repo)
hist_ok = {json.load(open(f))['repo'] for f in glob.glob(f'{I}/claim_histories/*.json') if 'error' not in open(f).read(200)}
proj = (cand.drop_duplicates('repo_name')
        .rename(columns={'repo_name': 'repo', 'mainLanguage': 'main_language', 'stargazers': 'stars'})
        [['repo', 'main_language', 'stars', 'contributors', 'commits', 'default_branch', 'scanned_at']])
proj['history_cloned'] = proj.repo.isin(hist_ok)
proj['in_sample'] = proj.repo.isin(sample_repos)
proj['github'] = proj.repo.map(gh)
proj.to_csv(f'{P}/projects.csv', index=False)

files = cand.rename(columns={'repo_name': 'repo', 'context_file': 'file', 'line_count': 'lines'})[
    ['repo', 'file', 'lines', 'created_at', 'first_commit_sha', 'last_commit_sha']]
files = files.merge(creator.rename(columns={'ai_v5': 'first_commit_has_agent_trace'})[['repo', 'file', 'first_commit_has_agent_trace']],
                    on=['repo', 'file'], how='left')
ctxc = claims[claims.doc == 'ctx'].groupby(['repo', 'file']).agg(n_versions=('nvers', 'first'), n_path_claims=('path', 'size')).reset_index()
files = files.merge(ctxc, on=['repo', 'file'], how='left')
files['in_sample'] = files.n_path_claims.fillna(0) > 0
files['file_type'] = files.file.replace({'.github/copilot-instructions.md': 'Copilot instructions'})
files.to_csv(f'{P}/context_files.csv', index=False)

# ---------------------------------------------------------------- path claims
OUT = {'valid': 'still_valid', 'rotted_fixed': 'stale_fixed', 'rotted_unfixed': 'stale_unfixed',
       'removed_while_valid': 'deleted_while_valid', 'never_valid': 'never_valid',
       'never_valid_removed': 'never_valid_deleted', 'became_valid': 'became_valid'}
ts = lambda x: pd.to_datetime(x, unit='s', utc=True)
pc = pd.DataFrame({
    'repo': claims.repo, 'document': claims.doc.map({'ctx': 'context_file', 'readme': 'readme'}), 'file': claims.file,
    'path': claims.path, 'form': claims.kind, 'tree_root': claims.root, 'in_structure_section': claims.arch,
    'language': claims.lang, 'language_group': claims.lg.map({'tjp': 'TS/JS/Python', 'other': 'other'}),
    'file_versions': claims.nvers,
    'written_commit': claims.intro_sha, 'written_at': ts(claims.intro_t),
    'valid_when_written': claims.exist_intro,
    'in_file_at_snapshot': claims.present_head, 'found_at_snapshot': claims.exist_head,
    'removed_from_file_at': ts(claims.removed_t), 'path_removed_at': ts(claims.path_gone_t),
    'snapshot_at': ts(claims.head_t), 'history_outcome': claims.fate.map(OUT)})
pc.insert(0, 'claim_id', [f'C{i:05d}' for i in range(len(pc))])
pc.to_csv(f'{P}/path_claims.csv', index=False)

# ---------------------------------------------------------------- dependency rules
J = {}
for f in glob.glob(f'{I}/rule_checks/*.json'):
    j = json.load(open(f))
    if 'rules' in j:
        for r in j['rules']: J[r['rid']] = (j, r)
R = pd.read_csv(f'{I}/rule_status.csv')
lang = proj.set_index('repo').main_language.to_dict()
rows = []
for x in R.itertuples():
    j, r = J[x.rid]
    status = 'held' if x.intro == 0 and x.head == 0 else ('broken_when_written' if x.intro > 0 else 'broken_later')
    rows.append(dict(rule_id=x.rid, repo=x.repo, language=lang.get(x.repo), context_file=r['file'], line=r['line'], rule_text=r['text'],
                     rule_type={'internal_boundary': 'internal', 'external_boundary': 'external_library'}[x.cat], polarity=r['polarity'],
                     applies_to=';'.join(r['source']), exempt=';'.join(r['exceptions']), forbidden_folders=';'.join(r['ti']),
                     forbidden_packages=';'.join(r['te']), sibling_scope=r['sibling'], written_commit=r['intro_sha'], written_at=ts(r['intro_t']) if r['intro_t'] else None,
                     breaking_imports_at_writing=x.intro, breaking_imports_at_snapshot=x.head, status=status, review_label=x.lab,
                     link=f"{gh(x.repo)}/blob/{r['intro_sha']}/{r['file']}#L{r['line']}" if r['intro_sha'] else None))
rules = pd.DataFrame(rows); rules.to_csv(f'{P}/dependency_rules.csv', index=False)
allr = json.load(open(f'{I}/rule_classification/all_rule_sentences.json'))
pd.DataFrame([dict(repo=a['repo'], context_file=a['file'], line=a['line'], sentence=a['text'], is_dependency_rule=a['is_dependency_rule'],
                   category=a['category'], checkable=a['checkable'], llm_note=a.get('note')) for a in allr]).to_csv(f'{P}/rule_candidate_sentences.csv', index=False)

# ---------------------------------------------------------------- commits
C = pd.read_csv(f'{I}/commit_groups.csv'); Pp = pd.read_csv(f'{I}/commit_rule_pairs_raw.csv')
def traces(s):
    s = set(str(s).split('+')) if isinstance(s, str) else set()
    return pd.Series({'trace_message': bool(s & {'S1', 'S2'}), 'trace_agent_account': 'S3' in s, 'trace_pull_request': bool(s & {'S4', 'S5', 'S6'})})
com = pd.concat([C[['repo', 'sha']], C.signals.apply(traces)], axis=1)
com['group'] = C.who.map({'agent': 'agent_assisted', 'human': 'other'})
com['trace_codes'] = C.signals.fillna('')
com['flagged_break'] = C.viol; com['confirmed_break'] = C.conf; com['repair'] = C.fix
com['github'] = [f'{gh(r)}/commit/{s}' for r, s in zip(C.repo, C.sha)]
com.to_csv(f'{P}/exposed_commits.csv', index=False)
Pp[Pp.who != 'bot'].rename(columns={'rid': 'rule_id', 'who': 'group', 'viol': 'flagged_break', 'fix': 'repair'})[
    ['repo', 'sha', 'rule_id', 'group', 'flagged_break', 'repair']].replace({'group': {'agent': 'agent_assisted', 'human': 'other'}}).to_csv(f'{P}/commit_rule_pairs.csv', index=False)
A = pd.read_csv(f'{I}/rule_attribution.csv')
A.rename(columns={'rid': 'rule_id', 'lab': 'review_label', 'rule_commit': 'rule_written_by', 'nviol': 'breaking_imports_at_writing',
                  'before_window': 'lines_older_than_window', 'agent': 'lines_added_by_agent_assisted', 'human': 'lines_added_by_other'}).to_csv(f'{P}/rule_attribution.csv', index=False)

# ---------------------------------------------------------------- manual review files
V = f'{I}/review'
FL = json.load(open(f'{V}/final_labels.json'))
def load(fn): return {x['id']: x for x in json.load(open(fn))}
def both(name, items, cols, A, B, adj, final, extra=None):
    """Write one review sheet: item and evidence, the two LLM labels, the adjudicated label and the final label."""
    norm = {'R3': {'TRUE': 'CONFIRMED_BROKEN'}, 'R5': {'confirmed': 'CONFIRMED', 'not_confirmed': 'NOT_CONFIRMED'}}.get(name[:2], {})
    T = pd.DataFrame([{'review_id': f'{name[:2]}-{i:03d}', **cols(it), **(extra(i) if extra else {}),
                       'llm_label_A': A[i].get('label'), 'llm_reason_A': A[i].get('reason', A[i].get('evidence')),
                       'llm_label_B': B[i].get('label'), 'llm_reason_B': B[i].get('reason', B[i].get('evidence')),
                       'llm_adjudicated': adj[i]['final'] if i in adj else '',
                       'final_label': norm.get(final[str(i)], final[str(i)])} for i, it in sorted(items.items())])
    T.to_csv(f'{MR}/{name}.csv', index=False)

# R1 missing path claims
S = load(f'{V}/sample_missing_paths.json'); heads = {}
for f in glob.glob(f'{I}/claim_histories/*.json'):
    j = json.load(open(f))
    if 'head' in j: heads[j['repo']] = j['head']
fileof = claims.groupby(['repo', 'doc', 'path']).file.first().to_dict()
B = {}
for f in sorted(glob.glob(f'{V}/llm_B_missing_paths_*.json')): B.update(load(f))
both('R1_missing_path_claims', S,
     lambda x: dict(document='context_file' if x['doc'] == 'ctx' else 'readme', language_group=x['lang_group'], repo=x['repo'],
                    claimed_path=x['claimed_path'], tree_root=x['tree_root'], context_text=x['context'],
                    file_at_snapshot=f"{gh(x['repo'])}/blob/{heads.get(x['repo'], 'HEAD')}/{fileof.get((x['repo'], x['doc'], x['claimed_path']), '')}",
                    repo_tree_at_snapshot=f"{gh(x['repo'])}/tree/{heads.get(x['repo'], 'HEAD')}"),
     load(f'{V}/llm_A_missing_paths.json'), B, load(f'{V}/adjudicated_missing_paths.json'), FL['paths'],
     extra=lambda i: {'history': S[i]['fate'].replace('rotted_unfixed', 'stale_unfixed')})
# R2 found path claims
S = load(f'{V}/sample_found_paths.json')
both('R2_found_path_claims', S,
     lambda x: dict(repo=x['repo'], context_file=x['context_file'], claimed_path=x['claimed_path'], tree_root=x['tree_root'], match_type=x['match_type'],
                    matched_paths=';'.join(x['matching_paths']), context_text=x['context'],
                    file_at_snapshot=f"{gh(x['repo'])}/blob/{x['head']}/{x['context_file']}", repo_tree_at_snapshot=f"{gh(x['repo'])}/tree/{x['head']}"),
     load(f'{V}/llm_A_found_paths.json'), load(f'{V}/llm_B_found_paths.json'), load(f'{V}/adjudicated_found_paths.json'), FL['found'])
# R3 rules broken when written (drop the one rule that is no longer broken after the checker fix)
S = {k: v for k, v in load(f'{V}/sample_broken_rules.json').items() if k != 49}
rid_of = {}
for i, x in S.items():
    rid_of[i] = [k for k, (j, r) in J.items() if r['repo'] == x['repo'] and r['text'] == x['rule_text'] and r['source'] == x['rule']['source']
                 and r['ti'] == x['rule']['ti'] and r['te'] == x['rule']['te']][0]
both('R3_rules_broken_when_written', S,
     lambda x: dict(repo=x['repo'], context_file=x['context_file'], rule_text=x['rule_text'], applies_to=';'.join(x['rule']['source']),
                    exempt=';'.join(x['rule']['exceptions']), forbidden_folders=';'.join(x['rule']['ti']), forbidden_packages=';'.join(x['rule']['te']),
                    breaking_imports_at_writing=x['violations_at_writing'], example_breaking_imports=' | '.join(x['examples_at_snapshot'])),
     load(f'{V}/llm_A_broken_rules.json'), load(f'{V}/llm_B_broken_rules.json'), load(f'{V}/adjudicated_broken_rules.json'), FL['rules'],
     extra=lambda i: {'rule_id': rid_of[i]})
# R4 rules that held
S = load(f'{V}/sample_held_rules.json')
both('R4_rules_that_held', S,
     lambda x: dict(repo=x['repo'], context_file=x['context_file'], rule_text=x['rule_text'], applies_to=';'.join(x['rule']['source']),
                    exempt=';'.join(x['rule']['exceptions']), forbidden_folders=';'.join(x['rule']['forbidden_internal']),
                    forbidden_packages=';'.join(x['rule']['forbidden_external']), polarity=x['rule']['polarity'],
                    code_at_snapshot=f"{gh(x['repo'])}/tree/{x['snapshot']}", context_file_link=f"{gh(x['repo'])}/blob/{x['snapshot']}/{x['context_file']}"),
     load(f'{V}/round2_llm_A_held_rules.json'), load(f'{V}/round2_llm_B_held_rules.json'), load(f'{V}/round2_adjudicated_held_rules.json'), FL['held'])
# R5 flagged commits (commit-rule pairs that are in the final exposed-commit set)
flag = set(C[C.viol].sha)
S = {k: v for k, v in load(f'{V}/sample_flagged_commits.json').items() if v['sha'] in flag}
cA = load(f'{V}/llm_A_flagged_commits.json'); cB = load(f'{V}/llm_B_flagged_commits.json')
for d in (cA, cB):
    for v in d.values(): v['label'] = f"{v['label']}|added={v.get('added_in_commit')}"
adj = load(f'{V}/adjudicated_flagged_commits.json')
for v in adj.values(): v['final'] = f"{v['final']}|added={v.get('added_in_commit')}"
both('R5_flagged_commits', S,
     lambda x: dict(repo=x['repo'], commit=x['sha'], commit_link=f"{gh(x['repo'])}/commit/{x['sha']}", rule_text=x['rule_text'],
                    applies_to=';'.join(x['rule']['source']), forbidden_folders=';'.join(x['rule']['ti']), forbidden_packages=';'.join(x['rule']['te']),
                    flagged_imports=' | '.join(x['flagged_imports'])),
     cA, cB, adj, {k: ('confirmed' if v else 'not_confirmed') for k, v in FL['commits'].items()})
# R6 unflagged commits
S = load(f'{V}/sample_unflagged_commits.json')
both('R6_unflagged_commits', S,
     lambda x: dict(repo=x['repo'], commit=x['sha'], commit_link=f"{gh(x['repo'])}/commit/{x['sha']}",
                    rules=' || '.join(r['rule_text'] for r in x['rules'])),
     load(f'{V}/llm_A_unflagged_commits.json'), load(f'{V}/llm_B_unflagged_commits.json'), {}, FL['unflagged'])
# R7 agent labels
S = load(f'{V}/sample_agent_labels.json'); grp = C.set_index('sha').who.to_dict()
def pr_link(x):
    ref = x['hint'].get('pull_request_branch_ref')
    return f"{gh(x['repo'])}/pull/{ref.split('/')[-1]}" if ref else ''
both('R7_agent_commit_labels', S,
     lambda x: dict(repo=x['repo'], commit=x['sha'], commit_link=f"{gh(x['repo'])}/commit/{x['sha']}", pull_request=pr_link(x),
                    merge_commit=f"{gh(x['repo'])}/commit/{x['hint']['merge_commit']}" if x['hint'].get('merge_commit') else ''),
     load(f'{V}/llm_A_agent_labels.json'), load(f'{V}/llm_B_agent_labels.json'), load(f'{V}/adjudicated_agent_labels.json'), FL['agentlabel'],
     extra=lambda i: {'detector_group': {'agent': 'agent_assisted', 'human': 'other'}[grp[S[i]['sha']]]})
print('done', {f: len(pd.read_csv(f'{MR}/{f}')) for f in sorted(os.listdir(MR)) if f.endswith('.csv')})
