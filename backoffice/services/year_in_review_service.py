from datetime import date
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from backoffice.models import Event, Registration, Route


class YearInReviewService:
    def fetch_2025_statistics(self) -> dict:
        year = 2025
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        events = Event.objects.filter(
            starts_at__date__gte=start_date,
            starts_at__date__lte=end_date,
            archived=False
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
            .order_by('-registration_count')[:5]
        )

        events_by_program = (
            events
            .values('program__name')
            .annotate(event_count=Count('id'))
            .order_by('-event_count')
        )

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

        return {
            'total_events': total_events,
            'total_registrations': total_registrations,
            'unique_participants': unique_participants,
            'total_distance': distance_data['total_distance'] or 0,
            'total_elevation': distance_data['total_elevation'] or 0,
            'top_routes': list(top_routes),
            'events_by_program': list(events_by_program),
            'monthly_data': list(monthly_data),
        }
