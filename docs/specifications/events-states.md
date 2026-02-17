# Event State Machine

This document describes the event lifecycle state machine. The `state` field is the single source of truth for event visibility, cancellation, and archival status.

## States

The Event model has five possible states, defined as class constants (e.g., `Event.STATE_LIVE`):

| State       | Description                                    | Visibility | Registration |
|-------------|------------------------------------------------|------------|--------------|
| `draft`     | Event is being prepared                        | Admin-only | Closed       |
| `announced` | Event is visible but not open for registration | Public     | Closed       |
| `live`      | Event is live and accepting registrations      | Public     | Open         |
| `cancelled` | Event has been cancelled                       | Public     | Closed       |
| `archived`  | Event has been removed/deleted                 | Admin-only | Closed       |

## Computed Properties

The model provides computed properties derived from `state`:

| Property    | True when state is                          |
|-------------|---------------------------------------------|
| `visible`   | `announced`, `live`, `cancelled`            |
| `cancelled` | `cancelled`                                 |
| `archived`  | `archived`                                  |

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

| Transition   | Source States    | Target State | Side Effects          | Guard Conditions                |
|--------------|-----------------|--------------|-----------------------|---------------------------------|
| `live()`     | draft, announced | live         | None                  | None                            |
| `announce()` | draft, live      | announced    | None                  | No confirmed registrations*     |
| `draft()`    | announced, live  | draft        | None                  | No confirmed registrations*     |
| `cancel()`   | live             | cancelled    | Sets `cancelled_at`   | None                            |
| `archive()`  | live, cancelled  | archived     | Sets `archived_at`    | No confirmed registrations*     |

*Guard only applies when transitioning from `live` state. Transitioning from other source states (e.g., `cancelled` to `archived`) is always allowed.

## Admin Interface

The state field is:
- Displayed in the event list view
- Available as a filter
- Editable via a dropdown in the detail view
- State changes trigger FSM transitions with side effects and guard conditions
- Invalid transitions or guard failures show validation errors in the admin UI
