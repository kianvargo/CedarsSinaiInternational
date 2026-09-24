---
name: country-profile
description: Draft a Cedars-Sinai International country profile (public-data research, independently fact-checked) for a named country, leaving the CSI-specific section as clearly marked manual-input placeholders. Use when asked to build, draft, or update a country profile for a potential CSI collaborator country.
---

# Country Profile Generator

Produces the same structure as CSI's existing country profiles (Country Overview,
Health System, Recent Developments, CSI Assessment), but keeps two things
strictly separate:

- **Researched content** (demographics, government, economy, health system,
  competitive landscape, recent news) — gathered by an agent from public
  sources, with a citation on every claim, then independently fact-checked.
- **CSI-specific content** (patient volume/revenue, referral sources,
  relationship history, named internal/government contacts, recommendations)
  — never invented by the agent. Left as explicit placeholders for a human
  analyst to fill in from Cedars-Sinai's own data.

## Steps

Given a target country name (`$ARGUMENTS` or ask the user if not given):

1. **Research pass.** Spawn a research agent (Agent tool, general-purpose or
   Explore, with web search) with this brief: gather the following for
   `<country>`, each fact tagged with a source name/URL:
   - Demographics: capital, official language, population, area, GDP (PPP)
     total and per capita with world rank, government type, head of
     state/government, currency
   - Disease prevalence: top causes of death, top risk factors, NCD burden
   - Government structure (2-4 sentence narrative)
   - Economy (2-4 sentence narrative, note any national development/economic
     diversification plan)
   - Health system: public vs. private structure, financing (% GDP, per
     capita spend vs. regional/OECD benchmarks), workforce (physicians/nurses/
     beds per 1,000 vs. benchmarks), medical education pathway, healthcare
     outlook narrative
   - Competitive landscape: any known partnerships, MOUs, or collaborations
     between that country's health institutions and major US academic
     medical centers (Mayo, Cleveland Clinic, MSK, Johns Hopkins, MD
     Anderson, Houston Methodist, UCLA, NewYork-Presbyterian, UPMC, Mass
     General Brigham, Northwestern) or other foreign hospital systems
   - Recent developments: 3-5 recent (last 2 years) health-sector news items
     with dates
   Output as structured JSON matching `schema/profile.example.json` in this
   skill's directory. Every `facts` entry and `narrative` must have a
   `sources` list — no source, no claim.

2. **Verification pass.** Spawn a *second, independent* agent — do not give
   it the first agent's reasoning, only its JSON output plus fresh web
   access. Its only job: for each claim in the draft, check it against the
   cited source (or find one if missing) and flag anything that is
   unsupported, contradicted, stale (e.g., a "recent" figure that's actually
   old), or a claim the source doesn't actually make. This catches silent
   fabrication that the research agent might otherwise introduce during
   synthesis. Output a `verification_report.flagged_claims` list
   (`severity`, `claim`, `issue`).

3. **Resolve flags.** For anything flagged `high` severity, remove or correct
   the claim in the draft rather than shipping it with a footnote. Lower
   severity flags can ship as noted flags in the "Fact-Verification Notes"
   section for the human reviewer to resolve.

4. **Assemble.** Merge the verified research JSON with an empty
   `csi_manual` block (see schema) and run:
   ```
   python3 scripts/generate_profile.py <merged.json> output/<Country>_Profile_DRAFT.docx
   ```
   This renders public-source content as normal text with source lines, and
   renders every unfilled CSI field as a highlighted `[MANUAL INPUT
   REQUIRED]` placeholder — so nobody can mistake an empty field for "no
   opportunity" or mistake agent output for internal data.

5. **Hand off.** Tell the user which fields still need manual input (list
   them), and that the Fact-Verification Notes page should be reviewed and
   deleted once resolved.

## Do not

- Do not let the research or verification agent write anything into
  `csi_manual` — patient volumes, revenue, named internal contacts, and
  relationship/political judgment calls must come from a human with access
  to CSI's actual records.
- Do not present a flagged claim as fact in the final draft; downgrade to
  "reported by X, unconfirmed" or remove it.
- Do not fabricate a source. If the verification agent can't find a source
  for a claim, that's a flag, not a citation.
