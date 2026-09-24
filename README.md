# CSI Country Profile Generator

Automates the research-heavy parts of building a Cedars-Sinai International
country profile, while keeping CSI's own internal/relationship data strictly
separate from anything an AI agent writes.

## Why it's split this way

Prior profiles (Kuwait, Qatar, Paraguay, Uzbekistan) mix two very different
kinds of content:

- **Public-record research**: demographics, government, economy, health
  system structure, financing, workforce stats, competitive landscape, recent
  news. This is well suited to agentic research — it's exactly what a web
  search + synthesis agent is good at, and it's the bulk of each document.
- **CSI-internal content**: patient volume/revenue by country, referral
  sources, relationship history, named contacts, and judgment calls (e.g.
  who to rekindle a relationship with). This must come from Cedars-Sinai's
  own data and a human's judgment — an agent has no way to know it and
  should never guess at it.

The pipeline below only automates the first kind, and forces the second kind
to stay as explicit, highlighted placeholders until a person fills them in.

## Pipeline

1. **Research pass** — an agent with web search gathers facts for the
   public-source sections, citing a source for every claim.
2. **Verification pass** — a *second, independent* agent re-checks each
   claim in the draft against its cited source and flags anything
   unsupported, contradicted, or stale. This is the guardrail against
   silent fact invention during the research agent's synthesis step.
3. **Assembly** — `scripts/generate_profile.py` renders the verified research
   into a `.docx` matching the existing profile format, with the CSI
   Assessment section left as highlighted `[MANUAL INPUT REQUIRED]`
   placeholders.
4. **Human fill-in** — an analyst completes the CSI Assessment section from
   internal data, and resolves/deletes the Fact-Verification Notes page.

See `.claude/skills/country-profile/SKILL.md` for the full step-by-step this
repo's Claude Code sessions follow, and `.claude/skills/country-profile/schema/profile.example.json`
for the data format the two passes produce and the generator consumes.

## Running it

Ask Claude Code (in this repo) to draft a country profile for `<country>` —
it will follow the skill. To run the generator manually once you have a
completed JSON file:

```
python3 scripts/generate_profile.py path/to/profile.json output/<Country>_Profile_DRAFT.docx
```
