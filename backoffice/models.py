from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition


class Member(models.Model):
    full_name = models.CharField(max_length=128)
    email = models.EmailField()

    def __str__(self):
        return self.full_name


class Program(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class Event(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT)
    name = models.CharField(max_length=128)
    location = models.CharField(max_length=128, blank=True)
    starts_at = models.DateTimeField()
    registration_closes_at = models.DateTimeField()
    description = models.TextField()
    virtual = models.BooleanField(default=False)
    ride_leaders_wanted = models.BooleanField(default=True)
    requires_emergency_contact = models.BooleanField(default=True)

    @property
    def has_rides(self) -> bool:
        return self.ride_set.all().exists()

    @property
    def ride_count(self) -> int:
        return self.ride_set.count()

    @property
    def registration_count(self) -> int:
        return self.registration_set.count()

    @property
    def registration_open(self) -> str:
        return 'Yes' if timezone.now() < self.registration_closes_at else 'No'

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
    name = models.CharField(max_length=128)
    url = models.URLField(verbose_name="Ride With GPS URL", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def ride_with_gps_id(self):
        parts = self.url.split('/')
        return parts[-1] if len(parts) > 0 else None

    def __str__(self):
        return self.name


class SpeedRange(models.Model):
    lower_limit = models.IntegerField()
    upper_limit = models.IntegerField(blank=True, null=True)

    def range(self) -> str:
        if self.upper_limit is None:
            return f"{self.lower_limit}+ km/h"
        else:
            return f"{self.lower_limit}-{self.upper_limit} km/h"

    def __str__(self) -> str:
        return self.range()

    class Meta:
        ordering = ['lower_limit']


class Ride(models.Model):
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.PROTECT)
    speed_ranges = models.ManyToManyField(SpeedRange, blank=True)

    def __str__(self):
        return self.name


class Registration(models.Model):
    RIDE_LEADER_YES = 'y'
    RIDE_LEADER_NO = 'n'
    RIDE_LEADER_NOT_APPLICABLE = 'na'

    RIDE_LEADER_CHOICES = [
        (RIDE_LEADER_YES, 'Yes'),
        (RIDE_LEADER_NO, 'No'),
        (RIDE_LEADER_NOT_APPLICABLE, 'N/A')
    ]

    name = models.CharField(max_length=128)
    email = models.EmailField()
    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    ride = models.ForeignKey(Ride, on_delete=models.PROTECT, null=True, blank=True)
    speed_range_preference = models.ForeignKey(SpeedRange, on_delete=models.PROTECT, null=True, blank=True)
    ride_leader_preference = models.CharField(max_length=2, choices=RIDE_LEADER_CHOICES, default=RIDE_LEADER_NOT_APPLICABLE)
    emergency_contact_name = models.CharField(max_length=128, blank=True)
    emergency_contact_phone = models.CharField(max_length=128, blank=True)

    state = FSMField(default='submitted', protected=True)

    registered_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)

    @transition(field=state, source='submitted', target='confirmed')
    def confirm(self):
        self.confirmed_at = timezone.now()

    @transition(field=state, source='confirmed', target='cancelled')
    def cancel(self):
        self.cancelled_at = timezone.now()

    def __str__(self):
        return f"{self.name} for {self.event}"

    def clean(self):
        if not self.event.ride_set.exists():
            return

        if self.ride and self.speed_range_preference:
            if not self.ride.speed_ranges.filter(id=self.speed_range_preference.id).exists():
                raise ValidationError({
                    'speed_range_preference': f"The speed range '{self.speed_range_preference}' is not available for this ride."
                })

        if self.event.requires_emergency_contact:
            if not self.emergency_contact_name or not self.emergency_contact_phone:
                raise ValidationError({
                    'emergency_contact_name': "This field is required as the event requires an emergency contact.",
                    'emergency_contact_phone': "This field is required as the event requires an emergency contact."
                })

        if self.event.ride_leaders_wanted:
            if self.ride_leader_preference == self.RIDE_LEADER_NOT_APPLICABLE:
                raise ValidationError({
                    'ride_leader_preference': "This field is required as the event requires a ride leader preference."
                })
