import re

import phonenumbers
from django import template

register = template.Library()

DIALABLE_PATTERN = re.compile(r'[^+0-9,;*#]')


@register.filter(name='national_phone')
def national_phone(value):
    if not value:
        return value
    if isinstance(value, str):
        try:
            value = phonenumbers.parse(value, 'CA')
        except phonenumbers.NumberParseException:
            return value
    if value.country_code is None:
        return str(value)
    return phonenumbers.format_number(value, phonenumbers.PhoneNumberFormat.NATIONAL)


@register.filter(name='phone_uri')
def phone_uri(value):
    if not value:
        return value
    if isinstance(value, str):
        try:
            value = phonenumbers.parse(value, 'CA')
        except phonenumbers.NumberParseException:
            return DIALABLE_PATTERN.sub('', value)
    if value.country_code is None:
        return DIALABLE_PATTERN.sub('', str(value))
    return phonenumbers.format_number(value, phonenumbers.PhoneNumberFormat.E164)
