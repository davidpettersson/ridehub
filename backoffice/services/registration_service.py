import hashlib
import logging
import random
import string
from dataclasses import dataclass
from enum import Enum

from django.contrib.auth.models import User
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.db import models, transaction
from django.db.models import QuerySet, Subquery, OuterRef, Count
from django.utils import timezone

from audit.services import AuditService
from backoffice.models import Event, Registration, RegistrationSnapshot, SpeedRange, Ride, UserProfile
from backoffice.services.email_service import EmailService
from backoffice.services.request_service import RequestDetail
from backoffice.services.user_service import UserService, UserDetail
from backoffice.utils import lower_email
from ridehub import settings

logger = logging.getLogger(__name__)

VERIFICATION_TOKEN_MAX_AGE = 86400
VERIFICATION_TOKEN_SALT = 'email-verification'


MASK_DOT = '·'
MASK_DOT_MIN = 3
MASK_DOT_MAX = 6


def _seeded_dot_count(name: str) -> int:
    digest = hashlib.sha256(name.strip().lower().encode('utf-8')).digest()
    return MASK_DOT_MIN + digest[0] % (MASK_DOT_MAX - MASK_DOT_MIN + 1)


def mask_name_with_initials(registration: 'Registration') -> tuple[str, str]:
    return f"{registration.first_name[:1].upper()}*", f"{registration.last_name[:1].upper()}*"


def mask_name_with_random_letters(registration: 'Registration') -> tuple[str, str]:
    return random.choice(string.ascii_uppercase), random.choice(string.ascii_uppercase)


def mask_name_with_dots(registration: 'Registration') -> tuple[str, str]:
    return (
        f"{registration.first_name[:1].upper()}{MASK_DOT * _seeded_dot_count(registration.first_name)}",
        f"{registration.last_name[:1].upper()}{MASK_DOT * _seeded_dot_count(registration.last_name)}",
    )


NAME_MASKING_STRATEGY = mask_name_with_dots


class RegistrationResult(Enum):
    CONFIRMED = 'confirmed'
    VERIFICATION_REQUIRED = 'verification_required'
    DUPLICATE = 'duplicate'


@dataclass
class RegistrationDetail:
    ride: Ride | None
    ride_leader_preference: str | None
    speed_range_preference: SpeedRange | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    first_time_attendee: str | None = None


@dataclass
class EventRequirements:
    has_rides: bool
    requires_emergency_contact: bool
    requires_membership: bool
    ride_leaders_wanted: bool
    ask_first_time_attendee: bool


