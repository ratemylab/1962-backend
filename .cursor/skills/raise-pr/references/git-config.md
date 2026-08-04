# Git config for PR workflow

Store persistent values in **`CURSOR.md`** at the repo root (create the file if missing). Use this table:

| Key | Value |
|-----|-------|
| **Base branch** | Target branch for PRs (e.g. `main`, `develop`) |
| **Git user** | Author name for context (`git config user.name`) |
| **GitHub labels** | Comma-separated label names available in this repo |

## Resolving empty fields

1. **Base branch**
   - If empty: run `git rev-parse --verify develop`. If it succeeds, use `develop` and write it into `CURSOR.md`.
   - If `develop` does not exist: ask the user once for the base branch, then update `CURSOR.md`.

2. **Git user**
   - If empty: run `git config user.name`, then update `CURSOR.md`.

3. **GitHub labels**
   - If empty (and `gh` is available):  
     `gh label list --limit 50 --json name --jq '.[].name' | paste -sd, -`  
     Store the result as comma-separated names in `CURSOR.md`. If `gh` fails or the repo has no labels, leave empty and pick labels only from what the user provides or skip labels.

After first resolution, subsequent PRs read from `CURSOR.md` unless the user overrides the base branch for this run.
