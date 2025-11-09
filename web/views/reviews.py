import json
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from backoffice.services.reviews_service import ReviewsService


def review_2025(request: HttpRequest) -> HttpResponse:
    service = ReviewsService()
    stats = service.fetch_2025_statistics()

    monthly_labels = []
    monthly_events = []
    monthly_registrations = []
    for month_data in stats['monthly_data']:
        monthly_labels.append(month_data['month'].strftime('%B'))
        monthly_events.append(month_data['event_count'])
        monthly_registrations.append(month_data['registration_count'])

    top_routes_labels = []
    top_routes_counts = []
    top_routes_details = []
    for route in stats['top_routes']:
        route_name = route['ride__route__name'] or 'Unknown Route'
        top_routes_labels.append(route_name)
        top_routes_counts.append(route['registration_count'])
        top_routes_details.append({
            'name': route_name,
            'distance': route['ride__route__distance'] or 0,
            'elevation': route['ride__route__elevation_gain'] or 0,
            'registrations': route['registration_count']
        })

    programs_labels = []
    programs_counts = []
    for program in stats['events_by_program']:
        program_name = program['program__name'] or 'No Program'
        programs_labels.append(program_name)
        programs_counts.append(program['event_count'])

    context = {
        'stats': stats,
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_events': json.dumps(monthly_events),
        'monthly_registrations': json.dumps(monthly_registrations),
        'top_routes_labels': json.dumps(top_routes_labels),
        'top_routes_counts': json.dumps(top_routes_counts),
        'top_routes_details': json.dumps(top_routes_details),
        'programs_labels': json.dumps(programs_labels),
        'programs_counts': json.dumps(programs_counts),
    }

    return render(request, 'web/reviews/2025.html', context)
