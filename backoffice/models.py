from django.db import models
from django.core.exceptions import ValidationError


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
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    location = models.CharField(max_length=128, blank=True)
    starts_at = models.DateTimeField()
    description = models.TextField()
    virtual = models.BooleanField(default=False)
    ride_leaders_wanted = models.BooleanField(default=True)
    requires_emergency_contact = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Route(models.Model):
    name = models.CharField(max_length=128)
    url = models.URLField(verbose_name="Ride With GPS URL", blank=True)

    def __str__(self):
        return self.name


class SpeedRange(models.Model):
    lower_limit = models.IntegerField()
    upper_limit = models.IntegerField(blank=True, null=True)

    def __str__(self):
        if self.upper_limit is None:
            return f"{self.lower_limit}+ km/h"
        else:
            return f"{self.lower_limit} - {self.upper_limit} km/h"


class Ride(models.Model):
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    speed_ranges = models.ManyToManyField(SpeedRange, blank=True)

    def __str__(self):
        return self.name


class Registration(models.Model):
    name = models.CharField(max_length=128)
    email = models.EmailField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, null=True, blank=True)
    speed_range_preference = models.ForeignKey(SpeedRange, on_delete=models.CASCADE, null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=128, blank=True)
    emergency_contact_phone = models.CharField(max_length=128, blank=True)


    def __str__(self):
        return f"{self.full_name} - {self.event} - {self.ride.name if self.ride else 'No ride'}"

    def clean(self):
        # Validate that the selected speed range is available for this ride
        if self.ride and self.speed_range_preference:
            if not self.ride.speed_ranges.filter(id=self.speed_range_preference.id).exists():
                raise ValidationError({
                    'speed_range_preference': f"The speed range '{self.speed_range_preference}' is not available for this ride."
                })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
