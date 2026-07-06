from django.contrib import admin

from agents.models import AgentRequest


@admin.register(AgentRequest)
class AgentRequestAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'family', 'kind', 'method', 'path', 'status_code', 'probe', 'authenticated')
    list_filter = ('family', 'kind', 'probe', 'created_at')
    search_fields = ('user_agent', 'path')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
