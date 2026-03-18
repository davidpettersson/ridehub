import django_tables2 as tables
from django.utils.html import format_html

from backoffice.models import Registration


class RegistrationTable(tables.Table):
    name = tables.Column(order_by=('last_name', 'first_name'))
    email = tables.EmailColumn()
    phone = tables.Column()
    ride = tables.Column()
    speed_range_preference = tables.Column(verbose_name="Speed")
    ride_leader_preference = tables.Column(verbose_name="Ride leader")
    state = tables.Column()
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
            'ride_leader_preference', 'state', 'emergency_contact_name',
            'emergency_contact_phone', 'actions',
        )
        attrs = {
            'class': 'table table-sm table-hover',
            'thead': {'class': 'table-light'},
        }

    def render_ride_leader_preference(self, value):
        if value == Registration.RideLeaderPreference.YES:
            return format_html('<span class="badge bg-primary">Yes</span>')
        return value

    def render_state(self, value):
        badge_classes = {
            Registration.STATE_CONFIRMED: 'bg-success',
            Registration.STATE_WITHDRAWN: 'bg-danger',
            Registration.STATE_SUBMITTED: 'bg-warning text-dark',
        }
        css = badge_classes.get(value, 'bg-secondary')
        return format_html('<span class="badge {}">{}</span>', css, value.title())
