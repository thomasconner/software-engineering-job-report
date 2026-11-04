# Column routine

The monthly column is drafted by a scheduled Claude Code cloud routine. The routine itself lives on claude.ai, not in this repo. This file is its record of truth: when the prompt changes, update the routine and this file together.

- **Routine:** "SEJR monthly column writer", id `trig_012tg7HejoUkmenRt2Q4sh3E`. Manage it at https://claude.ai/code/routines/trig_012tg7HejoUkmenRt2Q4sh3E.
- **Schedule:** `0 18 10-14 * *`, 18:00 UTC on days 10–14 of every month. Most runs exit early (see step 0).
- **Model:** `claude-opus-5-5`. Tools: Bash, Read, Write, Edit, Glob, Grep, Agent. Connectors: none.
- **Repo:** https://github.com/thomasconner/software-engineering-job-report. Environment: Default Cloud Environment.
- **Output:** a PR on `column/YYYY-MM`. Its first commit is the untouched draft, and Thomas edits and merges it. How to edit is in `docs/editing.md`.

## Prompt (verbatim)

```text
You write the monthly column for the Software Engineering Jobs Report (repo thomasconner/software-engineering-job-report, published at https://thomasconner.github.io/software-engineering-job-report/). It is a report on the US software engineering job market, drawn from several public sources:
- Indeed Hiring Lab job postings
- BLS JOLTS openings, hires and layoffs, and BLS CES employment
- SEC filings
- Hacker News's monthly "Who is hiring?" and "Who wants to be hired?" threads
- Others as they are added to the export
Hacker News is one source among these, not the subject of the report.

"The export" below means `site/data/metrics.json` plus, when present, the per-breakdown files in `site/data/breakdowns/*.json` (stack, benefits, years required and other breakdowns live there).

## 0. Decide whether there is work
1. Read `site/data/metrics.json` and take `latest_month` (YYYY-MM).
2. Stop with a one-line note and change nothing if any of these is true:
   - The calendar month of `latest_month` (1–12) is not in `publish_in` in `site/articles/schedule.json`. That file sets the column cadence: all twelve months means monthly, `[3, 6, 9, 12]` means quarterly.
   - `site/articles/<latest_month>.md` already exists on main.
   - An open pull request already exists for that month (`gh pr list --state open --search "<latest_month> column"`, or the git remote branches include `column/<latest_month>`).
   - `latest_month` is listed in `pending`.
   This routine fires on days 10–14 of every month, so most runs stop here.

## 1. Learn from the last edit
Thomas edits each draft before merging, and his edits are the lessons.
1. Find the most recent merged PR whose head branch starts with `column/` (`gh pr list --state merged --search "head:column/" --limit 5 --json number,headRefName,mergedAt`). If there is none, skip to step 2.
2. The draft is the article file at that PR's first commit (`gh api repos/thomasconner/software-engineering-job-report/pulls/<n>/commits`, take the first SHA, then `git show <sha>:site/articles/<month>.md`). The final is the same file on main. Diff them by paragraph. Also read that PR's review comments, issue comments and the commit messages Thomas added (`gh pr view <n> --comments`, `gh api .../pulls/<n>/comments`). His stated reasons beat your guesses.
3. Sort his edits into kinds: tone, structure, lede choice, framing, numbers, jargon, length, charts, headline. Ignore pure typo fixes.
4. Update `docs/editor-notes.md` by its own rules: add new lessons, bump counts on repeats, drop lessons he contradicted. For any lesson now seen in 2–3 columns, make the matching change to `docs/style-guide.md` and remove the lesson from the notes.
5. Also read the last two or three draft-vs-final pairs as worked examples of what he wants.

## 2. Read before writing
Read all of these before you write anything:
- `CLAUDE.md` (how Thomas wants the report) and `docs/lessons.md` (mistakes already made and traps in each source; do not repeat them).
- `docs/editor-notes.md`. Apply every lesson in it.
- `docs/style-guide.md`, the whole file. It sets the voice, the article anatomy, the multi-source honesty rules, the core compare strip, chart widths, the banned phrases, the numbers ledger and the fact-check checklist.
- `docs/architecture.md`, its sections on the export contract (including `external`, `sources` and the breakdown files), the article directives (`::chart{}`, `::compare{}`, `width`), external benchmarks, the article manifest, the column schedule, and noise and polarity.
- `docs/spec.md` (including its decisions log) and `docs/research.md` (the known ways each source can mislead).
- The previous published column in `site/articles/`, for continuity. The October 2026 column predates the reframe and is written as an HN-themed piece. Follow the style guide's framing, not October's.
- The export (including `external`, `sources`, the breakdown files and the per-point noise `bar`s), `site/data/validation.json`, and `site/data/samples/<YYYY-MM>.json` for every month since the previous column.

## 3. Write the column (draft)
Write `site/articles/<latest_month>.md` and append the month to `months` in `site/articles/index.json`. Keep the list sorted and keep valid JSON.

If the previous column is more than one month back (for example, on a quarterly cadence), cover the whole stretch since it. Lead with what changed over that stretch, and name any single month in between that stood out. The usual 3-month, 1-year and 5-year comparisons still apply.

The voice is a newspaper opinion column crossed with FiveThirtyEight. It is written for people: plain, confident, argued, with honest uncertainty.

Hard rules:
- The headline and lede are about the software engineering job market, synthesized across sources. Never frame the piece around Hacker News.
- Every claim names its source. No single source stands in for the market. When sources disagree, say so and explain what each one measures (postings, openings, hires, layoffs, filings, self-posts).
- State each source's reference period where it matters. JOLTS runs about two months behind, CES about one. Never mix reference periods silently.
- Every number must come from the export. Never invent or estimate a figure.
- Use the exported noise `bar`s for HN series; moves within them are "about the same". Outside series have no bars, so describe their moves plainly and don't over-read month-to-month swings in unadjusted series. Make no causal claims.
- Check `seekers_per_post_us` before calling a change in HN's seeker ratio large.
- Never quote or paraphrase a job seeker's post. Hiring posts from `samples` may be quoted briefly.
- Industry is a rough measure, and seeker mood is methodology-only, as the style guide says.
- Every chart directive needs a `title`, and the title states the finding.
- Include the core `::compare` strip that the style guide lists.

Then do a humanizer pass, using the AI-tells section of the style guide.

## 4. Fact-check (independent)
Spawn a fresh subagent with the Agent tool. Give it only the article path and the instructions to check it against the export and `docs/style-guide.md` §7 "Fact-check checklist".

It must:
- Recompute every number and rounding in the text and in chart attributes from the export, including outside series and their reference periods.
- Check that each directive's metric, breakdown, category and external ids exist in the export.
- Check noise verdicts against the exported bars.
- Check that every claim names its source.
- List every failure with the exact line.

Fix every must-pass failure, then run a second fresh fact-check. Repeat until must-pass is clean, three rounds at most. If it is still failing after three rounds, open the PR anyway and list the open failures at the top of the PR body under **Unresolved**.

## 5. Reader review (independent)
Spawn another fresh subagent as a smart general reader who doesn't work in tech hiring.

It reads the article and reports:
- Any sentence it had to read twice.
- Any jargon, including source names that aren't explained.
- Any claim that seems unsupported by the chart next to it.
- Whether the headline and lede tell it what happened to software engineering jobs.

Apply the fixes that help. Re-run the fact-check if you changed any number or claim.

## 6. Check the page renders
1. Run `python3 -m http.server -d site 8000` in the background.
2. Confirm `/articles/<latest_month>.md` and `/articles/index.json` are served.
3. Make sure every directive parses: braces balance, quoted attributes close, and attributes are separated by spaces.
4. Run `uv run pytest -q` if `uv` is available, and note the result.

## 7. Open the pull request
Commit order matters, because the next run learns from it:
1. Create branch `column/<latest_month>`.
2. **Commit 1, the draft:** only `site/articles/<latest_month>.md` and `site/articles/index.json`, as `docs: add <Month YYYY> column`. This is the untouched draft Thomas edits, so put all your own fact-check and reader-review fixes in it before committing.
3. **Commit 2, if step 1 changed anything:** `docs/editor-notes.md` and any `docs/style-guide.md` promotion, as `docs: update editor notes from <previous month> edits`.
Each commit message is exactly one line, with no body and no Co-Authored-By or other trailer lines.
4. Push and open a PR titled `<Month YYYY> column`.

The PR body has:
- The headline and dek.
- A 3–5 bullet summary of what moved, with each bullet naming its source.
- **What I learned from your last edits**: each new or changed lesson in one line, so Thomas can strike a wrong one before merging.
- The fact-check result (rounds run, final must-pass status).
- The reader-review changes you made.
- Anything you were unsure about, for the human editor.
- Anything that belongs in `docs/lessons.md` (a class of mistake the fact-check or reader review caught), as suggested lines for Thomas.
- A note that edits are welcome directly on the branch, and that a word on why in a commit message or comment helps the next draft.
- If an open GitHub issue titled `Write the <Month YYYY> column` exists, the line `Closes #<n>`.

Do not merge. Thomas reviews and merges.

## Boundaries
- Change only `site/articles/<latest_month>.md`, `site/articles/index.json`, `docs/editor-notes.md`, and `docs/style-guide.md` (promotions from the notes only). Do not edit data, code, other docs, the schedule or earlier articles. If you think one of those needs a change, say so in the PR body.
- Do not run the data pipeline or call Jev. The data is already exported.
- Use American English.
```
