from django.contrib.auth.models import User
from django.db import connection
from django.template import Template, Context
from django.test import TestCase

from phonenumber_field.phonenumber import PhoneNumber

from backoffice.models import UserProfile
from web.templatetags.phone_filters import national_phone


class NationalPhoneFilterTests(TestCase):
    def test_formats_canadian_number_in_national_format(self):
        phone = PhoneNumber.from_string('+16135550100')

        result = national_phone(phone)

        self.assertEqual('(613) 555-0100', result)

    def test_returns_none_unchanged(self):
        result = national_phone(None)

        self.assertIsNone(result)

    def test_returns_empty_string_unchanged(self):
        result = national_phone('')

        self.assertEqual('', result)

    def test_formats_ottawa_area_code(self):
        phone = PhoneNumber.from_string('+16132345678')

        result = national_phone(phone)

        self.assertEqual('(613) 234-5678', result)

    def test_renders_in_template_with_phone_number_object(self):
        phone = PhoneNumber.from_string('+16135550100')
        template = Template('{% load phone_filters %}{{ phone|national_phone }}')

        result = template.render(Context({'phone': phone}))

        self.assertEqual('(613) 555-0100', result.strip())

    def test_renders_in_template_with_model_field(self):
        user = User.objects.create_user(username='testuser')
        profile = user.profile
        profile.phone = '+16135550100'
        profile.save()
        profile.refresh_from_db()
        template = Template('{% load phone_filters %}{{ profile.phone|national_phone }}')

        result = template.render(Context({'profile': profile}))

        self.assertEqual('(613) 555-0100', result.strip())

    def test_handles_phone_stored_without_country_code(self):
        user = User.objects.create_user(username='testlegacy')
        profile = user.profile
        profile.phone = '+16135550100'
        profile.save()
        cursor = connection.cursor()
        cursor.execute(
            'UPDATE backoffice_userprofile SET phone = %s WHERE id = %s',
            ['6135550100', profile.id]
        )
        profile.refresh_from_db()
        template = Template('{% load phone_filters %}{{ profile.phone|national_phone }}')

        result = template.render(Context({'profile': profile}))

        self.assertNotEqual('None', result.strip())
        self.assertIn('613', result.strip())
