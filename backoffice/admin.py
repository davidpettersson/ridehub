from adminsortable2.admin import SortableAdminBase, SortableStackedInline
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from backoffice.actions import cancel_event, duplicate_event, archive_event
from backoffice.models import Member, Ride, Route, Event, Program, SpeedRange, Registration


class RideInline(SortableStackedInline):
    model = Ride
    autocomplete_fields = ('route',)
    extra = 0


class RegistrationInline(admin.TabularInline):
    model = Registration
    readonly_fields = ('state', 'name', 'email', 'ride')
    fields = readonly_fields
    can_delete = False
    extra = 0
    max_num = 0


class EventAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ('name', 'starts_at', 'registration_count', 'links', 'cancelled', 'archived',)
    inlines = [RideInline, ]
    ordering = ('-starts_at',)
    date_hierarchy = 'starts_at'
    list_filter = ('starts_at', 'program', 'cancelled', 'archived',)
    search_fields = ('name',)
    actions = [cancel_event, archive_event, duplicate_event]
    readonly_fields = ('cancelled', 'cancelled_at', 'cancellation_reason', 'archived', 'archived_at')

    def links(self, obj):
        public_url = reverse('event_detail', args=[obj.id])
        full_url = reverse('event_registrations_full', args=[obj.id])
        return format_html('<a href="{}">Public event page</a>, <a href="{}">Full registration details</a>', public_url,
                           full_url)

    links.short_description = 'Links'

    fieldsets = [
        (None, {
            'fields': ('program', 'name', 'description', 'starts_at', 'location', 'location_url', 'virtual')
        }),
        ('Registration options', {
            'fields': ('registration_closes_at', 'external_registration_url', 'registration_limit'),
            'description': 'Configure when registration closes and/or provide an external registration URL.'
        }),
        ('Registration form settings', {
            'fields': ('ride_leaders_wanted', 'requires_emergency_contact'),
            'description': 'Configure what information is collected during registration.'
        }),
        ('Cancellation information', {
            'fields': ('cancelled', 'cancelled_at', 'cancellation_reason'),
            'description': 'These fields are read-only and can only be modified through the Cancel Event action.'
        }),
        ('Archiving information', {
            'fields': ('archived', 'archived_at'),
            'description': 'These fields are read-only and are set through the Archive Event action.'
        })
    ]


class SpeedRangeAdmin(admin.ModelAdmin):
    list_display = ('range', 'lower_limit', 'upper_limit',)


class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'updated_at',)
    search_fields = ('name',)


class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'event', 'state', 'ride', 'speed_range_preference')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'event__name',)
    readonly_fields = ('state', 'emergency_contact_name', 'emergency_contact_phone', 'submitted_at', 'confirmed_at',
                       'withdrawn_at')
    fields = ('user', 'event', 'ride', 'speed_range_preference', 'ride_leader_preference') + readonly_fields


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
