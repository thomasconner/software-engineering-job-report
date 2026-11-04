# Labeling rubric (reference set for validating an automated classifier)

Label ONLY from what the post text says. Do not use outside knowledge of the company (its later fate, size, funding) and do not guess from the company name. When the text is genuinely ambiguous, pick the best label AND set "unsure": true for that field.

## Hiring posts ("Who is hiring?")
- work_mode: remote | hybrid | onsite | unclear. Answer for most of the engineering roles. A city with no remote mention = onsite. Occasional/ad-hoc WFH or "remote possible as an exception" = onsite. hybrid needs a stated recurring in-office cadence or the word hybrid. "Onsite or remote, your choice" / "REMOTE OK" = remote. unclear only if the post gives no location or work arrangement at all.
- seniority: junior | mid | senior | staff_plus | unspecified. The modal (most common) level among the individual-contributor engineering roles. Management roles excluded. "All levels" or no level stated = unspecified. "Senior" in title or 5+ years = senior; staff/principal/architect = staff_plus; new grad/intern/entry/junior = junior; 2–4 years or plain "Software Engineer" with stated mid-level expectations = mid.
- industry: ai_ml | devtools_infra | fintech | health | climate_energy | security | commerce | media_consumer | enterprise_saas | hardware_robotics | other | unstated. What the company sells/builds. other = the post says what it does but none fit (edtech, adtech, real estate, govtech, staffing agencies, consultancies, nonprofits, research labs...). unstated = the post doesn't say what the company does.
- funding_stage: bootstrapped | seed | series_a | series_b | series_c_plus | public_or_large | venture_unspecified | unknown. seed only with an explicitly named pre-seed/seed/angel round. An accelerator batch tag alone (e.g. "(YC W12)") = unknown. Investors or amounts named but no round letter = venture_unspecified. "Profitable, no outside funding" = bootstrapped. Public company or explicitly large established company = public_or_large.
- ai_native: 1 if the post describes its product as built on AI/ML (LLMs, machine learning models, computer vision, etc. at the core of the product); generic "data-driven"/analytics = 0.
- new_grad: 1 if the post says it welcomes new grads, juniors, entry-level, or interns; else 0.
- eng_leadership: 1 if the post hires engineering managers, team leads, heads of engineering, or CTO; else 0.

## Seeking posts ("Who wants to be hired?")
- seeker_mood: 0 discouraged (long fruitless search, desperation, "anything at all"), 1 strained (says the search is hard/slow, worried, open to big compromises), 2 neutral (a standard pitch, nothing said about how the search is going — a confident pitch is still 2), 3 positive (says things are going fine, selective, casually looking), 4 upbeat (multiple offers, very choosy, clearly in demand). A career gap or life circumstance by itself is not mood.

## Output
One JSON object per line: {"post_id": ..., "labels": {field: value, ...}, "unsure": [fields], "note": "optional short reason for any unsure field"}.

## Clarifications (2026-11-04, after the first validation run)
- Founding or first engineer with no stated level = unspecified.
- Adtech = other. Gambling and betting exchanges = other.
- Consumer fitness/wellness products = media_consumer; health = healthcare, medical, biotech, health insurance.
- mid = 2–4 years.
- An accelerator batch tag alone = unknown funding. No outside knowledge of company size ("part of Cisco" alone = unknown).
- Posts that aren't job posts (or are in the wrong thread) get `"exclude": true`.
- seeker_mood 3 includes "employed and selective / casually looking"; 4 needs multiple offers or being clearly in demand.
