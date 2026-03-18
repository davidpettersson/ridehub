---
name: seed
description: Seed the development database with sample events, rides, speed ranges, users, and registrations
disable-model-invocation: true
---

Run the seed command to populate the development database with test data:

```bash
uv run python manage.py seedevents
```

This creates:
- 5 cycling programs (Road, MTB, Gravel, Social, Training)
- 8 routes (20-100 km)
- 4 speed ranges (20-25, 25-30, 30-35, 35+ km/h)
- 26 test users with phone numbers
- 7 events (one per day for the next week) with rides, speed ranges, and 5-15 confirmed registrations each

The command is idempotent — re-running skips existing events.
