from django.urls import path

from web.views.debug import trigger_task, trigger_error
from web.views.events import redirect_to_event_list, event_detail, event_list, event_registrations, \
    event_registrations_full
from web.views.events_ical import EventFeed
from web.views.helpers import populate_first_last_names
from web.views.login import LoginFormView, logout_view, CustomLoginView
from web.views.profile import profile, registration_withdraw
from web.views.registrations import registration_create, registration_detail, registration_submitted, registration_list
from web.views.rides import ride_speed_ranges

urlpatterns = [
    path("login/", LoginFormView.as_view(), name="login_form"),
    path("login/auth/", CustomLoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    path('debug/trigger_task', trigger_task),
    path('debug/trigger_error', trigger_error),
    path('helpers/populate_first_last_names', populate_first_last_names),
    path('calendar', redirect_to_event_list, name='calendar'),
    path('events/<int:event_id>/registrations/full', event_registrations_full, name='event_registrations_full'),
    path('events/<int:event_id>/registrations', event_registrations, name='riders_list'),
    path('events/<int:event_id>/registration', registration_create, name='registration_create'),
    path('events/<int:event_id>', event_detail, name='event_detail'),
    path('events.ics', EventFeed(), name='event_feed'),
    path('events', event_list, name='event_list'),
    path('registrations/<int:registration_id>/withdraw', registration_withdraw, name='registration_withdraw'),
    path('registrations/<int:registration_id>', registration_detail, name='registration_detail'),
    path('registrations/submitted', registration_submitted, name='registration_submitted'),
    path('registrations', registration_list, name='registration_list'),
    path('rides/<int:ride_id>/speed-ranges', ride_speed_ranges, name='get_speed_ranges'),
    path('profile', profile, name='profile'),
    path('', redirect_to_event_list, name='index'),
]
