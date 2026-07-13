from django import template

from backoffice.services.announcement_service import AnnouncementService

register = template.Library()


@register.inclusion_tag('web/components/announcements.html', takes_context=True)
def active_announcements(context):
    service = AnnouncementService()
    announcements = service.fetch_active_announcements(context['request'].user)
    return {'announcements': announcements} 