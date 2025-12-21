from dateutil.utils import today
from django.db import models


class Member(models.Model):
    first_name = models.CharField(
        max_length=64,
    )

    last_name = models.CharField(
        max_length=64,
    )

    date_of_birth = models.DateField(
    )

    sex = models.CharField(
        max_length=16,
    )

    category = models.CharField(
        max_length=64,
    )

    city = models.CharField(
        max_length=64,
        default='',
    )

    country = models.CharField(
        max_length=32,
    )

    postal_code = models.CharField(
        max_length=16,
    )

    email = models.EmailField(
        max_length=64,
    )

    phone = models.CharField(
        max_length=32,
    )

    cohort = models.DateField(
        help_text='Identified year+month cohort. Day always 1.',
    )

    last_registration_year = models.DateField(
        help_text='Identifies which year the member was last registered. Month and day always 1.',
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Registration(models.Model):
    registered_at = models.DateTimeField(
        help_text='Date of registration in CCN Bikes',
    )

    identity = models.IntegerField(
        help_text='Registration identity provided by CCN Bikes',
    )

    first_name = models.CharField(
        max_length=64,
    )

    last_name = models.CharField(
        max_length=64,
    )

    sex = models.CharField(
        max_length=16,
    )

    date_of_birth = models.DateField(
    )

    year = models.DateField(
    )

    category = models.CharField(
        max_length=64,
    )

    city = models.CharField(
        max_length=64,
    )

    country = models.CharField(
        max_length=32,
    )

    postal_code = models.CharField(
        max_length=16,
    )

    email = models.EmailField(
        max_length=64,
    )

    phone = models.CharField(
        max_length=32,
    )

    duration = models.CharField(
        max_length=32,
        help_text='Self-reported membership duration'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} in {self.registered_at.year}"


class Match(models.Model):
    registration = models.OneToOneField(
        to=Registration,
        on_delete=models.CASCADE,
    )

    member = models.ForeignKey(
        to=Member,
        on_delete=models.CASCADE,
    )

    method = models.CharField(
        max_length=128,
    )

    confidence = models.FloatField(
        help_text='Confidence score between 0..1'
    )

    matched_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
    )

    def __str__(self):
        return f"{self.registration} -> {self.member}"

    class Meta:
        verbose_name = 'match'
        verbose_name_plural = 'matches'