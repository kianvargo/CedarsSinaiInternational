<!-- Template: copy to <scratchpad>/<country>/, then replace every {PLACEHOLDER}.
     {COUNTRY} = display name (e.g. Spain), {country} = file key (e.g. spain, new_zealand),
     {SCRATCH} = absolute scratch folder for this country, {DATE} = today (e.g. 29 October 2026). -->
# {COUNTRY} country profile: research brief

Read /home/user/CedarsSinaiInternational/.claude/skills/country-profile/SKILL.md fully and follow its
"Research pass" (step 1), citation rules, "Length and competitive landscape", "Short visual summary"
(chart rules), "House preferences" and "Writing style" sections exactly. Schema:
.claude/skills/country-profile/schema/profile.example.json; finished examples of the exact JSON shape:
output/new_zealand_profile.json and output/australia_profile.json (sources are objects; {{n}} markers refer to
that section's sources list). Today is {DATE}; research cutoff today.

Specifics:
- competitive_landscape: only "narrative" (~70 words: foreign health systems and hospital groups active in
  {COUNTRY}, general terms, with markers) and "closing" (~90 words: {COUNTRY} as a destination and source of
  international patients), plus "tracker_country": "{COUNTRY}". No "entries".
- Top-level "charts" list, three charts, per SKILL.md: "spending" (page health, kind line: current health
  expenditure % of GDP and out-of-pocket % of current health expenditure, annual ~2012 to latest, World
  Bank/WHO GHED; set "split": true because units differ), "workforce" (page health, kind bar: physicians
  per 1,000 for {COUNTRY} and at least 5 comparators {COMPARATORS}, plus the OECD or regional average; note
  differing years), "market" (page market: a line of at least 6 yearly points or a bar of at least 5
  values, e.g. hospital beds per 1,000 by year, or the largest private hospital groups {GROUPS} by
  hospitals or beds if reliably sourced). Every plotted value must come from the cited source.
- Start from the World Bank file: run `python3 /home/user/CedarsSinaiInternational/scripts/worldbank.py {ISO3} {COMPARATOR_ISO3S} --out {SCRATCH}/{country}_wb.json`
  first (or read it if it exists) and use it for World Bank facts and chart series instead of fetching them again.
- Money: add the US dollar equivalent in parentheses right after each local-currency amount, using
  `python3 /home/user/CedarsSinaiInternational/scripts/fx.py {CURRENCY} <value>` (rates in data/fx_rates.json).
- csi_manual: every field an empty string. recent_developments: 4 or 5 items from the last 2 years,
  each {"date","headline","summary","sources"}.
- Only cite pages you actually opened and read; if blocked, find another reputable readable source. Every
  sentence must match its source exactly (numbers, years, units). No Wikipedia.
Sources: {SOURCES: national statistics office, health ministry, central bank, finance ministry}, OECD,
World Bank, WHO, IMF, UN, peer-reviewed work, the institutions themselves, established news.
Web: WebSearch works; WebFetch is blocked, so read pages with
`python3 /home/user/CedarsSinaiInternational/scripts/fetch_text.py "<url>" -k <keywords>`.
Write the JSON to {country}_profile_draft.json in this folder.
