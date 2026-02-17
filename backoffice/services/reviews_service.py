from datetime import date
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from backoffice.models import Event, Registration, Route


class ReviewsService:
    def fetch_2025_statistics(self) -> dict:
        year = 2025
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        events = Event.objects.filter(
            starts_at__date__gte=start_date,
            starts_at__date__lte=end_date,
        ).exclude(
            state=Event.STATE_ARCHIVED
        )

        confirmed_registrations = Registration.objects.filter(
            event__starts_at__date__gte=start_date,
            event__starts_at__date__lte=end_date,
            state=Registration.STATE_CONFIRMED
        )

        total_events = events.count()
        total_registrations = confirmed_registrations.count()

        unique_participants = confirmed_registrations.values('user').distinct().count()

        distance_data = confirmed_registrations.filter(
            ride__route__isnull=False
        ).aggregate(
            total_distance=Sum('ride__route__distance'),
            total_elevation=Sum('ride__route__elevation_gain')
        )

        top_routes = (
            confirmed_registrations
            .filter(ride__route__isnull=False)
            .values('ride__route__id', 'ride__route__name', 'ride__route__distance', 'ride__route__elevation_gain')
            .annotate(registration_count=Count('id'))
            .order_by('-registration_count')[:20]
        )

        registrations_by_location = (
            confirmed_registrations
            .exclude(event__location='')
            .values('event__location')
            .annotate(registration_count=Count('id'))
            .order_by('-registration_count')
        )

        events_by_program = (
            events
            .values('program__name')
            .annotate(event_count=Count('id'))
            .order_by('-event_count')
        )

        monthly_events_by_program = (
            events
            .annotate(month=TruncMonth('starts_at'))
            .values('month', 'program__name')
            .annotate(event_count=Count('id'))
            .order_by('month', 'program__name')
        )

        monthly_registrations_by_program = (
            confirmed_registrations
            .annotate(month=TruncMonth('event__starts_at'))
            .values('month', 'event__program__name')
            .annotate(registration_count=Count('id'))
            .order_by('month', 'event__program__name')
        )

        all_months = events.annotate(month=TruncMonth('starts_at')).values_list('month', flat=True).distinct().order_by('month')

        monthly_data = (
            events
            .annotate(month=TruncMonth('starts_at'))
            .values('month')
            .annotate(
                event_count=Count('id'),
                registration_count=Count('registration', filter=Q(registration__state=Registration.STATE_CONFIRMED))
            )
            .order_by('month')
        )

        ride_leader_registrations = confirmed_registrations.filter(
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )

        total_ride_leaders = ride_leader_registrations.values('user').distinct().count()
        total_ride_leader_slots = ride_leader_registrations.count()

        dedicated_leaders = (
            ride_leader_registrations
            .values('user')
            .annotate(times_led=Count('id'))
            .filter(times_led__gte=5)
            .count()
        )

        return {
            'total_events': total_events,
            'total_registrations': total_registrations,
            'unique_participants': unique_participants,
            'total_distance': distance_data['total_distance'] or 0,
            'total_elevation': distance_data['total_elevation'] or 0,
            'top_routes': list(top_routes),
            'registrations_by_location': list(registrations_by_location),
            'events_by_program': list(events_by_program),
            'monthly_data': list(monthly_data),
            'monthly_events_by_program': list(monthly_events_by_program),
            'monthly_registrations_by_program': list(monthly_registrations_by_program),
            'all_months': list(all_months),
            'total_ride_leaders': total_ride_leaders,
            'total_ride_leader_slots': total_ride_leader_slots,
            'dedicated_leaders': dedicated_leaders,
        }
