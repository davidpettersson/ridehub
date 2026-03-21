---
name: changelog
description: Generate a user-facing changelog from git history since a given date
---

Generate a changelog for OBC RideHub by analyzing git history. The user provides a date as an argument (e.g., `/changelog 2026-02-01`). If no date is provided, ask the user for a date.

## Steps

1. Run `git log --oneline --no-merges --since="<date>"` to get all non-merge commits since the given date.

2. For each commit, run `git show --stat <hash>` and `git show <hash>` to understand what files changed and what the actual code changes were. Read commits in batches to understand the full picture.

3. Analyze ALL commits and produce a user-facing changelog. This requires judgment — you must understand what each commit actually does and translate it into language that end users (cycling club members, ride leaders, and ride administrators) would understand and care about.

4. Write the result to `CHANGES_SINCE_<date>.md` in the project root (e.g., `CHANGES_SINCE_2026-02-01.md`).

## Changelog format and rules

The changelog follows this exact structure:

```markdown
# OBC RideHub Change Log

Contact david.pettersson@ottawabicycleclub.ca if you have questions.

## Month Year

**For ride administrators:**

- Description of change. Explain what changed and why it matters to this audience.

**For ride leaders:**

- Description of change.

**For members:**

- Description of change.

**For everyone:**

- Description of change.

---
```

### Audience categories (use only the ones that apply)

Group changes by who they affect. Use these audience labels, combining them when a change affects multiple groups:

- **For ride administrators:** — changes to admin panel, event management, bulk operations, configuration
- **For ride administrators and ride leaders:** — changes that affect both groups
- **For ride leaders:** — changes to ride leader tools, participant info, communication features
- **For members:** / **For signed-in members:** — changes visible only to logged-in users (profile, registration history)
- **For everyone:** — public-facing changes (styling, calendar, event display, bug fixes visible to all)

### Grouping by time period

- If the date range spans multiple months, group changes under monthly headings (e.g., "## March 2026", "## February 2026") in reverse chronological order.
- If all changes fall within a single month, use just one heading.

### What to INCLUDE

- New features and capabilities
- Meaningful UI/UX improvements (styling, layout, navigation changes)
- Bug fixes that users would have noticed
- Changes to registration, events, calendar, profile, login workflows
- New admin tools or capabilities
- Accessibility improvements that affect user experience

### What to EXCLUDE (do not mention these at all)

- Internal refactoring, code cleanup, import optimization
- Test additions or changes
- CI/CD pipeline changes
- Dependency bumps or package updates
- Developer tooling changes (seeds, dev scripts, CLAUDE.md updates, cursor rules)
- Type hints, linting fixes
- Sentry/monitoring/logging configuration
- Robots.txt or SEO-only changes
- Changes to documentation files
- Commit message style changes

### Tone and writing style

- Write in plain, friendly language — no jargon
- Focus on the benefit to the user, not the implementation
- Use active voice: "Registration page now requires a phone number" not "A phone number requirement has been added to the registration page"
- Be specific about what changed and why it matters
- Keep bullet points to 1-3 sentences each
- Related commits should be merged into a single bullet point (e.g., multiple styling commits become one "Improved styling" entry)
- Do NOT use words like "refactored", "migrated", "template", "HTMX", "Bootstrap", "Django", or other technical terms
- Do NOT mention specific file names, CSS classes, or code constructs
- Bug fixes should describe the symptom that was fixed, not the technical cause

### Example entries (good)

- "Ride administrators now see the same registration information that ride leaders see. This allows administrators to view all registration details without being registered as leaders for the ride."
- "Fixed an issue where some events would incorrectly appear on the next day in the calendar."
- "Improved styling across event pages with better button appearance, more consistent program rendering, and enhanced upcoming events view."

### Example entries (bad — do NOT write like this)

- "Migrated login templates from Tailwind to Bootstrap" (too technical)
- "Added type hints to robots_txt view" (internal, nobody cares)
- "Fix django-prose-editor W001/W004 warnings" (purely technical)
- "Refactored announcement rendering from HTMX to server-side template tags" (implementation detail)
