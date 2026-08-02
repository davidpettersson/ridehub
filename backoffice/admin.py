from adminsortable2.admin import SortableAdminBase, SortableStackedInline
from django.contrib import admin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

from audit.context import actor
from backoffice.actions import archive_event, cancel_event, duplicate_event, reschedule_event
from backoffice.models import Forecast, Ride, Route, Event, Program, SpeedRange, Registration, RegistrationSnapshot, Announcement, Notification, UserProfile, UserMembershipNumber
from .forms import EventAdminForm


class AuditedAdminMixin:
    def save_model(self, request, obj, form, change):
        with actor(request.user):
            super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        with actor(request.user):
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        with actor(request.user):
            super().delete_queryset(request, queryset)

    def save_formset(self, request, form, formset, change):
        with actor(request.user):
            super().save_formset(request, form, formset, change)


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


class EventAdmin(AuditedAdminMixin, SortableAdminBase, admin.ModelAdmin):
    list_display = ('starts_at', 'name', 'state', 'admin_registration_count', 'links',)
    list_display_links = ['name', ]
    inlines = [RideInline, ]
    ordering = ('-starts_at',)
    date_hierarchy = 'starts_at'
    list_filter = ('starts_at', 'program', 'state',)
    search_fields = ('name',)
    actions = [cancel_event, reschedule_event, archive_event, duplicate_event]
    readonly_fields = ('cancelled_at', 'cancellation_reason', 'archived_at', 'archival_reason',
                       'rescheduled_at', 'reschedule_reason', 'previous_starts_at', 'previous_ends_at')
    form = EventAdminForm

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            confirmed_registration_count=Count(
                'registration',
                filter=Q(registration__state=Registration.STATE_CONFIRMED)
            )
        )

    @admin.display(description='Registrations', ordering='confirmed_registration_count')
    def admin_registration_count(self, obj):
        if obj.state in (Event.STATE_DRAFT, Event.STATE_ANNOUNCED):
            return '–'
        return obj.confirmed_registration_count

    def links(self, obj):
        public_url = reverse('event_detail', args=[obj.id])
        manage_url = reverse('event_registrations_manage', args=[obj.id])
        return format_html('<a href="{}">Public event page</a>, <a href="{}">Manage registrations</a>', public_url,
                           manage_url)

    links.short_description = 'Links'

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (None, {
                'fields': ('program', 'name', 'description', 'starts_at', 'ends_at', 'all_day',
                           'location', 'location_url',
                           'organizer_email', 'virtual',
                           'state',)
            }),
            ('Registration options', {
                'fields': ('registration_enabled', 'registration_closes_at', 'external_registration_url', 'registration_limit'),
                'description': 'Configure when registration closes and/or provide an external registration URL.'
            }),
            ('Registration form settings', {
                'fields': ('ride_leaders_wanted', 'requires_emergency_contact', 'requires_membership', 'ask_first_time_attendee'),
                'description': 'Configure what information is collected during registration.'
            }),
        ]

        if obj and obj.cancelled_at:
            fieldsets.append(
                ('Cancellation information', {
                    'fields': ('cancelled_at', 'cancellation_reason'),
                    'description': 'These fields are read-only and can only be modified through the Cancel Event action.'
                })
            )

        if obj and obj.rescheduled:
            fieldsets.append(
                ('Reschedule information', {
                    'fields': ('rescheduled_at', 'reschedule_reason', 'previous_starts_at', 'previous_ends_at'),
                    'description': 'These fields are read-only and can only be modified through the Reschedule Event action.'
                })
            )

        if obj and obj.state == Event.STATE_ARCHIVED:
            fieldsets.append(
                ('Archival information', {
                    'fields': ('archived_at', 'archival_reason'),
                    'description': 'This event is archived and is not visible on any public page. '
                                   'Archiving cannot be undone.'
                })
            )

        return fieldsets


class SpeedRangeAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ('range', 'lower_limit', 'upper_limit',)


class RouteAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'url', 'updated_at', 'archived', 'deleted',)
    list_filter = ('archived', 'deleted',)
    search_fields = ('name',)


class ForecastAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ('start_time', 'end_time', 'latitude', 'longitude', 'hourly_count', 'prepared_at',)
    ordering = ('-start_time', '-prepared_at',)
    readonly_fields = ('latitude', 'longitude', 'start_time', 'end_time', 'prepared_at', 'hourly',)

    def has_change_permission(self, request, obj=None):
        return False

    def hourly_count(self, obj):
        return len(obj.hourly)
    hourly_count.short_description = 'Hours'


class RegistrationAdmin(AuditedAdminMixin, admin.ModelAdmin):
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
        'first_time_attendee',
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


class RegistrationSnapshotAdmin(admin.ModelAdmin):
    list_display = ('superseded_at', 'registration', 'actor', 'summary')
    list_filter = ('superseded_at',)
    search_fields = ('registration__email', 'registration__event__name', 'actor__email')
    ordering = ('-superseded_at',)

    readonly_fields = (
        'registration',
        'actor',
        'changed_fields',
        'superseded_at',
    ) + RegistrationSnapshot.SNAPSHOT_FIELDS

    fields = readonly_fields

    @admin.display(description='Changed fields')
    def summary(self, obj):
        return ', '.join(obj.changed_fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AnnouncementAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ('title', 'type', 'audience', 'begin_at', 'end_at',)
    search_fields = ('title', 'text',)
    list_filter = ('type', 'audience',)
    ordering = ('-end_at',)


class ProgramAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ('emoji', 'name', 'description', 'archived',)
    list_display_links = ('name',)
    list_filter = ('archived',)
    ordering = ('name',)


class UserMembershipNumberAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'number', 'year', 'created_at', 'updated_at')
    list_filter = ('year',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'number')


class UserProfileAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'user__first_name', 'user__last_name', 'email_verified', 'name_visibility', 'legacy')
    list_filter = ('email_verified', 'name_visibility', 'legacy')
    search_fields = ('user__first_name', 'user__last_name', 'user__email')
    readonly_fields = ('updated_at',)

    def has_delete_permission(self, request, obj=None):
        return False


class NotificationAdmin(admin.ModelAdmin):
    list_display = ('sent_at', 'kind', 'recipients', 'target_repr')
    list_filter = ('kind', 'sent_at')
    search_fields = ('target_repr',)
    date_hierarchy = 'sent_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Program, ProgramAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Forecast, ForecastAdmin)
admin.site.register(Route, RouteAdmin)
admin.site.register(SpeedRange, SpeedRangeAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Registration, RegistrationAdmin)
admin.site.register(RegistrationSnapshot, RegistrationSnapshotAdmin)
admin.site.register(Announcement, AnnouncementAdmin)
admin.site.register(UserMembershipNumber, UserMembershipNumberAdmin)
admin.site.register(Notification, NotificationAdmin)
