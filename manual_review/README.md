# Manual checks

Every automatic step of the study was checked on a sample of its output (paper, Section III.G and Table IV). Each sheet holds one check.

| sheet | items | paper | what the check tells us |
|---|---|---|---|
| `R1_missing_path_claims.csv` | 300 | RQ1, Tables IV–V | how many missing path claims are real errors (precision) |
| `R2_found_path_claims.csv` | 100 | RQ1, Table IV | whether lenient matching accepts wrong claims |
| `R3_rules_broken_when_written.csv` | 51 | RQ1, RQ3, Fig. 5a | which rules were really broken on the day they were written |
| `R4_rules_that_held.csv` | 40 | RQ3, Table IV | whether the import checker misses breaks |
| `R5_flagged_commits.csv` | 35 pairs (30 commits) | RQ3, Fig. 5b | which flagged commits really added a break |
| `R6_unflagged_commits.csv` | 100 | RQ3, Table IV | whether the checker misses breaks in commits |
| `R7_agent_commit_labels.csv` | 150 | RQ3, Tables III–IV | whether agent-assisted labels are right |

## Columns
- The first columns describe the item, with links to the exact file, tree or commit on GitHub.
- `llm_label_A`, `llm_reason_A` and `llm_label_B`, `llm_reason_B`: two LLM labellers with different models and differently worded instructions, blind to each other.
- `llm_adjudicated`: a third pass, filled only where A and B disagreed.
- `final_label`: the label used in the analysis, reviewed by one author.

For R4, a first pilot round (`llm_A/B_held_rules.json`, 78% agreement) showed cases the codebook did not cover; after adding decision rules for them (see `codebook.md`), both labellers relabelled all 40 rules (`round2_*` files, 95% agreement), and the sheet shows this second round.

Label definitions are in `codebook.md`. The raw labeller outputs and the agreement between A and B are in `data/intermediate/review/` (`agreement.json`).
