# Data

## `raw/` (not included)
Download `repos.csv`, `context_files.csv` and `commits.csv` from the Galster et al. dataset, Zenodo 10.5281/zenodo.19375881, into this folder. Only needed to re-run step 1.

## `processed/`: the clean tables the notebooks use
| file | one row per | key columns |
|---|---|---|
| `projects.csv` | candidate project (3,909) | `main_language`, `stars`, `contributors`, `commits`, `history_cloned`, `in_sample` |
| `context_files.csv` | candidate context file (4,372) | `file`, `lines`, `created_at`, `first_commit_has_agent_trace`, `n_versions`, `n_path_claims`, `in_sample` |
| `path_claims.csv` | path claim in a context file or README, over its history (49,388) | `document`, `path`, `form`, `in_structure_section`, `valid_when_written`, `in_file_at_snapshot`, `found_at_snapshot`, `written_at`, `path_removed_at`, `removed_from_file_at`, `history_outcome` |
| `rule_candidate_sentences.csv` | candidate rule sentence (1,645) | `sentence`, `category` (LLM), `checkable` |
| `dependency_rules.csv` | checkable rule (184) | `rule_text`, `rule_type`, `polarity`, `applies_to`, `exempt`, `forbidden_folders`, `forbidden_packages`, `breaking_imports_at_writing`, `breaking_imports_at_snapshot`, `status`, `review_label`, `link` |
| `rule_attribution.csv` | rule broken when written (51) | `rule_written_by`, `lines_older_than_window`, `lines_added_by_agent_assisted`, `lines_added_by_other` |
| `exposed_commits.csv` | exposed commit (7,480) | `group`, `trace_message`, `trace_agent_account`, `trace_pull_request`, `trace_codes`, `flagged_break`, `confirmed_break`, `repair`, `github` |
| `commit_rule_pairs.csv` | exposed commit × rule | `rule_id`, `flagged_break`, `repair` |

Lists inside a cell are separated by `;`. Times are UTC. `history_outcome` is one of `still_valid`, `stale_fixed`, `stale_unfixed`, `deleted_while_valid`, `never_valid`, `never_valid_deleted`, `became_valid`.

## `intermediate/`: cached pipeline outputs
Produced by the scripts in `src/` (see `notebooks/00_preprocessing.ipynb`). Large download caches (`fetched_files/`, `file_trees/`, `gitignore/`, about 200 MB) are not included and are rebuilt by `src/p01_fetch_context_files.py`.
| path | from |
|---|---|
| `context_file_candidates.csv` | `p00` |
| `claim_histories/`, `claim_histories.pkl` | `p02`, `p03` |
| `rule_classification/` | `p04` + LLM (inputs and outputs per batch, merged in `all_rule_sentences.json`) |
| `rule_checks/` | `p05` (per project: rules, imports at writing and snapshot, per-commit breaks) |
| `agent_traces/` | `p06`, `p07` (per project: trace codes per commit) |
| `commit_groups_raw.csv`, `commit_rule_pairs_raw.csv` | `p08` |
| `context_file_creators.csv` | `p09` |
| `rule_status_raw.csv`, `rule_status.csv`, `commit_groups.csv` | `p10` |
| `rule_attribution.csv` | `p11` |
| `review/` | `r01`–`r04`: samples (`sample_*`), LLM labels (`llm_A_*`, `llm_B_*`), `disagreements_*`, `adjudicated_*`, `final_labels.json`, `agreement.json` |
