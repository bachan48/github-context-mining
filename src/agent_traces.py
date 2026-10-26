"""Layered detection of agent-assisted commits (v5).

Follows the trace heuristics of Robbes et al. (MSR 2026, labri-progress/agent-mining)
and the multi-method idea of Khosravani & Mockus (2026). Signals, from strongest to weakest:

  S1 dataset   : commit is in the Galster et al. list of AI co-authored commits
  S2 message   : agent co-author trailer, "Generated with ..." signature, agent session link
  S3 identity  : author or committer name/email is a coding-agent account
  S4 branch    : commit reached the main branch through a merge of a branch whose
                 name starts with an agent prefix (claude/, codex/, copilot/, cursor/, ...)
  S5 PR branch : commit is a squash/rebase of pull request #N, and a commit on the
                 PR's own branch (refs/pull/N/head) carries S2 or S3
  S6 same PR   : commit was merged together with (on the same merged branch as) a commit that
                 carries S1, S2 or S3; the whole pull request counts as agent-assisted

A commit is agent-assisted if any signal fires. Review-only bots (CodeRabbit, Sourcery,
DeepSource) and dependency/CI bots are not counted as coding agents.
"""
import csv, re, os, subprocess, json, sys, collections

P = os.path.join(os.path.dirname(__file__), 'agent_patterns')
REVIEW_ONLY = {'Coderabbit', 'Sourcery', 'Deepsource', 'Generic'}

ids = [r for r in csv.DictReader(open(f'{P}/authors.csv')) if r['tool'] not in REVIEW_ONLY]
EMAILS = {r['pattern'].lower(): r['tool'] for r in ids if '@' in r['pattern']}
NAMES = {r['pattern'].lower(): r['tool'] for r in ids if '@' not in r['pattern']}
# short names that are also common human words/names must match the whole name field
BRANCH_PREFIX = [r['pattern'].lower() for r in csv.DictReader(open(f'{P}/branches.csv'))
                 if r['tool'] not in REVIEW_ONLY]

BOT = re.compile(r"\[bot\]|dependabot|renovate|github-actions|pre-commit-ci|semantic-release|"
                 r"greenkeeper|allcontributors|weblate|crowdin|mergify|snyk|imgbot", re.I)
SIG = re.compile(
    r"generated with \[?claude|generated (with|by) (claude|copilot|cursor|codex|gemini|aider|devin|jules)|"
    r"\U0001F916 generated|^aider: |"
    r"chatgpt\.com/codex/tasks|app\.devin\.ai/sessions|jules\.google\.com|cursor\.com/(agents|background-agent)|"
    r"claude\.ai/code|claude-session:|devin run:|created by (cursor|copilot|codex|jules)", re.I | re.M)
COAUTH = re.compile(r"(?im)^\s*co-?authored-?by:\s*(.*?)\s*<([^>]+)>\s*$")
AGENT_BOT_ACCT = re.compile(r"copilot-swe-agent|devin-ai-integration|google-labs-jules|cursor\[bot\]|"
                            r"cursoragent|claude\[bot\]|openhands|codex\[bot\]|chatgpt-codex|factory-droid|"
                            r"sweep-ai|gemini-code-assist|gru-agent|roomote|jetbrains-junie", re.I)


def ident_hit(name, email):
    n, e = (name or '').strip().lower(), (email or '').strip().lower()
    if not n and not e:
        return None
    if AGENT_BOT_ACCT.search(n + ' ' + e):
        return 'account'
    for pat, tool in EMAILS.items():
        if pat == e or (pat.startswith('noreply@') and e == pat):
            return tool
    if e.endswith('@anthropic.com') and ('claude' in n or n in ('', 'anthropic')):
        return 'Claude Code'
    if re.match(r'claude[\s\d._\-(]|claude$', n) or e.endswith('@ai.assistant') or re.match(r'claude[\w.\-]*@', e):
        return 'Claude Code'
    for pat, tool in NAMES.items():
        if n == pat or n.startswith(pat + ' (') or n == pat + '[bot]':
            return tool
    return None


def message_hit(msg):
    if SIG.search(msg or ''):
        return 'signature'
    for n, e in COAUTH.findall(msg or ''):
        if ident_hit(n, e):
            return 'coauthor'
    return None


def branch_hit(branch):
    b = (branch or '').lower()
    b = b.split(':')[-1]
    if '/' in b:
        # "owner/claude/fix" from "Merge pull request #1 from owner/claude/fix": drop owner
        parts = b.split('/')
        cands = ['/'.join(parts[i:]) for i in range(len(parts))]
    else:
        cands = [b]
    return any(c.startswith(p) for c in cands for p in BRANCH_PREFIX)


MERGE_PR = re.compile(r"^Merge pull request #\d+ from (\S+)")
MERGE_BR = re.compile(r"^Merge (?:remote-tracking )?branch '([^']+)'")
SQUASH = re.compile(r"\(#(\d+)\)\s*$")


def G(d, *a, timeout=1800):
    return subprocess.run(['git', '-C', d, *a], capture_output=True, text=True, timeout=timeout, errors='ignore')


def read_commits(d, rev='HEAD', since=None):
    args = ['log', '--format=%H%x1f%P%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%ct%x1f%B%x1e', rev]
    if since:
        args.insert(1, f'--since={since}')
    out = G(d, *args).stdout
    C = {}
    for rec in out.split('\x1e'):
        p = rec.strip('\n').split('\x1f')
        if len(p) < 8:
            continue
        sha, par, an, ae, cn, ce, t, msg = p
        C[sha] = dict(par=par.split(), an=an, ae=ae, cn=cn, ce=ce, t=int(t), msg=msg)
    return C


