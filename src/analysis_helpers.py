"""Small helpers shared by the four notebooks.

Every notebook starts with `from analysis_helpers import *`, which
- moves to the package root, so all paths below work,
- loads the clean tables in data/processed/,
- gives `review_labels(...)`, which reads one manual-check sheet from manual_review/.
"""
import os, sys, json
if os.path.basename(os.getcwd()) == 'notebooks':
    os.chdir('..')
sys.path.insert(0, 'src')
import numpy as np, pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from statsmodels.stats.proportion import proportion_confint

PROC, REVIEW, RESULTS, FIGS = 'data/processed', 'manual_review', 'results', 'results/figures'
os.makedirs(FIGS, exist_ok=True)
plt.rcParams.update({'font.size': 8, 'font.family': 'serif', 'axes.spines.top': False, 'axes.spines.right': False, 'pdf.fonttype': 42})
pd.set_option('display.max_colwidth', 80)
FIG_W = 3.45  # IEEE column width in inches


def load(name, **kw):
    """Load data/processed/<name>.csv."""
    return pd.read_csv(f'{PROC}/{name}.csv', low_memory=False, **kw)


def wilson(k, n):
    """95% Wilson interval for k successes out of n."""
    lo, hi = proportion_confint(k, n, method='wilson')
    return lo, hi


def pct(x, d=1):
    return f'{100 * x:.{d}f}%'


def review_labels(check):
    """One manual-check sheet, e.g. review_labels('R1_missing_path_claims').

    Each row is a sampled item. `final_label` is the label used in the analysis: the label both LLM labellers
    agreed on, or the adjudicated label where they disagreed, after review by one author.
    """
    T = pd.read_csv(f'{REVIEW}/{check}.csv')
    T['label'] = T.final_label
    print(f'{check}: {len(T)} items')
    return T


def save_numbers(name, d):
    """Write the numbers a notebook reports to results/<name>.json."""
    json.dump(d, open(f'{RESULTS}/{name}.json', 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
