from adminsortable2.admin import SortableAdminBase, SortableStackedInline
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from backoffice.actions import cancel_event, duplicate_event
from backoffice.models import Member, Ride, Route, Event, Program, SpeedRange, Registration, Announcement, UserProfile
from .forms import EventAdminForm


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
    list_display = ('starts_at', 'name', 'registration_count', 'links', 'visible', 'cancelled',)
    list_display_links = ['name', ]
    inlines = [RideInline, ]
    ordering = ('-starts_at',)
    date_hierarchy = 'starts_at'
    list_filter = ('starts_at', 'program', 'visible', 'cancelled',)
    search_fields = ('name',)
    actions = [cancel_event, duplicate_event]
    readonly_fields = ('cancelled', 'cancelled_at', 'cancellation_reason', 'archived', 'archived_at')
    form = EventAdminForm

    def links(self, obj):
        public_url = reverse('event_detail', args=[obj.id])
        full_url = reverse('event_registrations_full', args=[obj.id])
        return format_html('<a href="{}">Public event page</a>, <a href="{}">Full registration details</a>', public_url,
                           full_url)

    links.short_description = 'Links'

    fieldsets = [
        (None, {
            'fields': ('program', 'name', 'description', 'starts_at', 'ends_at', 'location', 'location_url',
                       'organizer_email', 'virtual',
                       'visible')
        }),
        ('Registration options', {
            'fields': ('registration_closes_at', 'external_registration_url', 'registration_limit'),
            'description': 'Configure when registration closes and/or provide an external registration URL.'
        }),
        ('Registration form settings', {
            'fields': ('ride_leaders_wanted', 'requires_emergency_contact', 'requires_membership'),
            'description': 'Configure what information is collected during registration.'
        }),
        ('Cancellation information', {
            'fields': ('cancelled', 'cancelled_at', 'cancellation_reason'),
            'description': 'These fields are read-only and can only be modified through the Cancel Event action.'
        }),
    ]


class SpeedRangeAdmin(admin.ModelAdmin):
    list_display = ('range', 'lower_limit', 'upper_limit',)


class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'updated_at',)
    search_fields = ('name',)


class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('id', 'state', 'submitted_at', 'username', 'event', 'ride', 'speed_range_preference')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'event__name',)
    autocomplete_fields = ('user', 'event')
    list_filter = ('submitted_at', 'state',)

    fields = (
        'user',
        'event',
        'state',
        'ride',
        'speed_range_preference',
        'ride_leader_preference',
        'first_name',
        'last_name',
        'email',
        'phone',
        'emergency_contact_name',
        'emergency_contact_phone',
        'submitted_at',
        'confirmed_at',
        'withdrawn_at',
        'ip_address',
        'user_agent',
        'authenticated',
    )

    readonly_fields = (
        'state',
        'submitted_at',
        'confirmed_at',
        'withdrawn_at',
        'ip_address',
        'user_agent',
        'authenticated',
    )

    def has_add_permission(self, request):
        return False

    @admin.display(ordering='user__username')
    def username(self, obj):
        return obj.user


class MemberAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'begin_at', 'end_at',)
    search_fields = ('title', 'text',)
    list_filter = ('type',)
    ordering = ('-end_at',)


class ProgramAdmin(admin.ModelAdmin):
    list_display = ('emoji', 'name', 'description', 'archived',)
    list_display_links = ('name',)
    list_filter = ('archived',)
    ordering = ('name',)


admin.site.register(Program, ProgramAdmin)
admin.site.register(UserProfile)
admin.site.register(Member, MemberAdmin)
admin.site.register(Route, RouteAdmin)
admin.site.register(SpeedRange, SpeedRangeAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Registration, RegistrationAdmin)
admin.site.register(Announcement, AnnouncementAdmin)