def label_repo(d, aiset, head='HEAD', fetch_prs=True, since=None, window_start=None):
    """Return {sha: {'agent': bool, 'bot': bool, 'signals': [..]}} for commits reachable from head."""
    C = read_commits(d, head, since)
    lab = {}
    for sha, c in C.items():
        s = []
        if sha in aiset:
            s.append('S1')
        if message_hit(c['msg']):
            s.append('S2')
        if ident_hit(c['an'], c['ae']) or ident_hit(c['cn'], c['ce']):
            s.append('S3')
        bot = bool(BOT.search(c['an'] + ' ' + c['ae'])) and not s
        lab[sha] = dict(signals=s, bot=bot)
    # S4: merges of agent-prefixed branches
    for sha, c in C.items():
        if len(c['par']) < 2:
            continue
        subj = c['msg'].split('\n', 1)[0]
        m = MERGE_PR.match(subj) or MERGE_BR.match(subj)
        if not m or not branch_hit(m.group(1)):
            continue
        side = G(d, 'rev-list', c['par'][1], '--not', c['par'][0]).stdout.split()
        for s2 in side + [sha]:
            if s2 in lab and 'S4' not in lab[s2]['signals']:
                lab[s2]['signals'].append('S4')
    # S5: squash/rebase commits of PR #N whose PR branch carries an agent trace
    if fetch_prs and window_start:
        prs = collections.defaultdict(list)
        for sha, c in C.items():
            if len(c['par']) == 1:
                m = SQUASH.search(c['msg'].split('\n', 1)[0])
                if m:
                    prs[int(m.group(1))].append(sha)
        nums = sorted(prs)
        t_min = min(c['t'] for c in C.values())
        for i in range(0, len(nums), 200):
            chunk = nums[i:i + 200]
            # --shallow-since keeps the clone's existing boundary; --depth would cut the main line
            G(d, 'fetch', '-q', '--no-tags', '--filter=blob:none', f'--shallow-since={window_start}', 'origin',
              *[f'+refs/pull/{n}/head:refs/prs/{n}' for n in chunk], timeout=3600)
        for n in nums:
            ref = f'refs/prs/{n}'
            if G(d, 'rev-parse', '-q', '--verify', ref).returncode:
                continue
            base = C[prs[n][0]]['par'][0]
            # PR-branch commits: not on the main line and not older than our window.
            # (A shallow main line cannot hide old base commits, so the time filter removes them.)
            own = []
            for line in G(d, 'rev-list', '--max-count=100', '--format=%ct', ref, '--not', base).stdout.split('\n'):
                if line.startswith('commit '):
                    cur = line.split()[1]
                elif line.strip().isdigit() and cur not in C and int(line) >= t_min:
                    own.append(cur)
            hit = False
            for s in own:
                o = G(d, 'show', '-s', '--format=%an%x1f%ae%x1f%cn%x1f%ce%x1f%B', s).stdout.split('\x1f')
                if len(o) < 5:
                    continue
                an, ae, cn, ce, msg = o
                if message_hit(msg) or ident_hit(an, ae) or ident_hit(cn, ce):
                    hit = True
                    break
            if hit:
                for sha in prs[n]:
                    if 'S5' not in lab[sha]['signals']:
                        lab[sha]['signals'].append('S5')
    for v in lab.values():
        v['agent'] = bool(v['signals'])
        if v['agent']:
            v['bot'] = False
    return lab, C


def propagate_branches(d, lab, C):
    """S6: label every commit of a merged branch if one of its commits carries a direct trace."""
    for sha, c in C.items():
        if len(c['par']) < 2:
            continue
        side = [x for x in G(d, 'rev-list', c['par'][1], '--not', c['par'][0]).stdout.split() if x in lab]
        if any(set(lab[x]['signals']) & {'S1', 'S2', 'S3'} for x in side):
            for x in side + [sha]:
                if x in lab and 'S6' not in lab[x]['signals']:
                    lab[x]['signals'].append('S6')
                    lab[x]['agent'] = True
                    lab[x]['bot'] = False
    return lab


def first_parent_merges(d, C, head='HEAD'):
    """Merges on the main line (pull requests merged into the scanned branch), with their own commits."""
    out = []
    for sha in G(d, 'rev-list', '--first-parent', '--merges', head).stdout.split():
        c = C.get(sha)
        if not c or len(c['par']) < 2:
            continue
        side = [x for x in G(d, 'rev-list', c['par'][1], '--not', c['par'][0]).stdout.split()]
        if 0 < len(side) <= 200:          # very large sides are release or sync merges, not pull requests
            out.append((sha, c, side))
    return out


def branch_signals(d, lab, C, head='HEAD'):
    """S4 (agent branch name) and S6 (same pull request as a traced commit), main-line merges only."""
    for v in lab.values():
        v['signals'] = [s for s in v['signals'] if s not in ('S4', 'S6')]
    for sha, c, side in first_parent_merges(d, C, head):
        subj = c['msg'].split('\n', 1)[0]
        m = MERGE_PR.match(subj) or MERGE_BR.match(subj)
        members = [x for x in side + [sha] if x in lab]
        if m and branch_hit(m.group(1)):
            for x in members:
                lab[x]['signals'].append('S4')
        long_lived = m and re.search(r"(^|/)(main|master|dev|develop|development|release[\w./-]*|v\d[\w./-]*|stable|staging|next|trunk)$", m.group(1))
        if m and not long_lived and any(set(lab[x]['signals']) & {'S1', 'S2', 'S3'} for x in side if x in lab):
            for x in members:
                if 'S6' not in lab[x]['signals']:
                    lab[x]['signals'].append('S6')
    for v in lab.values():
        v['agent'] = bool(v['signals'])
        if v['agent']:
            v['bot'] = False
    return lab
