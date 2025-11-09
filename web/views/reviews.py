import json
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from backoffice.services.reviews_service import ReviewsService


def review_2025(request: HttpRequest) -> HttpResponse:
    service = ReviewsService()
    stats = service.fetch_2025_statistics()

    monthly_labels = [month.strftime('%B') for month in stats['all_months']]

    programs = sorted(set(
        [item['program__name'] or 'No Program' for item in stats['monthly_events_by_program']] +
        [item['event__program__name'] or 'No Program' for item in stats['monthly_registrations_by_program']]
    ))

    events_by_program_monthly = {}
    for program in programs:
        events_by_program_monthly[program] = []
        for month in stats['all_months']:
            count = 0
            for item in stats['monthly_events_by_program']:
                if item['month'] == month and (item['program__name'] or 'No Program') == program:
                    count = item['event_count']
                    break
            events_by_program_monthly[program].append(count)

    registrations_by_program_monthly = {}
    for program in programs:
        registrations_by_program_monthly[program] = []
        for month in stats['all_months']:
            count = 0
            for item in stats['monthly_registrations_by_program']:
                if item['month'] == month and (item['event__program__name'] or 'No Program') == program:
                    count = item['registration_count']
                    break
            registrations_by_program_monthly[program].append(count)

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

    locations_data = []
    for location in stats['registrations_by_location']:
        locations_data.append({
            'location': location['event__location'],
            'registrations': location['registration_count']
        })

    context = {
        'stats': stats,
        'monthly_labels': json.dumps(monthly_labels),
        'programs': json.dumps(programs),
        'events_by_program_monthly': json.dumps(events_by_program_monthly),
        'registrations_by_program_monthly': json.dumps(registrations_by_program_monthly),
        'top_routes_labels': json.dumps(top_routes_labels),
        'top_routes_counts': json.dumps(top_routes_counts),
        'top_routes_details': json.dumps(top_routes_details),
        'programs_labels': json.dumps(programs_labels),
        'programs_counts': json.dumps(programs_counts),
        'locations_data': json.dumps(locations_data),
    }

    return render(request, 'web/reviews/2025.html', context)
