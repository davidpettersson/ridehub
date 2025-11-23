import logging
from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db.models import QuerySet, Subquery, OuterRef
from django.utils import timezone

from backoffice.models import Event, Registration, SpeedRange, Ride
from backoffice.services.email_service import EmailService
from backoffice.services.request_service import RequestDetail
from backoffice.services.user_service import UserService, UserDetail
from ridehub import settings

logger = logging.getLogger(__name__)


@dataclass
class RegistrationDetail:
    ride: Ride | None
    ride_leader_preference: str | None
    speed_range_preference: SpeedRange | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None


@dataclass
class EventRequirements:
    has_rides: bool
    requires_emergency_contact: bool
    requires_membership: bool
    ride_leaders_wanted: bool


class RegistrationService:
    def __init__(self):
        self.user_service = UserService()
        self.email_service = EmailService()

    def _create_registration(self, event: Event, user: User, registration_detail: RegistrationDetail,
                             request_detail: RequestDetail | None = None) -> Registration:
        registration = Registration()
        registration.event = event
        registration.user = user

        registration.name = user.get_full_name()
        registration.first_name = user.first_name
        registration.last_name = user.last_name
        registration.email = user.email
        registration.phone = user.profile.phone

        if event.has_rides:
            registration.ride = registration_detail.ride
            registration.speed_range_preference = registration_detail.speed_range_preference

        if event.ride_leaders_wanted:
            registration.ride_leader_preference = registration_detail.ride_leader_preference

        if event.requires_emergency_contact:
            registration.emergency_contact_name = registration_detail.emergency_contact_name
            registration.emergency_contact_phone = registration_detail.emergency_contact_phone

        if request_detail:
            registration.ip_address = request_detail.ip_address
            registration.user_agent = request_detail.user_agent
            registration.authenticated = request_detail.authenticated

        registration.save()
        return registration

    def _send_confirmation_email(self, registration: Registration) -> None:
        context = {
            'base_url': f"https://{settings.WEB_HOST}",
            'registration': registration,
        }

        self.email_service.send_email(
            template_name='confirmation',
            context=context,
            subject=f"Confirmed for {registration.event.name}",
            recipient_list=[registration.email],
        )

    def register(self, user_detail: UserDetail, registration_detail: RegistrationDetail, event: Event,
                 request_detail: RequestDetail | None = None) -> None:
        user = self.user_service.find_by_email_or_create(user_detail)

        registrations_submitted_or_confirmed = \
            Registration.objects.filter(user=user, event=event,
                                        state__in=[Registration.STATE_SUBMITTED, Registration.STATE_CONFIRMED])

        if registrations_submitted_or_confirmed.exists():
            # Do nothing, mostly because we don't want to reveal that they are registered already.
            # Log that a user attempted to register for an event they're already registered for.
            logger.info(
                f"User {user.email} (id={user.id}) attempted to register for event {event.name} (id={event.id}) but already has an active registration"
            )
        else:
            # OK, so either no registration exists, or it is withdrawn. Create a new one.
            registration = self._create_registration(event, user, registration_detail, request_detail)
            self._send_confirmation_email(registration)
            registration.confirm()
            registration.save()

    def fetch_current_registrations(self, user: User) -> QuerySet[Registration]:
        today = timezone.now().date()

        # Subquery to find the PK of the most recent registration for each event
        # for the given user. We assume 'pk' (auto-incrementing) indicates recency.
        latest_pk_subquery = Registration.objects.filter(
            user=user,
            event_id=OuterRef('event_id')  # Correlate with the outer query's event
        ).order_by('-pk').values('pk')[:1]

        return Registration.objects.filter(
            user=user,
            event__starts_at__date__gte=today,
            event__archived=False,
            state__in=[Registration.STATE_SUBMITTED, Registration.STATE_CONFIRMED],
            pk=Subquery(latest_pk_subquery)
        ).order_by('event__starts_at')

    def fetch_past_registrations(self, user: User) -> QuerySet[Registration]:
        today = timezone.now().date()

        latest_pk_subquery = Registration.objects.filter(
            user=user,
            event_id=OuterRef('event_id')
        ).order_by('-pk').values('pk')[:1]

        return Registration.objects.filter(
            user=user,
            event__ends_at__date__lt=today,
            pk=Subquery(latest_pk_subquery)
        ).order_by('-event__starts_at')

    def fetch_user_statistics(self, user: User) -> dict:
        today = timezone.now().date()

        total_events_attended = Registration.objects.filter(
            user=user,
            event__ends_at__date__lt=today,
            state=Registration.STATE_CONFIRMED
        ).values('event').distinct().count()

        times_as_ride_leader = Registration.objects.filter(
            user=user,
            event__ends_at__date__lt=today,
            state=Registration.STATE_CONFIRMED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        ).count()

        return {
            'total_events_attended': total_events_attended,
            'times_as_ride_leader': times_as_ride_leader,
        }

    def get_rides_for_event(self, event: Event) -> QuerySet[Ride]:
        return Ride.objects.filter(event=event)

    def get_speed_ranges_for_ride(self, ride: Ride | None) -> QuerySet[SpeedRange]:
        if ride is None:
            return SpeedRange.objects.none()
        return ride.speed_ranges.all()

    def get_event_requirements(self, event: Event) -> EventRequirements:
        return EventRequirements(
            has_rides=event.has_rides,
            requires_emergency_contact=event.requires_emergency_contact,
            requires_membership=event.requires_membership,
            ride_leaders_wanted=event.ride_leaders_wanted,
        )

    def validate_registration_selections(self, event: Event, ride: Ride | None, speed_range: SpeedRange | None) -> dict:
        errors = {}

        if ride is not None and ride.event_id != event.id:
            errors['ride'] = 'Selected ride does not belong to this event.'

        if speed_range is not None and ride is not None:
            if not ride.speed_ranges.filter(id=speed_range.id).exists():
                errors['speed_range_preference'] = 'Selected speed range is not available for this ride.'

        if event.has_rides and ride is None:
            errors['ride'] = 'A ride selection is required for this event.'

        if ride is not None and ride.speed_ranges.exists() and speed_range is None:
            errors['speed_range_preference'] = 'A speed range selection is required for this ride.'

        return errors

    def is_registration_allowed(self, event: Event) -> tuple[bool, str | None]:
        if event.cancelled:
            return False, 'Event is cancelled.'

        if event.archived:
            return False, 'Event is archived.'

        if not event.registration_open:
            return False, 'Registration is closed.'

        if event.external_registration_url:
            return False, 'Event uses external registration.'

        if not event.has_capacity_available:
            return False, 'Event has reached capacity.'

        return True, None
