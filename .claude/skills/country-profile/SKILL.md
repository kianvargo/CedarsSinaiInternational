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

**Hand off between agents through files, not chat.** Each agent writes its
output with the Write tool to the session scratchpad (e.g.
`<scratchpad>/<country>_research.json`, `<country>_verify_1.json` through
`_verify_3.json`) and returns only a short summary. Later agents read those
files directly. The resolution agent writes the final merged JSON straight
to `output/<country>_profile.json` in the exact schema the generator expects.
Never retype an agent's JSON by hand: that copy step is itself a place for
errors to slip in, and it burns tokens twice.

**Primary sources need network access.** The cloud environment must have
full network access, or search agents only see search-result snippets and
the primary-source check below can't really happen. Test first with
`curl -s -o /dev/null -w "%{http_code}" https://data.worldbank.org`. If the
WebFetch tool is blocked, have agents open pages with
`python3 scripts/fetch_text.py <URL> -k <keywords>`, which prints only the
lines that match (cheap on tokens). Some hospital sites (Mayo Clinic, Johns
Hopkins) refuse automated requests; use their press releases as republished
on PR Newswire, Business Wire or EurekAlert instead.

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

2. **Verification pass — three independent agents in parallel, not one.**
   Spawn three separate verification agents at the same time (single message,
   multiple Agent calls). None of them sees the others' output or reasoning —
   each gets only the research draft and fresh web access, and re-derives its
   own findings from scratch. This costs roughly 3x a single verifier's
   tokens, but a single verifier missing something (as happened on both the
   Vietnam and China runs) is exactly the failure mode this guards against:
   independent agents checking the same claim rarely make the identical
   mistake for the identical reason.

   For any claim naming a specific institution's partnership, relationship,
   or status (the highest reputational-risk category — this is where the
   China run's errors were), each verifier must check that institution's own
   primary source (its newsroom, press releases, official site) rather than
   accepting a secondary news article or aggregator's summary as sufficient.
   A claim like "no partnership exists" or "this joint venture ended"
   specifically requires a primary-source check before it can be marked
   confirmed — these are exactly the claims that turned out wrong in prior
   runs.

   Each verifier outputs the same flagged-claims format as before (severity,
   claim, issue). Take the three outputs and apply a consensus rule: a claim
   is only "confirmed accurate as drafted" if none of the three verifiers
   flagged it. If even one verifier flags a claim, or the three verifiers
   disagree with each other about what the correct claim should be, it goes
   to the resolution pass below, same as a single-verifier flag would have.

3. **Resolution pass — do this before touching the draft.** A flag from any
   of the three verifiers (or a disagreement between them) is not a
   correction. Two things can be flagged and they need different handling:
   - *Outright wrong* (no source supports it, or the source says something
     different): just fix it — replace the claim with what the source
     actually says.
   - *Genuinely contended* (multiple credible sources disagree, or a figure
     depends on methodology/date): spawn a third agent whose only job is to
     adjudicate that specific point with targeted follow-up search — find
     the most authoritative/current source, understand *why* the sources
     disagree (different year, different methodology, different agency),
     and decide what the profile should say. The output of this pass is not
     a note — it's the actual replacement sentence or figure, written as
     something a human analyst would write (e.g. "Vietnam's economy was
     valued at approximately $1.46 trillion (PPP) in 2024, per the CIA World
     Factbook; a commonly cited $2.03 trillion figure elsewhere uses IMF
     projection methodology for a later year and isn't a same-year
     comparison" folded into one flowing sentence — not a bracketed caveat).
   Only if a point truly cannot be resolved (rare) does a brief, naturally
   worded caveat stay in the sentence itself — never as a separate flagged
   list or appendix.

4. **Merge directly into the draft.** Apply every correction and resolution
   in place, in the actual section/paragraph it belongs to. There is no
   separate "verification notes" page in the final document — corrections
   are invisible seams, not visible footnotes. Keep an internal record (a
   local file, not part of the docx) of what was changed and why, in case
   the human reviewer wants to see it, but the document itself should read
   as a single confident, coherent draft.

5. **Assemble.** Merge the corrected research JSON with an empty
   `csi_manual` block (see schema) and run:
   ```
   python3 scripts/generate_profile.py <merged.json> output/<Country>_Profile_DRAFT.docx
   ```
   This renders public-source content as normal prose with source lines, and
   renders every unfilled CSI field as a highlighted `[MANUAL INPUT
   REQUIRED]` placeholder — so nobody can mistake an empty field for "no
   opportunity" or mistake agent output for internal data.

6. **Hand off.** Tell the user which CSI fields still need manual input, and
   summarize (in chat, not in the document) what the resolution pass changed
   and why, so they can spot-check the calls that were made on their behalf.

## Writing style

- Avoid em/en dashes; write in full sentences with normal punctuation
  (commas, periods, "which," "because," parentheses) the way a human analyst
  would.
- Narrative paragraphs should be substantive — aim for real depth (context,
  mechanism, implication), not a compressed bullet-to-prose conversion.
  Err toward more detail rather than a clipped summary sentence.
- Write corrections and resolved ambiguities as natural prose within the
  relevant paragraph, not as bracketed disclaimers or "Note:" asides.

## Do not

- Do not let the research or verification agent write anything into
  `csi_manual` — patient volumes, revenue, named internal contacts, and
  relationship/political judgment calls must come from a human with access
  to CSI's actual records.
- Do not present a flagged claim as fact in the final draft; downgrade to
  "reported by X, unconfirmed" or remove it.
- Do not fabricate a source. If the verification agent can't find a source
  for a claim, that's a flag, not a citation.
