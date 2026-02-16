# Event State Machine

This document describes the event lifecycle state machine introduced in Step 1 of the event states implementation.

## States

The Event model has five possible states, defined as class constants (e.g., `Event.STATE_LIVE`):

| State | Description | Visibility | Registration |
|-------|-------------|------------|--------------|
| `draft` | Event is being prepared | Admin-only | Closed |
| `announced` | Event is visible but not open for registration | Public | Closed |
| `live` | Event is live and accepting registrations | Public | Open |
| `cancelled` | Event has been cancelled | Public | Closed |
| `archived` | Event has been removed/deleted | Admin-only | Closed |

## State Transitions

```
                    +-----------+
                    |   draft   |
                    +-----+-----+
                          |
            +-------------+-------------+
            |                           |
            v                           v
      +-----------+               +-----------+
      | announced |<------------->|   live    |
      +-----------+               +-----+-----+
                                        |
                          +-------------+-------------+
                          |                           |
                          v                           v
                    +-----------+               +-----------+
                    | cancelled |-------------->|  archived |
                    +-----------+               +-----------+
```

### Available Transitions

| Transition | Source States | Target State | Side Effects |
|------------|---------------|--------------|--------------|
| `live()` | draft, announced | live | Sets `visible=True` |
| `announce()` | draft, live | announced | Sets `visible=True` |
| `draft()` | announced, live | draft | Sets `visible=False` |
| `cancel()` | live | cancelled | Sets `cancelled=True`, `cancelled_at` |
| `archive()` | open, cancelled | archived | Sets `archived=True`, `archived_at` |

## Legacy Boolean Field Mapping

The state field shadows existing boolean fields for backwards compatibility:

| State | `visible` | `cancelled` | `archived` |
|-------|-----------|-------------|------------|
| draft | False | False | False |
| announced | True/False | False | False |
| live | True | False | False |
| cancelled | True | True | False |
| archived | False | False | True |

## Data Migration

Existing events were migrated to states based on their boolean fields:

1. `archived=True` -> state='archived'
2. `cancelled=True` -> state='cancelled'
3. `visible=True` -> state='live'
4. `visible=False` -> state='draft'

## Admin Interface

The state field is:
- Displayed in the event list view
- Available as a filter
- Shown as read-only in the detail view
- Modified only through admin actions (Cancel Event, Archive Event)

## Future Steps

Steps 2-4 of the implementation will:
- Add guard conditions for transitions (e.g., no registrations for draft/announced)
- Migrate UI to use state instead of boolean fields
- Eventually deprecate the boolean fields
