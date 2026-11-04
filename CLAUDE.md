# Software Engineering Jobs Report

A monthly report on the US software engineering job market, published at https://thomasconner.github.io/software-engineering-job-report/. Hacker News is one data source among several: Indeed Hiring Lab, BLS JOLTS and CES, SEC filings, company job boards, and more as they land. Owner: Thomas. Tracker: Linear project P-CON-53 (Conner Technology team).

## Read before working

Read these first, in this order. They hold the context this repo builds on, so don't re-ask what they answer.

1. `docs/spec.md`: goals, point-in-time rules, and the **Decisions log**. The log is the record of what was decided and why.
2. `docs/lessons.md`: mistakes already made, approaches already tried and rejected, and traps in each source. Check it before proposing something that sounds new.
3. `docs/architecture.md`: the layout, schema, export contract and article directives.
4. `docs/style-guide.md`: how the column reads. `docs/editor-notes.md` holds what Thomas changed in past drafts.
5. `docs/research.md`: the known ways each source can mislead, and the sources considered, both used and rejected.
6. `docs/sessions/`: one note per working session, recording what Thomas asked for and what was decided.
7. `docs/column-routine.md`: the scheduled routine that drafts each column, with its verbatim prompt. Keep it in sync with the routine on claude.ai. `docs/editing.md` covers how Thomas edits a column PR.

## How Thomas wants the report

- It is about the software engineering job market, written as a newspaper opinion column crossed with FiveThirtyEight: for people, argued, plain, honest about uncertainty, with interactive charts.
- Trends over time, compared against 3 months, 1 year and 5 years ago.
- Every month is computed as it looked then, with no hindsight, including outside data (values as first published).
- Every claim names its source. No single source stands in for the market. When sources disagree, the column says so.
- It covers what employers ask for: stack, databases, DevOps tools, benefits, experience, and how posts change. A UK vs US view is planned.

## How work runs here

- **Delegation:** the lead session delegates to agents (Opus) and runs independent work in parallel, each agent in its own git worktree under `.claude/worktrees/<branch>`.
- **Review loop, every time:**
  1. An agent implements on a branch.
  2. A fresh agent reviews the diff adversarially. It gets the code, not the author's conclusions, and checks numbers against the data. Where labels matter, it draws its own sample.
  3. The author fixes the findings.
  4. The same reviewer re-reviews until nothing serious is left.
  5. The lead opens a PR and runs the full test suite. Thomas merges; auto mode blocks agent merges to main. Small doc and data commits go straight to main.
- **Learning loop:** after each review, any finding that reveals a class of mistake goes into `docs/lessons.md` in the same PR. Agents read it before starting.
- **Column loop:** the routine's draft is the first commit of each `column/YYYY-MM` PR. Thomas edits it and merges. The next run reads the gap between draft and merge, plus his reasons, and records it in `docs/editor-notes.md`.
- **Decisions:** any decision made in conversation lands in the `docs/spec.md` Decisions log, or in the relevant doc, in the same session.
- **Tracking:** the Linear project is updated as work happens, with an end-of-day project update.
- **Asking Thomas:** one question at a time, with a proposed default. Steps he must do himself come as numbered single actions. Secrets and GitHub settings are his to set; agent sessions are blocked from writing secrets.

## Commands

`uv run sejr <step>` (fetch, normalize, features, classify, aggregate, ats, external, sec, export, validate, unanswered); `uv run pytest -q`; `uv run ruff check`. Jev needs `uv run --env-file .env` (`TYPESAFE_API_KEY`). The SEC needs `SEC_USER_AGENT`. Never print or commit `.env`. Actions secrets: `TYPESAFE_API_KEY` and `SEC_USER_AGENT`, plus optional `BLS_API_KEY`. Only Thomas can set them.

## Conventions

- Commits: one-line conventional commits, with no body and no trailers.
- American English throughout.
- Tests never sleep.
- Seeker (job-seeker) post text is never exported, quoted or paraphrased.
- Job-board snapshots store tags and titles, never descriptions.
