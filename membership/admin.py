from django.contrib import admin

from membership.models import Member, Registration


class MemberAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'cohort',)
    list_filter = ('cohort',)
    list_display_links = ('first_name',)

class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('identity', 'first_name', 'last_name', 'registered_at', )
    list_display_links = ('identity',)
    date_hierarchy = 'registered_at'
    ordering = ('-registered_at',)

admin.site.register(Member, MemberAdmin)
admin.site.register(Registration, RegistrationAdmin)
