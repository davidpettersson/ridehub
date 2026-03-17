---
paths:
  - web/templates/**
  - web/static/**
---

# Frontend & Styling Guidelines

- Bootstrap 5.3.2 is the primary CSS framework; new pages extend `web/_base_bootstrap.html`
- Tailwind remains only in login pages (`_base.html`); do not introduce Tailwind elsewhere
- All custom CSS goes in `web/static/web/styling.css`; rich-text prose styles are in `prose-styling.css`
- OBC brand colors are defined as CSS custom properties at the top of `styling.css`
- Use Bootstrap responsive classes (`d-none d-md-*`, `col-12 col-md-6`) for mobile-first layout
- Alpine.js and HTMX are available for interactivity
