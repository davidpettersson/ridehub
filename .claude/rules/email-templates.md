---
paths:
  - web/templates/email/**
---

# Email Template Guidelines

- Every HTML email template has a corresponding .txt version
- Edit the HTML version first, then update the adjacent .txt file
- HTML templates extend `email/_base_email.html` using blocks: `title`, `content`, `footer`, `extra_css`
- Build all URLs with `{{ base_url }}{% url 'name' %}` — never use relative URLs
- When adding a hyperlink, add a test in `web/tests/templates/test_email_templates.py` using the `assert_all_links_absolute` helper from `BaseEmailTestCase`
