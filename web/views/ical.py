from django.http import HttpResponse
from django.utils import timezone
from backoffice.models import Event

def generate_ical_feed(request):
    """Generate an iCal feed of all events."""
    events = Event.objects.all().order_by('starts_at')
    
    # Start building the iCalendar file
    ical_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RideHub//Event Calendar//EN",
        "X-WR-CALNAME:RideHub Events",
        "X-WR-CALDESC:All events from RideHub",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    
    for event in events:
        # Format dates to iCalendar format with proper timezone handling
        # Make sure the datetime is timezone aware
        starts_at = event.starts_at
        if starts_at.tzinfo is None:
            # If naive, assume it's in the current timezone
            starts_at = timezone.make_aware(starts_at)
        
        # Convert to UTC for iCalendar format
        starts_at_utc = starts_at.astimezone(timezone.utc)
        starts_at_str = starts_at_utc.strftime("%Y%m%dT%H%M%SZ")
        
        # Set all events to 1 hour duration
        ends_at = starts_at + timezone.timedelta(hours=1)
        
        # Convert end time to UTC
        ends_at_utc = ends_at.astimezone(timezone.utc)
        ends_at_str = ends_at_utc.strftime("%Y%m%dT%H%M%SZ")
        
        # Create a unique identifier for the event
        uid = f"{event.id}@ridehub"
        
        # Properly escape event name
        event_name = event.name.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
        
        # Build description
        description = event.description if hasattr(event, 'description') and event.description else ""
        
        # Properly escape description for iCalendar format
        description = description.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
        
        # Add status (cancelled or confirmed)
        status = "CANCELLED" if event.cancelled else "CONFIRMED"
        
        # Format location
        location = ""
        if event.location:
            location = event.location.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            if event.location_url:
                location += f" ({event.location_url})"
        
        # Current timestamp in UTC for DTSTAMP
        now_utc = timezone.now().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        
        # Build the event
        ical_event = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"SUMMARY:{event_name}",
            f"DTSTART:{starts_at_str}",
            f"DTEND:{ends_at_str}",
            f"DTSTAMP:{now_utc}",
            f"STATUS:{status}",
        ]
        
        # Add location if available
        if location:
            ical_event.append(f"LOCATION:{location}")
        
        # Add description if available
        if description:
            ical_event.append(f"DESCRIPTION:{description}")
        
        # Add URL if available
        if hasattr(event, 'location_url') and event.location_url:
            ical_event.append(f"URL:{event.location_url}")
        
        # Close the event
        ical_event.append("END:VEVENT")
        
        # Add this event to the calendar
        ical_content.extend(ical_event)
    
    # Close the calendar
    ical_content.append("END:VCALENDAR")
    
    # Join all lines and create the response
    response = HttpResponse("\r\n".join(ical_content), content_type="text/calendar")
    response["Content-Disposition"] = "attachment; filename=ridehub_events.ics"
    
    return response 