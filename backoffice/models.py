from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition
from django_prose_editor.fields import ProseEditorField
from phonenumber_field.modelfields import PhoneNumberField


class Member(models.Model):
    full_name = models.CharField(max_length=128)
    email = models.EmailField()

    def __str__(self):
        return self.full_name


class Program(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Event(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
    )

    name = models.CharField(
        max_length=128,
    )

    visible = models.BooleanField(
        default=True,
        help_text='Check if the event is visible to members.'
    )

    location = models.CharField(
        max_length=128,
        blank=True,
        help_text='Physical (e.g. "Andrew Haydon Park") or virtual location ("Teams").'
    )

    location_url = models.URLField(
        blank=True,
        verbose_name='Location URL',
        help_text='If provided, users will get a link to the location. Typically, you can place a Google Maps location here.',
    )

    starts_at = models.DateTimeField(
        help_text='Start time of the event',
    )

    ends_at = models.DateTimeField(
        help_text='End time of the event. If left blank, event duration is assumed to be one hour.',
        blank=True,
        null=True,
    )

    registration_closes_at = models.DateTimeField(
        help_text='Closing time of the registration',
    )

    external_registration_url = models.URLField(
        blank=True,
        help_text='When an external registration URL is provided, registration will be delegated to the external system',
    )

    registration_limit = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Maximum number of registrations allowed. Blank means no limit. Zero means no registration.'
    )

    description = ProseEditorField(
        help_text='Description of the event to share with members.'
    )

    virtual = models.BooleanField(
        default=False,
        help_text='Mark virtual if it happens online, via Teams, Zwift or other electronic means.'
    )

    ride_leaders_wanted = models.BooleanField(
        default=True,
        help_text='Check if you want to allow members to sign up as ride leaders.'
    )

    requires_emergency_contact = models.BooleanField(
        default=True,
        help_text='Check if you require registrations to provide emergency contact details.'
    )

    cancelled = models.BooleanField(
        default=False,
        help_text='Indicates if the event has been cancelled.'
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the event was cancelled.'
    )

    cancellation_reason = models.TextField(
        blank=True,
        help_text='Reason for cancellation.'
    )

    archived = models.BooleanField(
        default=False,
        help_text='Indicates if the event has been archived. Archived events are not visible to members.'
    )

    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the event was archived.'
    )

    organizer_email = models.EmailField(
        blank=True,
        help_text='When set, members will be able to reach out to the organizer at this email.'
    )

    @property
    def duration(self) -> timedelta:
        if self.ends_at:
            return self.ends_at - self.starts_at
        else:
            return timedelta(hours=1)

    @property
    def has_rides(self) -> bool:
        return self.ride_set.all().exists()

    @property
    def ride_count(self) -> int:
        return self.ride_set.count()

    @property
    def registration_count(self) -> int:
        return self.registration_set.filter(state=Registration.STATE_CONFIRMED).count()

    @property
    def capacity_remaining(self) -> int | None:
        if self.registration_limit is None:
            return None
        return max(0, self.registration_limit - self.registration_count)

    @property
    def has_capacity_available(self) -> bool:
        return self.registration_limit is None or self.registration_count < self.registration_limit

    @property
    def registration_open(self) -> bool:
        if self.cancelled:
            return False

        if self.archived:
            return False

        return timezone.now() < self.registration_closes_at

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        if self.starts_at and self.registration_closes_at:
            if self.registration_closes_at > self.starts_at:
                raise ValidationError({
                    'registration_closes_at': 'Registration cannot close after the event starts.'
                })


class Route(models.Model):
    name = models.CharField(
        max_length=128,
        help_text='Ride name.'
    )

    url = models.URLField(
        verbose_name="Ride With GPS URL",
        blank=True,
        help_text='Ride with GPS URL. If this is set, then whenever an import from Ride with GPS happens other fields will be overwritten for this route.'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='When this route was last updated.'
    )

    distance = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Distance in kilometers.'
    )

    elevation_gain = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Elevation gain in meters.'
    )

    last_imported_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this route was last imported into the backoffice.'
    )

    def ride_with_gps_id(self):
        parts = self.url.split('/')
        return parts[-1] if len(parts) > 0 else None

    def __str__(self):
        return self.name


