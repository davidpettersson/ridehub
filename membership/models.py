from django.db import models

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

    category = models.CharField(
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

    member_for = models.CharField(
        max_length=16,
        help_text='Self-reported membership length'
    )

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