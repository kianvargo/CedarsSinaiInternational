# Skills folder

Drop Claude skills here. Claude Code loads every skill in this folder automatically for anyone who
opens a session on this repository.

## How to add a skill

1. Download or unzip the skill. It is a **folder** containing a file named `SKILL.md`.
2. Put the whole folder in here, so it looks like this:
   ```
   .claude/skills/
     country-profile/      (already here)
       SKILL.md
     your-new-skill/
       SKILL.md
       (any other files that came with it)
   ```
   On GitHub: open this folder, click **Add file → Upload files**, drag the skill's folder in, then
   choose **Create a new branch and start a pull request** and merge it.
3. Start a new Claude Code session. The skill is picked up automatically.

## Check before adding

- **Read the skill's `SKILL.md` first.** Skills are instructions that Claude follows, and some include
  scripts that run on your behalf. Only add skills you understand and trust.
- **This repository is public.** Anything in this folder can be read by anyone.
- **Don't add skills meant for disallowed uses**, such as removing watermarks from photos you don't hold
  a license for, or getting around plagiarism or AI-detection checks.

## Skill file format

The top of every `SKILL.md` must look like this:

```markdown
---
name: my-skill
description: One sentence saying when Claude should use this skill.
---
# Instructions
...
```
