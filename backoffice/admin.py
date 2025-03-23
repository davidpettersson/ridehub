from django.contrib import admin, messages

from backoffice.models import Member, Ride, Route, Event, Program, SpeedRange, Registration
from backoffice.actions import cancel_event, duplicate_event


class RideInline(admin.TabularInline):
    model = Ride
    autocomplete_fields = ('route',)
    extra = 0

class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'starts_at', 'virtual', 'registration_count', 'registration_open')
    inlines = [RideInline]
    ordering = ('starts_at',)
    date_hierarchy = 'starts_at'
    list_filter = ('virtual', 'starts_at',)
    search_fields = ('name',)
    actions = [cancel_event, duplicate_event]


class SpeedRangeAdmin(admin.ModelAdmin):
    list_display = ('range', 'lower_limit', 'upper_limit',)


class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'updated_at', )
    search_fields = ('name',)

class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('email', 'event', 'registered_at', 'ride', 'speed_range_preference')
    search_fields = ('email', )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class MemberAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(Program)
admin.site.register(Member, MemberAdmin)
admin.site.register(Route, RouteAdmin)
admin.site.register(SpeedRange, SpeedRangeAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Registration, RegistrationAdmin)
