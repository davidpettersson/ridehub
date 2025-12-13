# Events: Duplication

## Summary

Duplication of events happens in the admin. It is meant to reduce the work burden for ride administrators that
frequently need to create either a new single or multiple events based off existing records. For instance,
one ride admin needs to duplicate his Thursday ride event to happen the next Thursday and only make minimal
changes to it. Other ride administrators need to duplicate a month's worth of events, for instance all Sunday
rides, and so they need more of a bulk editing functionality in combination with the duplication.

## Event data record duplication

Rules:

 - Duplication of an event creates a new event record.
 - All fields from the existing event are copied over to the new event, with exceptions:
   - A new event must never carry over any cancellation status.
   - A new event must never start as visible.
   - A new event must never carry over archived status.
   - A new event must never carry over legacy import fields.
 - Linked records may sometimes be deep copied, sometimes not.
   - Ride records must be duplicated.
     - Routes referenced from a ride must never be duplicated, but the ride should reference the same route.
     - Speed ranges referenced from a ride must never be duplicated, but the ride should be associated to the same ranges.
   - Registration records must never be duplicated.
   - Program records must never be duplicated.

## User experience

Flow:

 - The ride admin will use the checkboxes and select one or more events to duplicate in the admin
 - Once they select the duplicate action, a bulk edit view is shown.
 - For each ride selected for duplication, the administrator must have the option to:
   - Change the name of the event
   - Change the start time of the event
 - When the administrator presses save, the new events should be created as per the rules above, with the following side-effects:
   - Name should be changed to what was entered in the bulk edit view
   - Start time of the event should be updated to what was entered in the bulk view
   - End time should be calculated again: take the time delta from the old event and calculate duration, add that to the start time to get a new end time
   - Registration close time should be calculated again: take the time delta as for end time and do the calculation.
 - Once everything is saved, the ride administrator must be redirected to the event index view with a success message at the top

## Field copying rules

| Field | Action |
|-------|--------|
| name | Use form value |
| location, location_url, description | Copy from source |
| external_registration_url, registration_limit | Copy from source |
| virtual, ride_leaders_wanted | Copy from source |
| requires_emergency_contact, requires_membership | Copy from source |
| organizer_email | Copy from source |
| program | Same FK reference |
| starts_at | Use form value |
| ends_at | Recalculate: `new_starts_at + (ends_at - starts_at)` |
| registration_closes_at | Recalculate: `new_starts_at + (registration_closes_at - starts_at)` |
| visible | Set to `False` |
| cancelled, cancelled_at, cancellation_reason | Reset to defaults |
| archived, archived_at | Do not copy (use defaults) |
| legacy, legacy_event_id | Do not copy (use defaults) |

## Ride copying

Each ride is deep copied as a new `Ride` object with:
- Same `name`, `description`, `ordering` values
- Same `route` FK reference (not duplicated)
- Same `speed_ranges` M2M associations (not duplicated)
