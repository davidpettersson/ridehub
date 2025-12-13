# Duplication of events

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
