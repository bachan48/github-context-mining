"""Step 1: select candidate context files from the Galster et al. dataset.

Keeps project-level context files that agents load by default, in engineered projects of any language,
with at least 20 lines, not empty and not just a pointer to another file.
Input : data/raw/context_files.csv, data/raw/repos.csv  (Zenodo 10.5281/zenodo.19375881)
Output: data/intermediate/context_file_candidates.csv
"""
import pandas as pd
FILES = ['AGENTS.md', 'CLAUDE.md', '.claude/CLAUDE.md', '.github/copilot-instructions.md', 'GEMINI.md', '.cursorrules']
c = pd.read_csv('data/raw/context_files.csv', low_memory=False)
r = pd.read_csv('data/raw/repos.csv', low_memory=False)
r = r[r.engineered_project.astype(str).str.lower() == 'true'][['repo_name', 'default_branch', 'scanned_at', 'engineered_project', 'mainLanguage', 'size',
                                     'commits', 'stargazers', 'contributors']]
c = c[c.context_file.isin(FILES) & (c.line_count >= 20) & (c.is_empty != True) & (c.is_reference != True)]
c = c.merge(r, on='repo_name', how='inner')
c.to_csv('data/intermediate/context_file_candidates.csv', index=False)
print(len(c), 'files in', c.repo_name.nunique(), 'projects')
