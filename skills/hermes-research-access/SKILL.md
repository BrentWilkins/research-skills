---
name: hermes-research-access
description: Set up and use Hermes scholarly retrieval and a local browser with the research-access plugin. Use alongside deep-researcher for PubMed/PMC access, retrieval coverage, and browser fallback.
license: MIT
metadata:
  hermes:
    category: research
    tags: [research, web-extraction, browser]
---

# Hermes Research Access

## Setup

When asked to set up these capabilities, follow [setup details](references/setup.md): use
`hermes plugins install` for the executable runtime, then run the installed plugin's setup.
The plugin is distributed separately from this instruction skill so Hermes applies its
plugin-specific security checks. Dependency setup is explicit, locked, and backed up.

Loading this skill alone does not activate the plugin. If setup was not requested and the
plugin is absent, report that limitation and continue with available native tools. Start a
new Hermes session after setup so plugin discovery uses the new files and configuration.

## Research

- Use native `web_search` directly and sequentially. Do not emulate parallel search through
  a terminal, scrape search-engine HTML, or call SearXNG directly.
- Use native `web_extract` for PubMed, PMC, and DOI article URLs. The configured plugin
  routes supported scholarly URLs through free NCBI APIs before local Firecrawl. Preserve
  identifiers, canonical URL, retrieval method/time, and coverage in the evidence ledger.
- `abstract_only` establishes only what the abstract says. `full_text` describes retrieval
  coverage, not study quality or which sections the agent has read. Read relevant cached
  sections with the native file tool when the extraction response is truncated.
- A cookie wall, challenge, login page, or empty body is a failure even when HTTP says success.
  For an allowed site, use native `browser_navigate`, then `browser_snapshot`, in the same
  dedicated local research session. Use `browser_click` for ordinary consent, preferring
  necessary-only cookies, then inspect another snapshot. Do not bypass site-policy denials.
- Limit fallback to one browser attempt per failed URL and at most two consent interactions.
  If blocked, record the reason and seek a canonical/PDF version, official API, original
  study, repository copy, or another authoritative source. Never count an interstitial as evidence.
- Preserve the user's local-only, no-extra-model setup: no hosted retrieval, paid browser,
  auxiliary snapshot summarization, or `browser_vision`. If the configured snapshot tool would
  invoke an auxiliary model, stop that route and report the configuration mismatch. Do not
  assume a no-cost setting from this skill alone or silently change host configuration.
- Persistent cookies belong to the dedicated browser profile. Do not copy browser profiles,
  cookies, tokens, host configuration, or authentication state into evidence artifacts or archives.

The companion plugin runs locally. Browser persistence helps ordinary consent and JavaScript; it does not
guarantee access past subscription or challenge restrictions.
