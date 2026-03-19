from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from backoffice.services.announcement_service import AnnouncementService


def active_announcements(request: HttpRequest) -> HttpResponse:
    service = AnnouncementService()
    announcements = service.fetch_active_announcements()
    return render(request, 'web/components/announcements.html', {'announcements': announcements})
