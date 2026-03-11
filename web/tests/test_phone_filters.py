from django.test import TestCase

from phonenumber_field.phonenumber import PhoneNumber

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
