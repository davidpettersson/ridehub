from content.models import Page


class PageService:
    def fetch_visible_by_slug(self, slug, user):
        qs = Page.objects.all() if user.is_staff else Page.objects.filter(published=True)
        return qs.filter(slug=slug).first()
