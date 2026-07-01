from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin

from content.models import Page


@admin.register(Page)
class PageAdmin(MarkdownxModelAdmin):
    list_display = ('title', 'slug', 'published', 'updated_at')
    list_filter = ('published',)
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'body')
