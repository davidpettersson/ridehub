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
                                        v
                                  +-----------+
                                  | cancelled |
                                  +-----------+

      draft, announced, live, cancelled ------> archived
```

Any state can transition to `archived`. Nothing transitions out of `archived`: archival is
permanent and an archived event can never be restored.

### Available Transitions

| Transition   | Source States                        | Target State | Side Effects          | Guard Conditions                |
|--------------|--------------------------------------|--------------|-----------------------|---------------------------------|
| `live()`     | draft, announced                     | live         | None                  | None                            |
| `announce()` | draft, live                          | announced    | None                  | No confirmed registrations      |
| `draft()`    | announced, live                      | draft        | None                  | No confirmed registrations      |
| `cancel()`   | live                                 | cancelled    | Sets `cancelled_at`   | None                            |
| `archive()`  | draft, announced, live               | archived     | Sets `archived_at`    | No confirmed registrations      |
| `archive()`  | cancelled                            | archived     | Sets `archived_at`    | None                            |

An event that has confirmed registrations must be cancelled before it can be archived. Cancelling
notifies the registrants; archiving afterwards is unguarded because that notification already went out.

## Archival

Archival is a permanent administrative cleanup step, not a member-facing one:

- Archived events are excluded from public event listings and the calendar.
  `EventService.fetch_events` excludes them by default.
- The public event detail page for an archived event renders `web/events/archived.html`, a short
  message stating the event has been archived. The archival reason is never shown there.
- Archiving is irreversible. There is no transition out of `archived`.
- `archived_at` records when it happened; `archival_reason` records why. Both are read-only in the
  admin and only ever set through the Archive Event action.
- No email is sent when an event is archived.
- Archived events remain visible in the admin changelist and can still be duplicated. A duplicate of
  an archived event is created as a `draft` and carries over neither `archived_at` nor
  `archival_reason`.

## Admin Interface

The state field is:
- Displayed in the event list view
- Available as a filter
- Editable via a dropdown in the detail view
- State changes trigger FSM transitions with side effects and guard conditions
- Invalid transitions or guard failures show validation errors in the admin UI

`cancelled` and `archived` are not offered in the state dropdown. Both are reached only through
their respective changelist actions, which collect a reason and show a confirmation page first.
