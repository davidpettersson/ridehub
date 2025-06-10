from django import template

from backoffice.services.announcement_service import AnnouncementService

register = template.Library()


@register.inclusion_tag('web/components/announcements.html')
def active_announcements():
    service = AnnouncementService()
    announcements = service.fetch_active_announcements()
    return {'announcements': announcements} 