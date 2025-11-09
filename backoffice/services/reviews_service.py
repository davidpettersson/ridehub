from datetime import date
from django.db.models import Count, Q, Sum, Avg
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

        avg_participants = events.annotate(
            participant_count=Count('registration', filter=Q(registration__state=Registration.STATE_CONFIRMED))
        ).aggregate(avg=Avg('participant_count'))['avg'] or 0

        most_active_month_data = max(monthly_data, key=lambda x: x['registration_count'], default=None)
        most_active_month = most_active_month_data['month'].strftime('%B') if most_active_month_data else 'N/A'

        return {
            'total_events': total_events,
            'total_registrations': total_registrations,
            'unique_participants': unique_participants,
            'total_distance': distance_data['total_distance'] or 0,
            'total_elevation': distance_data['total_elevation'] or 0,
            'top_routes': list(top_routes),
            'events_by_program': list(events_by_program),
            'monthly_data': list(monthly_data),
            'total_ride_leaders': total_ride_leaders,
            'total_ride_leader_slots': total_ride_leader_slots,
            'dedicated_leaders': dedicated_leaders,
            'avg_participants': round(avg_participants, 1),
            'most_active_month': most_active_month,
        }