class RegistrationService:
    def __init__(self):
        self.user_service = UserService()
        self.email_service = EmailService()
        self.audit_service = AuditService()

    def _create_registration(self, event: Event, user: User, user_detail: UserDetail,
                             registration_detail: RegistrationDetail,
                             request_detail: RequestDetail | None = None) -> Registration:
        registration = Registration()
        registration.event = event
        registration.user = user

        registration.name = f"{user_detail.first_name} {user_detail.last_name}"
        registration.first_name = user_detail.first_name
        registration.last_name = user_detail.last_name
        registration.email = user.email
        registration.phone = user_detail.phone

        if event.has_rides:
            registration.ride = registration_detail.ride
            registration.speed_range_preference = registration_detail.speed_range_preference

        if event.ride_leaders_wanted:
            registration.ride_leader_preference = registration_detail.ride_leader_preference

        if event.requires_emergency_contact:
            registration.emergency_contact_name = registration_detail.emergency_contact_name
            registration.emergency_contact_phone = registration_detail.emergency_contact_phone

        if event.ask_first_time_attendee:
            if registration_detail.first_time_attendee is None:
                raise ValueError(
                    "first_time_attendee must be provided when event.ask_first_time_attendee is True"
                )
            registration.first_time_attendee = registration_detail.first_time_attendee

        if request_detail:
            registration.ip_address = request_detail.ip_address
            registration.user_agent = request_detail.user_agent
            registration.authenticated = request_detail.authenticated

        registration.full_clean(exclude=['state'])
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

    def _should_skip_verification(self, user: User, acting_user: User | None) -> bool:
        if acting_user is not None and acting_user.is_authenticated and acting_user.pk == user.pk:
            if not user.profile.email_verified:
                user.profile.email_verified = True
                user.profile.save(update_fields=['email_verified'])
            return True
        return False

    def build_verification_url(self, registration: Registration) -> str:
        signer = TimestampSigner(salt=VERIFICATION_TOKEN_SALT)
        token = signer.sign(str(registration.id))
        return f"https://{settings.WEB_HOST}/registrations/verify?token={token}"

    def _send_verification_email(self, registration: Registration) -> None:
        context = {
            'base_url': f"https://{settings.WEB_HOST}",
            'registration': registration,
            'verification_url': self.build_verification_url(registration),
        }

        self.email_service.send_email(
            template_name='verification',
            context=context,
            subject=f"Verify your email for {registration.event.name}",
            recipient_list=[registration.email],
        )

    def verify_registration(self, token: str) -> tuple[Registration | None, str | None]:
        signer = TimestampSigner(salt=VERIFICATION_TOKEN_SALT)

        try:
            registration_id = signer.unsign(token, max_age=VERIFICATION_TOKEN_MAX_AGE)
        except SignatureExpired:
            try:
                registration_id = signer.unsign(token)
            except BadSignature:
                return None, 'invalid'

            try:
                registration = Registration.objects.select_related('user', 'user__profile').get(
                    id=int(registration_id),
                    state=Registration.STATE_UNVERIFIED,
                )
            except Registration.DoesNotExist:
                return None, 'not_found'

            self._send_verification_email(registration)
            return None, 'expired'
        except BadSignature:
            return None, 'invalid'

        try:
            registration = Registration.objects.select_related('user', 'user__profile').get(
                id=int(registration_id),
                state=Registration.STATE_UNVERIFIED,
            )
        except Registration.DoesNotExist:
            return None, 'not_found'

        registration.confirm()
        registration.save()

        user = registration.user
        user.profile.email_verified = True
        user.profile.save()

        self._send_confirmation_email(registration)

        return registration, None

    def has_active_registration(self, user: User, event: Event) -> bool:
        return Registration.objects.filter(
            user=user, event=event,
            state__in=[Registration.STATE_SUBMITTED, Registration.STATE_CONFIRMED, Registration.STATE_UNVERIFIED],
        ).exists()

    def register(self, user_detail: UserDetail, registration_detail: RegistrationDetail, event: Event,
                 request_detail: RequestDetail | None = None,
                 acting_user: User | None = None) -> RegistrationResult:
        update_existing = (
            acting_user is not None
            and acting_user.is_authenticated
            and lower_email(acting_user.email) == lower_email(user_detail.email)
        )
        user = self.user_service.find_by_email_or_create(user_detail, update_existing=update_existing)

        if self.has_active_registration(user, event):
            logger.info(
                f"User {user.email} (id={user.id}) attempted to register for event {event.name} (id={event.id}) but already has an active registration"
            )
            return RegistrationResult.DUPLICATE

        registration = self._create_registration(event, user, user_detail, registration_detail, request_detail)

        if self._should_skip_verification(user, acting_user):
            self._send_confirmation_email(registration)
            registration.confirm()
            registration.save()
            return RegistrationResult.CONFIRMED

        registration.hold_for_verification()
        registration.save()
        self._send_verification_email(registration)
        return RegistrationResult.VERIFICATION_REQUIRED

    def _name_visible_to_viewer(self, registration: Registration, viewer_is_authenticated: bool,
                                viewer_is_privileged: bool) -> bool:
        if viewer_is_privileged:
            return True

        if registration.user_id is None:
            return False

        profile = getattr(registration.user, 'profile', None)
        if profile is None:
            return False

        match profile.name_visibility:
            case UserProfile.NameVisibility.ONLY_USERS:
                return viewer_is_authenticated
            case UserProfile.NameVisibility.ONLY_REQUIRED_USERS:
                return False
            case _:
                return True

    def mask_hidden_names(self, registrations: list[Registration], viewer_is_authenticated: bool,
                          viewer_is_privileged: bool) -> list[Registration]:
        for registration in registrations:
            if not self._name_visible_to_viewer(registration, viewer_is_authenticated, viewer_is_privileged):
                registration.first_name, registration.last_name = NAME_MASKING_STRATEGY(registration)
                registration.name = f"{registration.first_name} {registration.last_name}"
        return registrations

    def fetch_confirmed_emails(self, event: Event, ride_leaders_only: bool = False) -> list[str]:
        registrations = Registration.objects.filter(
            event=event,
            state=Registration.STATE_CONFIRMED,
        )
        if ride_leaders_only:
            registrations = registrations.filter(
                ride_leader_preference=Registration.RideLeaderPreference.YES
            )
        return sorted({
            email for email in registrations.values_list('email', flat=True) if email
        })

    def fetch_ride_counts(self, user_ids: list[int]) -> dict[int, int]:
        rows = (
            Registration.objects.filter(
                user_id__in=user_ids,
                state=Registration.STATE_CONFIRMED,
            )
            .exclude(event__state=Event.STATE_CANCELLED)
            .values('user_id')
            .annotate(count=Count('event', distinct=True))
        )
        return {row['user_id']: row['count'] for row in rows}

    def fetch_confirmed_event_ids(self, user: User, event_ids: list[int]) -> set[int]:
        return set(
            Registration.objects.filter(
                user=user,
                event_id__in=event_ids,
                state=Registration.STATE_CONFIRMED
            ).values_list('event_id', flat=True)
        )

    def fetch_current_registrations(self, user: User) -> QuerySet[Registration]:
        today = timezone.localdate()

        # Subquery to find the PK of the most recent registration for each event
        # for the given user. We assume 'pk' (auto-incrementing) indicates recency.
        latest_pk_subquery = Registration.objects.filter(
            user=user,
            event_id=OuterRef('event_id')  # Correlate with the outer query's event
        ).order_by('-pk').values('pk')[:1]

        return Registration.objects.filter(
            user=user,
            event__starts_at__date__gte=today,
            event__state__in=[Event.STATE_LIVE, Event.STATE_CANCELLED],
            state__in=[Registration.STATE_SUBMITTED, Registration.STATE_CONFIRMED],
            pk=Subquery(latest_pk_subquery)
        ).select_related('event', 'ride', 'speed_range_preference').order_by('event__starts_at')

    def fetch_past_registrations(self, user: User) -> QuerySet[Registration]:
        today = timezone.localdate()

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
        today = timezone.localdate()

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
            ask_first_time_attendee=event.ask_first_time_attendee,
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

    def withdraw_registration(self, registration: Registration, user: User) -> None:
        allowed, reason = self.is_registration_withdrawable(registration)

        if not allowed:
            raise ValueError(reason)

        registration.withdraw()
        registration.save()

        logger.info(
            "User %s (id=%d) withdrew registration %d from event %s (id=%d)",
            user.email, user.id, registration.id,
            registration.event.name, registration.event.id,
        )

        self.audit_service.log(user, 'registration_withdrawn', target=registration)

        self._send_withdrawal_email(registration, withdrawn_by_organizer=False)

    def staff_withdraw(self, registration: Registration, staff_user) -> None:
        if registration.state not in [Registration.STATE_CONFIRMED, Registration.STATE_UNVERIFIED]:
            raise ValueError(f"Cannot withdraw registration in state '{registration.state}'")

        was_confirmed = registration.state == Registration.STATE_CONFIRMED

        registration.withdraw()
        registration.save()

        logger.info(
            "Staff user %s (id=%d) withdrew registration %d for %s from event %s (id=%d)",
            staff_user.email, staff_user.id, registration.id, registration.email,
            registration.event.name, registration.event.id,
        )

        self.audit_service.log(staff_user, 'staff_withdrew', target=registration)

        if was_confirmed:
            self._send_withdrawal_email(registration)

    def staff_register(self, user_detail: UserDetail, registration_detail: RegistrationDetail,
                       event: Event, staff_user) -> Registration | None:
        user = self.user_service.find_by_email_or_create(user_detail, update_existing=True)

        existing = Registration.objects.filter(
            user=user, event=event,
            state__in=[Registration.STATE_SUBMITTED, Registration.STATE_CONFIRMED, Registration.STATE_UNVERIFIED]
        )

        if existing.exists():
            logger.info(
                "Staff user %s (id=%d) attempted to register %s for event %s (id=%d) but active registration exists",
                staff_user.email, staff_user.id, user.email, event.name, event.id,
            )
            return None

        registration = self._create_registration(event, user, user_detail, registration_detail)
        registration.confirm()
        registration.save()

        logger.info(
            "Staff user %s (id=%d) registered %s for event %s (id=%d)",
            staff_user.email, staff_user.id, user.email, event.name, event.id,
        )

        self.audit_service.log(staff_user, 'staff_registered', target=registration)

        self._send_confirmation_email(registration)
        return registration

    def _field_has_changed(self, registration: Registration, field_name: str, value) -> bool:
        current = getattr(registration, field_name)

        if isinstance(current, models.Model) or isinstance(value, models.Model):
            current_id = current.pk if current is not None else None
            new_id = value.pk if value is not None else None
            return current_id != new_id

        return str(current or '') != str(value or '')

    def _create_snapshot(self, registration: Registration, actor: User | None,
                          changed_fields: list[str]) -> RegistrationSnapshot:
        snapshot = RegistrationSnapshot(
            registration=registration,
            actor=actor,
            changed_fields=changed_fields,
        )

        for field_name in RegistrationSnapshot.SNAPSHOT_FIELDS:
            setattr(snapshot, field_name, getattr(registration, field_name))

        snapshot.full_clean()
        snapshot.save()
        return snapshot

    def _apply_registration_changes(self, registration: Registration, actor: User | None,
                                    action: str, fields: dict) -> list[str]:
        changed_fields = [
            field_name for field_name, value in fields.items()
            if self._field_has_changed(registration, field_name, value)
        ]

        if not changed_fields:
            return []

        with transaction.atomic():
            self._create_snapshot(registration, actor, changed_fields)

            for field_name, value in fields.items():
                setattr(registration, field_name, value)

            if 'first_name' in changed_fields or 'last_name' in changed_fields:
                registration.name = f"{registration.first_name} {registration.last_name}"

            registration.full_clean(exclude=['state'])
            registration.save()

            self.audit_service.log(actor, action, target=registration)

        return changed_fields

    def staff_update_registration(self, registration: Registration, staff_user, **fields) -> list[str]:
        changed_fields = self._apply_registration_changes(
            registration, staff_user, 'staff_edited', fields
        )

        if changed_fields:
            logger.info(
                "Staff changed %s on registration %d for %s (event %s, id=%d)",
                changed_fields, registration.id, registration.email,
                registration.event.name, registration.event.id,
            )

        return changed_fields

    def has_editable_fields(self, event: Event) -> bool:
        return any([
            event.has_rides,
            event.ride_leaders_wanted,
            event.ask_first_time_attendee,
            event.requires_emergency_contact,
        ])

    def is_registration_editable(self, registration: Registration) -> tuple[bool, str | None]:
        if registration.state != Registration.STATE_CONFIRMED:
            return False, 'Only confirmed registrations can be edited.'

        event = registration.event

        if event.cancelled:
            return False, 'Event is cancelled.'

        if event.archived:
            return False, 'Event is archived.'

        if timezone.now() >= event.starts_at:
            return False, 'Event has already started.'

        if not self.has_editable_fields(event):
            return False, 'This event has no editable registration details.'

        return True, None

    def mark_editable(self, registrations: list[Registration]) -> list[Registration]:
        for registration in registrations:
            registration.editable = self.is_registration_editable(registration)[0]
        return registrations

    def is_registration_withdrawable(self, registration: Registration) -> tuple[bool, str | None]:
        if registration.state != Registration.STATE_CONFIRMED:
            return False, 'Only confirmed registrations can be withdrawn.'

        event = registration.event

        if event.cancelled:
            return False, 'Event is cancelled.'

        if event.archived:
            return False, 'Event is archived.'

        if timezone.now() >= event.starts_at:
            return False, 'Event has already started.'

        return True, None

    def mark_withdrawable(self, registrations: list[Registration]) -> list[Registration]:
        for registration in registrations:
            registration.withdrawable = self.is_registration_withdrawable(registration)[0]
        return registrations

    def _editable_fields(self, event: Event, registration_detail: RegistrationDetail) -> dict:
        fields = {}

        if event.has_rides:
            fields['ride'] = registration_detail.ride
            fields['speed_range_preference'] = registration_detail.speed_range_preference

        if event.ride_leaders_wanted:
            fields['ride_leader_preference'] = registration_detail.ride_leader_preference

        if event.ask_first_time_attendee:
            fields['first_time_attendee'] = registration_detail.first_time_attendee

        if event.requires_emergency_contact:
            fields['emergency_contact_name'] = registration_detail.emergency_contact_name
            fields['emergency_contact_phone'] = registration_detail.emergency_contact_phone

        return fields

    def edit_registration(self, registration: Registration, user: User,
                          registration_detail: RegistrationDetail) -> list[str]:
        allowed, reason = self.is_registration_editable(registration)

        if not allowed:
            raise ValueError(reason)

        fields = self._editable_fields(registration.event, registration_detail)
        changed_fields = self._apply_registration_changes(
            registration, user, 'registration_edited', fields
        )

        if changed_fields:
            logger.info(
                "User %s (id=%d) changed %s on registration %d for event %s (id=%d)",
                user.email, user.id, changed_fields, registration.id,
                registration.event.name, registration.event.id,
            )

        return changed_fields

    def _send_withdrawal_email(self, registration: Registration,
                               withdrawn_by_organizer: bool = True) -> None:
        context = {
            'base_url': f"https://{settings.WEB_HOST}",
            'registration': registration,
            'withdrawn_by_organizer': withdrawn_by_organizer,
        }

        self.email_service.send_email(
            template_name='withdrawal',
            context=context,
            subject=f"Registration withdrawn for {registration.event.name}",
            recipient_list=[registration.email],
        )

    def is_registration_allowed(self, event: Event) -> tuple[bool, str | None]:
        if not event.registration_enabled:
            return False, 'Registration is not available for this event.'

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
