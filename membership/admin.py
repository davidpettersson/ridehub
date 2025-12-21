from django.contrib import admin

from membership.models import Member, Registration, Match


class MemberAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'last_registration_year', 'cohort',)
    list_display_links = ('first_name',)
    search_fields = ('first_name', 'last_name',)


class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('identity', 'first_name', 'last_name', 'registered_at',)
    list_display_links = ('identity',)
    date_hierarchy = 'registered_at'
    ordering = ('-registered_at',)
    search_fields = ('first_name', 'last_name',)


class MatchAdmin(admin.ModelAdmin):
    list_display = ('registration', 'member', 'method', 'confidence',)


admin.site.register(Member, MemberAdmin)
admin.site.register(Registration, RegistrationAdmin)
admin.site.register(Match, MatchAdmin)
