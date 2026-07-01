from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from content.services.page_service import PageService


def page_detail(request: HttpRequest, slug: str) -> HttpResponse:
    page = PageService().fetch_visible_by_slug(slug, request.user)
    if page is None:
        raise Http404
    return render(request, 'web/pages/detail.html', {'page': page})
