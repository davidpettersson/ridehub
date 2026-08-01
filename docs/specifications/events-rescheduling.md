# Events: Rescheduling

## Summary

Rescheduling of events happens in the admin. It is meant for the case where an event keeps its identity and its
registrations, but moves to a different time. A ride admin who has to push Sunday's ride out by a week because of
thunderstorms should not have to cancel the event and duplicate it, which would lose every registration and force
riders to sign up again.

Rescheduling is deliberately separate from editing the start time on the event change form: it records what the
schedule used to be, requires a reason, tells registrants, and shows a public notice.

## Rules

 - Only one event can be rescheduled at a time. Selecting several events and choosing the action is an error.
 - Only draft, announced and live events can be rescheduled. Cancelled and archived events cannot; the way back for
   those is duplication.
 - Rescheduling never changes the event state.
 - Rescheduling never changes registrations. Confirmed registrations stay confirmed, and no one is asked to
   re-confirm.
 - Only the latest reschedule is recorded. A second reschedule overwrites the previous start and end times with the
   ones the event carried immediately before it.
 - A duplicate of a rescheduled event never carries over any reschedule status.

## Integrity checks

The new schedule must satisfy all of the following:

 - The new start time must be in the future.
 - The new start time must differ from the current start time, to the minute.
 - The end time, when provided, must not be before the start time.
 - The registration close time, when provided, must not be after the start time.
 - The registration close time is required unless an external registration URL is provided.
 - An all-day event must have an end date.
 - A reason is required, and it may not be blank.

The last four rules are the ordinary event validation rules; rescheduling reuses them rather than restating them.

## User experience

Flow:

 - The ride admin uses the checkbox to select exactly one event and chooses the reschedule action.
 - A confirmation page is shown with the current schedule, and fields for the new start time, new end time, new
   registration close time, the reason, and a checkbox to notify registrants.
 - The new schedule fields are pre-filled with the event's current values.
 - The notification checkbox is checked by default.
 - When the administrator submits, the event is moved, the previous start and end times are recorded, and the
   reschedule is written to the audit log.
 - If the notification checkbox is checked, every confirmed registration receives an email stating the previous
   time, the new time, and the reason. Withdrawn registrations are never notified.

## Public visibility

 - The event page shows a notice with the date of the reschedule, the previous schedule, the new schedule, and the
   reason. The notice stays for the life of the event.
 - The event name is suffixed with `(rescheduled)` on the upcoming list, the event page, the registration pages and
   the registrations print view.
 - The profile page shows a `Rescheduled` badge on the registration row.
 - Cancellation takes precedence over rescheduling in the name suffix and the badge. A rescheduled event that is
   later cancelled reads as cancelled, while still showing the reschedule notice on the event page.
