import nh3
from django.db import models
from markdownx.models import MarkdownxField
from markdownx.utils import markdownify


class Page(models.Model):
    slug = models.SlugField(unique=True, help_text='URL path segment, e.g. "user-guide".')
    title = models.CharField(max_length=200)
    body = MarkdownxField(
        help_text='Markdown content. Cross-link other pages with relative links, e.g. [User Guide](/pages/user-guide).'
    )
    published = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def body_html(self):
        return nh3.clean(markdownify(self.body))
