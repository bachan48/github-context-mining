# Codebook for the manual checks

The labels used in each sheet of `manual_review/`. General rules for all sheets:
- Judge what the **author of the context file meant**, using the surrounding text and the repository at the linked commit.
- Production code only. Tests, examples, demo folders, scripts and vendored code do not count as breaking a rule.
- Type-only imports (`import type`, `TYPE_CHECKING`, Go types used only in signatures) do not count.
- `UNCLEAR` is used when an item cannot be decided.

## R1 · Missing path claims (300)
The checker could not find the path in the repository at the snapshot. Is it a real documentation error?

| label | use when |
|---|---|
| `WRONG_PATH` | The text presents the path as an existing part of **this** repository, and it is not there (renamed or moved counts). |
| `NOT_REPO_PATH` | Not meant as a path in this repository: the user's own project, another repo or machine, a URL piece, a package/module name, an API route, a command argument. Also use it if the file does exist (e.g. via a symlink or a missing extension). |
| `PLACEHOLDER_OR_EXAMPLE` | An example, template or placeholder path. |
| `GENERATED_OR_IGNORED` | Created by a build, install, test run or at runtime, so not expected in git. |
| `PARSE_ERROR` | The extractor cut or joined the string wrongly. |
`WRONG_PATH` is used only when the text clearly claims the path exists.

## R2 · Found path claims (100)
The checker accepted the path, either exactly from the root (`match_type = exact`) or as the end of a longer path (`suffix`).

| label | use when |
|---|---|
| `CORRECT` | The location the text means exists (a suffix match is fine if it is clearly the place meant). |
| `WRONG_MATCH` | What the text describes does not exist; the match is an unrelated path with the same name. |
| `UNCLEAR` | Cannot decide. |

## R3 · Rules broken when written (51)
The checker found imports that break the rule at the commit where the rule was written. `example_breaking_imports` shows some of them.

| label | use when |
|---|---|
| `CONFIRMED_BROKEN` | The code really breaks the rule as its author meant it, including exceptions stated in the file or in lint configs. |
| `FALSE_MAPPING` | The structured rule (`applies_to`, `exempt`, `forbidden_*`) does not match what the sentence means, or a stated exception applies. |
| `FALSE_RESOLUTION` | The import was resolved to the wrong folder or package. |
| `UNCLEAR` | Cannot decide. |

## R4 · Rules that held (40)
The checker found no breaking import at the snapshot; the labeller searched the code independently.

| label | use when |
|---|---|
| `HOLDS` | No production-code import breaks the rule. |
| `MISSED_VIOLATION` | At least one production-code import breaks it. |
| `BAD_MAPPING` | The structured rule clearly does not express the sentence, so the check could not work. If there is also a real violation, use `MISSED_VIOLATION`. |
| `UNCLEAR` | Cannot decide. |
Decision rules: dependencies declared only in build files (`pom.xml`, `package.json`, `Cargo.toml`) do **not** count; dynamic loading (`import_module`, runtime plugin loading, subprocess calls) does **not** count; maintenance scripts count as scripts and do **not** count.

## R5 · Commits flagged as adding a break (35 commit-rule pairs, 30 commits)
Judged from the added lines of the files in `flagged_imports`.

| label | use when |
|---|---|
| `CONFIRMED` | This commit itself adds an import that breaks the rule as meant. |
| `NOT_ADDED_IN_COMMIT` | The import breaks the rule, but this commit only moved, renamed or reformatted it, or the commit is the first commit of the clone. |
| `FALSE_MAPPING` | The structured rule does not match the sentence, or an exception applies. |
| `FALSE_RESOLUTION` | The import was resolved to the wrong target. |
| `UNCLEAR` | Cannot decide. |

## R6 · Exposed commits that were not flagged (100)
Did the commit add a rule-breaking import the checker missed?

| label | use when |
|---|---|
| `NO_BREAK` | No added import breaks the rules. |
| `MISSED_BREAK` | It adds one. |
| `UNCLEAR` | Cannot decide. |

## R7 · Agent-assisted labels (150)
Is there a visible trace that an AI coding agent took part in this commit or in its own pull request?

| label | use when |
|---|---|
| `AGENT` | An agent account as author or committer, an agent co-author trailer, a "Generated with ..." line or agent session link in the commit or in its pull request's own commits, or a branch named after an agent (`claude/`, `codex/`, `copilot/`, `cursor/`, ...). |
| `NO_EVIDENCE` | No such trace. |
| `UNCLEAR` | Ambiguous, e.g. a person whose name is Claude, or a generic "AI" note. |
Decision rules: traces in **other** pull requests that were merged together in one large release merge do not count; traces in older base-branch history do not count. Copilot Autofix trailers and a project's own "[AI]" title convention count as `AGENT`.
