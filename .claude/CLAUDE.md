# RideHub

Django web application for managing cycling events, deployed to Heroku.

## Architecture
- All models and business logic belong in the `backoffice` application
- Use service classes for business logic, not fat models
- Services organized by domain (events, registrations, users, etc.)
- Keep models lightweight and focused on data structure
- Always create model validations to ensure data integrity
- If the correct validation approach is unclear, ask the user

## Code Style
- No comments in code
- No docstrings
- Keep code self-documenting through clear naming
- No badges in UI templates

## Git
- Branch names: `<YYYYMMDD>-<description>`, e.g. `20260317-branch-naming-skill`

## Development Environment
- Development is on Windows; production is Linux on Heroku
- Always use `uv` to run commands
- Run tests: `uv run python manage.py test`

## Frontend
- Mobile-first responsive design for all pages
- Bootstrap CSS with global stylesheet at `web/static/web/styling.css`
- Migrating from Tailwind to Bootstrap; let them co-exist during transition
