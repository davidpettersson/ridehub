---
paths:
  - "**/tests/**"
---

# Testing Guidelines

- Use Django `TestCase` for all tests
- Follow arrange-act-assert with explicit `# Arrange`, `# Act`, `# Assert` comments
- Create test data with `Model.objects.create()` in `setUp()` — no factory libraries
- Use base test classes with shared `setUp()` and `_create_*` helpers for common setup
- Name methods `test_<descriptive_phrase>`, classes `<Feature>TestCase` or `<Feature>Tests`
- Organize tests by layer: `models/`, `services/`, `views/`, `templates/`
- Tests must be independent and runnable in any order
