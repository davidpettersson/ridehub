import phonenumbers
from django import template

register = template.Library()


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
