import django_tables2 as tables
from django.utils.html import format_html

from backoffice.models import Registration
from web.templatetags.phone_filters import national_phone


class RegistrationTable(tables.Table):
    name = tables.Column(order_by=('last_name', 'first_name'))
    email = tables.Column()
    phone = tables.Column()
    ride = tables.Column()
    speed_range_preference = tables.Column(verbose_name="Speed")
    ride_leader_preference = tables.Column(verbose_name="Ride leader")
    emergency_contact_name = tables.Column(verbose_name="Emergency contact")
    emergency_contact_phone = tables.Column(verbose_name="Emergency phone")
    actions = tables.TemplateColumn(
        template_name='web/events/_registration_actions.html',
        orderable=False,
        verbose_name="",
    )

    class Meta:
        model = Registration
        fields = (
            'name', 'email', 'phone', 'ride', 'speed_range_preference',
            'ride_leader_preference', 'emergency_contact_name',
            'emergency_contact_phone', 'actions',
        )
        attrs = {
            'class': 'table',
            'th': {'class': 'small fw-medium'},
        }

    def render_name(self, value, record):
        return format_html(
            '<span class="small fw-medium">{}</span>', value
        )

    def render_email(self, value):
        return format_html('<span class="small text-muted">{}</span>', value)

    def render_phone(self, value):
        formatted = national_phone(value)
        return format_html('<span class="small text-muted">{}</span>', formatted)

    def render_ride(self, value):
        return format_html('<span class="small text-muted">{}</span>', value)

    def render_speed_range_preference(self, value):
        return format_html('<span class="small text-muted">{}</span>', value)

    def render_ride_leader_preference(self, value, record):
        if value == Registration.RideLeaderPreference.YES:
            return format_html('<span class="badge bg-primary">Yes</span>')
        display = record.get_ride_leader_preference_display()
        return format_html('<span class="small text-muted">{}</span>', display)

    def render_emergency_contact_name(self, value):
        return format_html('<span class="small text-muted">{}</span>', value)

    def render_emergency_contact_phone(self, value):
        formatted = national_phone(value)
        return format_html('<span class="small text-muted">{}</span>', formatted)
