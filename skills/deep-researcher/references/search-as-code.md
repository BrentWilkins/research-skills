# Batched native tools

Optional on Hermes when `execute_code` and the required native tools are enabled.
Use the native tools directly on other hosts or when code execution is unavailable.
This changes how results reach context, not the research scope or budgets.

## Discovery

Within one `execute_code` call, call `hermes_tools.web_search(query, limit=8)`
for independently planned queries and retain only a compact shortlist for review.
The response contains `data.web` rows with `url`, `title`, and `description`.

- Count every query against the existing quick/standard/deep budgets (4/8/12),
  even when several queries share one code-execution call.
- Keep adaptive searches separate: the next query may depend on the last result.
  Use small batches (at most two queries), and honor the existing empty-result and
  no-new-credible-URL stop rules before scheduling more work.
- Deduplicate with the bundled ledger's `canonical_url` function. Preserve the
  original retrieval URL; canonical identity is for deduplication only.
- Keep all question associations for a URL found by several queries before
  deciding whether it was seen before. Multiple matching questions indicate
  relevance, not independent corroboration or source quality.
- Persist query outcomes, question associations, candidate metadata, and selected
  URLs in the run directory. Register the files with `research_run.py checkpoint`.
  A candidate omitted from a printed shortlist must remain recoverable from disk.
- Print a bounded shortlist, query failures, and newly found URL counts rather
  than entire tool responses. Snippets are discovery aids, never claim evidence.

Batching several tool calls in one model turn does not imply concurrent execution.
Do not add threads around native tool calls unless the host explicitly supports it.

## Extraction

Call `hermes_tools.web_extract(urls, char_limit=8000)` inside `execute_code`, with
at most three selected URLs per batch, preserving the skill's extraction budget.
The response contains `results` rows with `url`, `title`, `content`, and `error`.
Keep native retrieval responsible for network access; never replace it with raw
HTTP, a vendor SDK, or generated scraping code.

Cache retained text with stable line numbers and print relevant passages with
surrounding context and locators. Print failures and absence of relevant passages;
a keyword miss is not evidence that the source lacks an answer. Inspect more of
the native cache when needed, and record truncation and retrieval limitations.
Register retained cache files, and verify every decisive passage before synthesis.

## Recording

Record sources and claims through the bundled CLI in a single code or terminal
invocation when possible. Keep one ledger writer, run commands sequentially, and
stop on a nonzero exit status. Use an argument list rather than shell interpolation.
Confirm assigned source/evidence IDs from CLI output before recording claims;
never assume that IDs restart at 1 in a resumed run. Run `check` after the batch.
See the skill's command signatures for required flags and citation format.

These instructions do not add automatic subagent fan-out or raise collection
budgets. Lower context volume is an efficiency goal, not proof of faster execution
or better research. Compare equal-budget runs before making either claim.

Adapted from Teknium's search-as-code work in
[Hermes PR #105531](https://github.com/NousResearch/hermes-agent/pull/105531),
commit `c79582a54c`.
