from django import template

register = template.Library()

EVENT_URL_NAMES = {
    'upcoming',
    'calendar',
    'calendar_month',
    'events',
    'event_detail',
    'riders_list',
    'registration_create',
    'event_registrations_manage',
    'staff_registration_add',
    'staff_registration_edit',
    'staff_registration_withdraw',
    'membership_number_capture',
    'registration_submitted',
    'registration_verification_sent',
}


@register.simple_tag(takes_context=True)
def events_nav_active(context):
    request = context.get('request')
    resolver_match = getattr(request, 'resolver_match', None)
    if resolver_match and resolver_match.url_name in EVENT_URL_NAMES:
        return ' active'
    return ''
