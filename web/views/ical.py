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
        # Format dates to iCalendar format
        starts_at = event.starts_at.strftime("%Y%m%dT%H%M%SZ") if event.starts_at.tzinfo else event.starts_at.strftime("%Y%m%dT%H%M%S")
        
        # Determine end time (using registration_closes_at as fallback or add 1 hour if not available)
        if hasattr(event, 'registration_closes_at') and event.registration_closes_at:
            ends_at = event.registration_closes_at.strftime("%Y%m%dT%H%M%SZ") if event.registration_closes_at.tzinfo else event.registration_closes_at.strftime("%Y%m%dT%H%M%S")
        else:
            # Default to 1 hour later if no end time is available
            ends_at = (event.starts_at + timezone.timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ") if event.starts_at.tzinfo else (event.starts_at + timezone.timedelta(hours=1)).strftime("%Y%m%dT%H%M%S")
        
        # Create a unique identifier for the event
        uid = f"{event.id}@ridehub"
        
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
        
        # Build the event
        ical_event = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"SUMMARY:{event.name}",
            f"DTSTART:{starts_at}",
            f"DTEND:{ends_at}",
            f"DTSTAMP:{timezone.now().strftime('%Y%m%dT%H%M%SZ')}",
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