import phonenumbers
from django import template

register = template.Library()


@register.filter(name='national_phone')
def national_phone(value):
    if not value:
        return value
    return phonenumbers.format_number(value, phonenumbers.PhoneNumberFormat.NATIONAL)
