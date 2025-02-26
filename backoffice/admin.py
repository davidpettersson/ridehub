from django.contrib import admin

from backoffice.models import Member, Ride, Route, Event, Program, SpeedRange, Registration


class RideInline(admin.TabularInline):
    model = Ride
    autocomplete_fields = ('route',)

class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'starts_at', 'virtual', 'ride_leaders_wanted')
    inlines = [RideInline]
    date_hierarchy = 'starts_at'
    ordering = ('starts_at',)
    list_filter = ('virtual',)
    search_fields = ('name',)

class SpeedRangeAdmin(admin.ModelAdmin):
    list_display = ('lower_limit', 'upper_limit',)

class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'url',)
    search_fields = ('name',)

admin.site.register(Program)
admin.site.register(Member)
admin.site.register(Route, RouteAdmin)
admin.site.register(SpeedRange, SpeedRangeAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Registration)