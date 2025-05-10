from django.http import HttpResponse, HttpRequest
from django.shortcuts import get_object_or_404

from backoffice.models import Ride


def event_ride_speed_ranges(request: HttpRequest, ride_id: int) -> HttpResponse:
    """HTMX endpoint to get speed ranges for a specific ride"""
    # Handle the case when no ride is selected (ride_id=0)
    if ride_id == 0:
        html = f'<select name="speed_range_preference" id="id_speed_range_preference" class="form-select" disabled>'
        html += '<option value="">Please select a ride first</option>'
        html += '</select>'
        return HttpResponse(html)

    ride = get_object_or_404(Ride, id=ride_id)
    speed_ranges = ride.speed_ranges.all()

    # Create a select element with the speed ranges
    html = f'<select name="speed_range_preference" id="id_speed_range_preference" class="form-select">'
    if not speed_ranges:
        html += '<option value="">No speed ranges available</option>'
    else:
        for speed_range in speed_ranges:
            html += f'<option value="{speed_range.id}">{speed_range}</option>'
    html += '</select>'

    return HttpResponse(html)
