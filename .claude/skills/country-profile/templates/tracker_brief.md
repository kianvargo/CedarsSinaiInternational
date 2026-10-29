<!-- Template: copy to <scratchpad>/<country>/, then replace every {PLACEHOLDER}.
     {COUNTRY} = display name (e.g. Spain), {country} = file key (e.g. spain, new_zealand),
     {SCRATCH} = absolute scratch folder for this country, {DATE} = today (e.g. 29 October 2026). -->
# {COUNTRY} partnerships tracker: research brief

Find partnerships between FOREIGN health systems and institutions in {COUNTRY}, per step 5b of
/home/user/CedarsSinaiInternational/.claude/skills/country-profile/SKILL.md. Today is {DATE}.
Status rule: Active = dated evidence of activity (including a signing) on or after October 2024; Unclear =
latest evidence 2021 to September 2024; Ended = ended 2021 or later; nothing older. The foreign party must
be a hospital, health system or university (not a government, investor, drug or device company); foreign
groups that own or operate hospitals in {COUNTRY} count as "Ownership or management". The partnership must be
WITH an institution in {COUNTRY} (a {COUNTRY} institution working abroad is out of scope). Exclude referral
offices, one-off events, individual-faculty ties.

Search widely (at least 25 searches): each named system with "{COUNTRY}" / "España"; each {COUNTRY} partner with
"partnership", "MoU", "acuerdo", "colaboración", "convenio". Check e.g. {CHECKLIST: major hospitals and research centres, universities, private hospital groups and any
foreign owners or operators in {COUNTRY}}. Care-network memberships (e.g. Mayo Clinic Care Network) count as clinical
affiliations. Confirm on the institution's own newsroom or press release wherever possible.
{country}_tracker_brief.json in this folder lists known leads (may be empty).

Web: WebSearch works; WebFetch is blocked, so read pages with
`python3 /home/user/CedarsSinaiInternational/scripts/fetch_text.py "<url>" -k <keywords>`.
Output {"relationships":[...], "excluded":[...leads left out and why]}. Each record:
{"foreign_institution","foreign_country","group":"US academic medical centers"|"Other foreign health systems",
 "indian_partner":"the {COUNTRY} partner (field name is historical)","partner_city","type": one of
 "Clinical affiliation","Advisory and consulting","Training and education","Research collaboration",
 "Telehealth and second opinion","Government agreement","Ownership or management",
 "description":"one or two plain sentences, no dashes","status","start","end","last_evidence":"YYYY-MM",
 "evidence","sources":[{"author","title","publisher","date","url"}]}
