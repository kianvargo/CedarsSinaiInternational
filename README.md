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

## Partnerships tracker

`data/partnerships.json` lists foreign health systems' partnerships in each
profiled country that are Active (dated evidence from the last 24 months),
Ended (within five years) or Unclear, each with sources. It comes from its own
research run (three research agents, three independent verifiers, a
resolution pass). `python3 scripts/tracker.py export` writes
`output/Partnerships_Tracker.xlsx`; `python3 scripts/make_partner_map.py India
output/India_partnerships_map.png` draws the city map. The profile's
competitive landscape and the summary read from this file, so they cannot
drift apart.

## Country explorer

`python3 scripts/build_explorer.py` writes `explorer/index.html`, an interactive world map: hover or search a country to lift it out of the map and open its profile in the side panel. Countries with a profile in `output/` are shaded red; any other country shows the prompt to build one. Re-run the script after each new profile. The page layout lives in `scripts/explorer_template.html`. Each brief's Word, Excel, map and zip files are offered for download in the side panel. claude.ai only hosts web file types, so the script also writes base64 text copies to `explorer/files/` (not committed) and lists them in `explorer/publish_files.json`. Pass that list as the `files` map when republishing the artifact.

CSI's own earlier profiles (with patient and revenue figures) go in `private/csi_profiles/` with an `archive.json` index. That folder is ignored by git because this repository is public. When it exists, the script also writes `explorer/index_full.html` (also ignored), which adds those countries to the map in a separate color with their original files; publish that file, not `index.html`, to the private artifact.