class SpeedRange(models.Model):
    lower_limit = models.IntegerField()
    upper_limit = models.IntegerField(blank=True, null=True)

    @property
    def range(self) -> str:
        if self.upper_limit is None:
            return f"{self.lower_limit}+ km/h"
        else:
            return f"{self.lower_limit}-{self.upper_limit} km/h"

    def __str__(self) -> str:
        return self.range

    class Meta:
        ordering = ['lower_limit']


class Ride(models.Model):
    name = models.CharField(
        max_length=128,
        help_text='Ride name, for example "A Ride Long"'
    )

    description = ProseEditorField(
        blank=True,
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
    )

    route = models.ForeignKey(
        Route,
        on_delete=models.PROTECT,
    )

    speed_ranges = models.ManyToManyField(
        SpeedRange,
        blank=True,
    )

    ordering = models.PositiveIntegerField(
        default=0,
        blank=False,
        null=False,
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['ordering']


class Registration(models.Model):
    class RideLeaderPreference(models.TextChoices):
        YES = 'y', 'Yes'
        NO = 'n', 'No'
        NOT_APPLICABLE = 'na', 'N/A'

    name = models.CharField(
        max_length=128
    )

    first_name = models.CharField(
        max_length=128
    )

    last_name = models.CharField(
        max_length=128
    )

    email = models.EmailField()

    phone = PhoneNumberField(blank=True)

    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT
    )

    ride = models.ForeignKey(
        Ride,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    speed_range_preference = models.ForeignKey(
        SpeedRange,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    ride_leader_preference = models.CharField(
        max_length=2,
        choices=RideLeaderPreference,
        default=RideLeaderPreference.NOT_APPLICABLE
    )

    emergency_contact_name = models.CharField(
        max_length=128,
        blank=True
    )

    emergency_contact_phone = models.CharField(
        max_length=128,
        blank=True
    )

    STATE_SUBMITTED = 'submitted'
    STATE_CONFIRMED = 'confirmed'
    STATE_WITHDRAWN = 'withdrawn'

    state = FSMField(default=STATE_SUBMITTED, protected=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    @transition(field=state, source=STATE_SUBMITTED, target=STATE_CONFIRMED)
    def confirm(self):
        self.confirmed_at = timezone.now()

    @property
    def is_ride_leader(self):
        return self.ride_leader_preference == Registration.RideLeaderPreference.YES

    @transition(field=state, source=STATE_CONFIRMED, target=STATE_WITHDRAWN)
    def withdraw(self):
        self.withdrawn_at = timezone.now()

    def __str__(self):
        return f"{self.name} for {self.event}"

    def clean(self):
        if not self.event.ride_set.exists():
            return

        if self.ride and self.speed_range_preference:
            if not self.ride.speed_ranges.filter(id=self.speed_range_preference.id).exists():
                raise ValidationError({
                    'speed_range_preference': f"{self.id} The speed range '{self.speed_range_preference}' is not available for {self.ride}."
                })

        if self.event.requires_emergency_contact:
            if not self.emergency_contact_name or not self.emergency_contact_phone:
                raise ValidationError({
                    'emergency_contact_name': "This field is required as the event requires an emergency contact.",
                    'emergency_contact_phone': "This field is required as the event requires an emergency contact."
                })

        if self.event.ride_leaders_wanted:
            if self.ride_leader_preference == Registration.RideLeaderPreference.NOT_APPLICABLE:
                raise ValidationError({
                    'ride_leader_preference': "This field is required as the event requires a ride leader preference."
                })


class Announcement(models.Model):
    TYPE_INFORMATION = 'i'
    TYPE_WARNING = 'w'

    TYPE_CHOICES = [
        (TYPE_INFORMATION, 'Information'),
        (TYPE_WARNING, 'Warning'),
    ]

    begin_at = models.DateTimeField(
        help_text='Time when the announcement should begin.',
    )

    end_at = models.DateTimeField(
        help_text='Time when the announcement should end.',
    )

    type = models.CharField(
        max_length=1,
        choices=TYPE_CHOICES,
        default=TYPE_INFORMATION,
        help_text='Type of the announcement. Use warning to get more attention.',
    )

    title = models.CharField(
        max_length=128,
        help_text='Name of the announcement. Will precede the body of the announcement.', )

    text = ProseEditorField(
        help_text='Body of the announcement. Keep formatting to a minimum as there is limited space on the page.'
    )

    def __str__(self):
        return self.title