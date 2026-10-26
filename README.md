# github-context-mining
Architectural claims (path claims and dependency rules) in AI agent context files, checked against the code and history of 3,346 open-source projects.

## Start here
```
pip install -r requirements.txt
jupyter notebook notebooks/
```
| notebook | content |
|---|---|
| `00_preprocessing.ipynb` | from the raw dataset to the clean tables; explains every pipeline step |
| `01_RQ1_accuracy.ipynb` | how accurate path claims and dependency rules are; Tables IVâ€“V, VII; Fig. 3 |
| `02_RQ2_staleness.ipynb` | how claims go stale and get fixed; Tables VIâ€“VII; Fig. 4 |
| `03_RQ3_rules_and_commits.ipynb` | rule status, agent-assisted vs. other commits, the Mantel-Haenszel test; Tables III, VIII; Fig. 5 |

The notebooks run in a few seconds from the cached data. Each writes its numbers to `results/rqN_numbers.json` and its figures to `results/figures/`.

## Folders
| folder | content |
|---|---|
| `notebooks/` | the four notebooks |
| `data/processed/` | clean tables, one row per project, file, claim, rule or commit (see `data/README.md`) |
| `data/intermediate/` | cached outputs of the pipeline |
| `manual_review/` | the samples used for the manual checks (R1â€“R7), their labels, and the codebook; see `manual_review/README.md` |
| `src/` | pipeline scripts, numbered in run order (`p00`â€“`p12`, `r01`â€“`r04`), and shared modules |
| `results/` | numbers and figures produced by the notebooks |

## Pipeline scripts (`src/`)
| script | step |
|---|---|
| `p00_select_candidates.py` | select candidate context files |
| `p01_fetch_context_files.py` | download files, READMEs, `.gitignore`, file trees |
| `p02_replay_claim_history.py` | clone projects, replay every file version, check claims (uses `claims_extractor.py`) |
| `p03_claim_outcomes.py` | git-ignore filter and history outcome per claim |
| `p04_find_rule_sentences.py` | candidate rule sentences (then LLM classification) |
| `p05_check_rules_and_commits.py` | import checker at writing, snapshot and per commit (uses `import_checker.py`) |
| `p06_detect_agent_commits.py`, `p07_add_branch_traces.py`, `p08_label_commit_groups.py` | agent-assisted commits (uses `agent_traces.py`, `agent_patterns/`) |
| `p09_context_file_creators.py` | agent trace on each context file's first commit |
| `p10_rule_and_commit_tables.py`, `p11_rule_attribution.py` | rule and commit tables, who wrote broken rules |
| `p12_export_clean_tables.py` | clean tables and review sheets |
| `r01`â€“`r04` | review samples, disagreements, merged labels and agreement |

Clones go to the folders named by the environment variables `CLONES` and `CLONES_FULL` (default `clones/`, `clones_full/`). Re-running the full pipeline needs `git`, network access and many hours.
