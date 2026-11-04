# Editing a column

Each month's column arrives as a PR on `column/YYYY-MM`. The routine is described in `docs/column-routine.md`. The PR's first commit is the untouched draft. Thomas's edits and comments on that PR are what the routine learns from: the next run diffs the draft against what was merged, reads the comments and commit messages, and records lessons in `docs/editor-notes.md`.

## Edit in the browser

1. Open the column PR on GitHub, then **Files changed**.
2. On `site/articles/YYYY-MM.md`, click **⋯**, then **Edit file**.
3. Make the changes.
4. **Commit changes** to the `column/…` branch, with a commit message that says why ("too hedgy", "lead with the market, not HN").
5. Merge the PR when it reads right.

## Suggest without rewriting

Comment on a line in **Files changed**, or use the suggestion button to propose exact wording. Comments count as guidance. An edit with a reason is the strongest signal.

## Preview locally

1. `git fetch && git switch column/YYYY-MM`
2. `python3 -m http.server -d site 8000`
3. Open http://127.0.0.1:8000/?issue=YYYY-MM, then edit and refresh.

## How lessons build up

Each draft's PR lists "What I learned from your last edits", so a wrong lesson can be struck before merging. A lesson seen in two or three columns moves into `docs/style-guide.md`. Standing preferences can go straight into `docs/editor-notes.md`.

The loop only reads column PRs. A hand edit to an already published issue, such as October 2026, teaches nothing unless its reason is recorded in `docs/editor-notes.md`.
