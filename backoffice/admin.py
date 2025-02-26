from django.contrib import admin

from backoffice.models import Member, Ride, Route, Event, Program, SpeedRange, Registration


class RideInline(admin.TabularInline):
    model = Ride

class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'starts_at', 'virtual', 'ride_leaders_wanted')
    inlines = [RideInline]

class SpeedRangeAdmin(admin.ModelAdmin):
    list_display = ('lower_limit', 'upper_limit',)

admin.site.register(Program)
admin.site.register(Member)
admin.site.register(Route)
admin.site.register(SpeedRange)
admin.site.register(Event, EventAdmin)
admin.site.register(Registration)